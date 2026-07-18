"""
Signal Radar pipeline — weekly job.

Pulls rising queries from Google Search Console for the DataHub property, runs each
through the Claude-based classifier to triage as Confirmed / Conditional / Exclude,
and posts TWO Slack digests:
  - Internal channel: full scored list (all buckets)
  - Agency channel:  only 🔥 Strategic (Confirmed + rising fast)

This is a triage pipeline. High-priority findings should be re-submitted to
/bart-validate for authoritative fit-checks (Bart has codebase access that Claude lacks).
"""
import asyncio
import logging
import os
from datetime import date
from typing import Callable, Dict, List, Optional

from pipelines.signal_radar.ads_coverage import load_ads_coverage, lookup_coverage
from pipelines.signal_radar.classifier import classify_queries
from pipelines.signal_radar.gsc_client import fetch_query_deltas

logger = logging.getLogger("uvicorn.error")

# Tuning knobs — set via env vars if needed.
MIN_IMPRESSIONS_RECENT = int(os.getenv("SIGNAL_RADAR_MIN_IMPRESSIONS", "5"))
TOP_N = int(os.getenv("SIGNAL_RADAR_TOP_N", "15"))


def _score(verdict: str, delta: int, velocity: Optional[float]) -> str:
    """Turn a Claude verdict + growth metrics into a Signal Radar tier label."""
    is_hot = delta >= 20 or (velocity is not None and velocity >= 1.0)
    if verdict == "confirmed" and is_hot:
        return "🔥 Strategic"
    if verdict == "confirmed":
        return "✅ Ready"
    if verdict == "conditional":
        return "⚠️ Watch"
    return "⬜ Pass"


def _fmt_velocity(delta: int, velocity: Optional[float]) -> str:
    if velocity is None:
        return f"+{delta} (new)"
    return f"+{delta} ({velocity * 100:+.0f}%)"


def _fmt_coverage(cov: Optional[Dict]) -> str:
    """Short one-cell coverage summary for the table view."""
    if not cov:
        return "✗ none"
    ag = (cov.get("ad_group") or "?")[:22]
    kind = cov.get("match_kind", "")
    if kind == "exact":
        return f"✓ {ag}"
    return f"~ {ag}"  # fuzzy match: contains/within


def _format_internal_digest(scored: List[Dict], recent_window: str, prior_window: str, coverage_stats: str = "") -> str:
    header_line = f"_Recent: {recent_window} · Prior: {prior_window}_"
    if coverage_stats:
        header_line += f"\n_{coverage_stats}_"
    lines = [
        f"🛰️ *Signal Radar — weekly digest*",
        header_line,
        "",
        f"Top {len(scored)} rising queries on datahub.com. Triage below — for authoritative fit-check on the interesting ones, use `/bart-validate`.",
        "",
        "```",
        f"{'Tier':<15} {'Δ impressions':<18} {'Coverage':<26} {'Query'}",
        "-" * 100,
    ]
    for s in scored:
        tier = s["tier"]
        vel = _fmt_velocity(s["delta"], s["velocity"])
        cov = _fmt_coverage(s.get("coverage"))
        q = s["query"][:40]
        lines.append(f"{tier:<15} {vel:<18} {cov:<26} {q}")
    lines.append("```")
    lines.append("")
    lines.append("*Reasoning per query:*")
    for s in scored:
        cov_note = ""
        c = s.get("coverage")
        if c:
            ag = c.get("ad_group", "?")
            kind = c.get("match_kind", "")
            mt = c.get("match_type", "")
            matched = c.get("matched_kw")
            cov_note = f" · covered by ad group `{ag}`" + (f" ({mt})" if mt else "")
            if kind in ("contains", "within") and matched:
                cov_note += f" — fuzzy match on `{matched}`"
        else:
            cov_note = " · *no ad coverage*"
        lines.append(f"• {s['tier']} — `{s['query']}` — {s['reason']}{cov_note}")
    return "\n".join(lines)


