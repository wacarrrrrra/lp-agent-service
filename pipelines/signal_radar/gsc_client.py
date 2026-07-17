"""
Google Search Console client for Signal Radar.

Pulls query-level performance data for a property and computes week-over-week
deltas. Uses the same bart-validate service account as gdoc_read.py — the
account just needs "Restricted" access on the GSC property and the Search
Console API enabled in the GCP project.
"""
import asyncio
import json
import logging
import os
from datetime import date, timedelta
from typing import Dict, List

logger = logging.getLogger("uvicorn.error")

BART_VALIDATE_SERVICE_ACCOUNT_JSON = os.getenv("BART_VALIDATE_SERVICE_ACCOUNT_JSON", "")
_DEFAULT_SECRET_FILE = "/etc/secrets/bart-validate-sa.json"
GSC_PROPERTY = os.getenv("GSC_PROPERTY", "sc-domain:datahub.com")

_GSC_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def _get_credentials():
    from google.oauth2 import service_account

    val = BART_VALIDATE_SERVICE_ACCOUNT_JSON or _DEFAULT_SECRET_FILE
    if val.strip().startswith("{"):
        return service_account.Credentials.from_service_account_info(
            json.loads(val), scopes=_GSC_SCOPES
        )
    return service_account.Credentials.from_service_account_file(val, scopes=_GSC_SCOPES)


def _query_sync(property_url: str, start_date: str, end_date: str, row_limit: int = 25000) -> list:
    from googleapiclient.discovery import build

    creds = _get_credentials()
    svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)

    resp = svc.searchanalytics().query(
        siteUrl=property_url,
        body={
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["query"],
            "rowLimit": row_limit,
        },
    ).execute()

    return resp.get("rows", []) or []


async def fetch_query_deltas(
    property_url: str = "",
    days_recent: int = 7,
    days_prior: int = 7,
    lag_days: int = 3,
) -> List[Dict]:
    """Return rising-query records, sorted by impression delta descending.

    Each record: {query, impressions_recent, impressions_prior, delta, velocity, clicks_recent, position_recent}

    Velocity is (delta / prior) when prior > 0; queries brand-new this week get velocity=None
    to signal "not comparable" but they'll still bubble up via absolute delta if impressions land.
    """
    site = property_url or GSC_PROPERTY
    # GSC data lags a few days — end our recent window there
    end = date.today() - timedelta(days=lag_days)
    recent_start = end - timedelta(days=days_recent - 1)
    prior_end   = recent_start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=days_prior - 1)

    logger.info(
        "GSC pull site=%s recent=[%s..%s] prior=[%s..%s]",
        site, recent_start, end, prior_start, prior_end,
    )

    recent_rows, prior_rows = await asyncio.gather(
        asyncio.to_thread(_query_sync, site, recent_start.isoformat(), end.isoformat()),
        asyncio.to_thread(_query_sync, site, prior_start.isoformat(), prior_end.isoformat()),
    )

    prior_impressions = {r["keys"][0]: r.get("impressions", 0) for r in prior_rows}

    results: List[Dict] = []
    for r in recent_rows:
        query = r["keys"][0]
        rec_impr = r.get("impressions", 0)
        pri_impr = prior_impressions.get(query, 0)
        delta = rec_impr - pri_impr
        if pri_impr > 0:
            velocity = delta / pri_impr
        else:
            velocity = None  # brand new
        results.append({
            "query": query,
            "impressions_recent": rec_impr,
            "impressions_prior": pri_impr,
            "delta": delta,
            "velocity": velocity,
            "clicks_recent": r.get("clicks", 0),
            "position_recent": r.get("position", 0.0),
        })

    # Rank by absolute impression delta, positive first
    results.sort(key=lambda d: d["delta"], reverse=True)
    return results