def _format_agency_digest(strategic: List[Dict], recent_window: str) -> str:
    gaps      = [s for s in strategic if not s.get("coverage")]
    covered   = [s for s in strategic if s.get("coverage")]

    lines = [
        f"🎯 *Weekly rising queries — DataHub is a strong fit*",
        f"_Signal window: {recent_window}. Suggestions for LP + SEM prioritization._",
        "",
    ]

    if gaps:
        lines.append("*🚨 Gap opportunities* — DataHub-confirmed coverage, rising traffic, and NO current ad targeting:")
        for s in gaps:
            lines.append(f"• *{s['query']}* — {_fmt_velocity(s['delta'], s['velocity'])} impressions")
            lines.append(f"    _{s['reason']}_")
        lines.append("")

    if covered:
        lines.append("*📈 Already targeted, rising fast* — consider bid/creative review:")
        for s in covered:
            ag = s["coverage"].get("ad_group", "?")
            lines.append(f"• *{s['query']}* — {_fmt_velocity(s['delta'], s['velocity'])} impressions · in `{ag}`")
            lines.append(f"    _{s['reason']}_")
        lines.append("")

    lines.append(f"_Triaged as 🔥 Strategic: {len(strategic)} queries. {len(gaps)} gaps, {len(covered)} already targeted._")
    lines.append("_Deeper fit-check on any of these? Use `/bart-validate` with the query as context._")
    return "\n".join(lines)


async def run_signal_radar(
    post_message: Callable,
    internal_channel: str,
    agency_channel: str,
) -> Dict:
    """Fetch → classify → score → post. Returns a summary dict for the caller."""
    logger.info("Signal Radar run starting")
    try:
        deltas = await fetch_query_deltas()
    except Exception as e:
        logger.exception("GSC fetch failed: %s", e)
        if internal_channel:
            try:
                await post_message(
                    internal_channel,
                    f"❌ Signal Radar run failed at GSC fetch: `{e}`",
                )
            except Exception:
                pass
        return {"ok": False, "error": f"gsc_fetch: {e}"}

    rising = [
        d for d in deltas
        if d["delta"] > 0 and d["impressions_recent"] >= MIN_IMPRESSIONS_RECENT
    ]
    top = rising[:TOP_N]

    if not top:
        msg = (
            f"🛰️ *Signal Radar — weekly digest*\n"
            f"_No rising queries this week (min {MIN_IMPRESSIONS_RECENT} impressions filter). "
            f"Nothing to triage._"
        )
        if internal_channel:
            await post_message(internal_channel, msg)
        logger.info("Signal Radar: no rising queries this week")
        return {"ok": True, "rising_count": 0}

    # Kick off Claude classification and Ads-coverage load in parallel
    classifications, ads_coverage = await asyncio.gather(
        classify_queries([d["query"] for d in top]),
        load_ads_coverage(),
    )
    logger.info("Signal Radar: %d rising queries, %d ads keywords loaded",
                len(top), len(ads_coverage))

    # Diagnostic: surface coverage-load stats in the digest header so failures are
    # visible without needing to open Render logs.
    ads_sheet_url = os.getenv("SIGNAL_RADAR_ADS_SHEET_URL", "").strip()
    if not ads_sheet_url:
        coverage_stats = "⚠️ Ads coverage: SIGNAL_RADAR_ADS_SHEET_URL not set"
    elif not ads_coverage:
        coverage_stats = "⚠️ Ads coverage: sheet fetched but 0 keywords parsed — check sharing + header row"
    else:
        sample = ", ".join(list(ads_coverage.keys())[:3])
        coverage_stats = f"Ads coverage: {len(ads_coverage)} keywords loaded (sample: {sample})"

    scored: List[Dict] = []
    for d, c in zip(top, classifications):
        verdict = c["verdict"]
        tier = _score(verdict, d["delta"], d["velocity"])
        coverage = lookup_coverage(d["query"], ads_coverage) if ads_coverage else None
        scored.append({
            **d,
            "verdict": verdict,
            "reason": c["reason"],
            "tier": tier,
            "coverage": coverage,
        })

    # Window strings for the digest header
    today = date.today()
    recent_window = f"last 7 days ending {today.isoformat()}"
    prior_window  = "prior 7 days"

    if internal_channel:
        await post_message(
            internal_channel,
            _format_internal_digest(scored, recent_window, prior_window, coverage_stats),
        )

    strategic = [s for s in scored if s["tier"] == "🔥 Strategic"]
    if strategic and agency_channel:
        await post_message(agency_channel, _format_agency_digest(strategic, recent_window))

    counts = {
        "strategic": sum(1 for s in scored if s["tier"] == "🔥 Strategic"),
        "ready":     sum(1 for s in scored if s["tier"] == "✅ Ready"),
        "watch":     sum(1 for s in scored if s["tier"] == "⚠️ Watch"),
        "pass":      sum(1 for s in scored if s["tier"] == "⬜ Pass"),
    }
    logger.info("Signal Radar run complete: %s", counts)
    return {"ok": True, "rising_count": len(scored), "counts": counts}
