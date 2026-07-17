"""
Load Google Ads keyword coverage from a Google Sheet exported via Google Ads'
"Download → Google Sheets" flow, and expose a lookup that Signal Radar uses to
annotate rising GSC queries with "already targeted" / "no coverage" status.

The Ads → Sheets export typically has 1–3 title/metadata rows above a header
row containing "Campaign", "Ad group", "Keyword", "Match type", "Keyword status"
(and metric columns). The parser scans the first 10 rows to locate the header
by looking for cells that contain both "Ad group" and "Keyword" text; positions
of the other columns are best-effort.

Coverage lookup is fuzzy:
  - exact:      query == bidded keyword (case-insensitive)
  - contains:   the bidded phrase is a substring of the query (broader query)
  - within:     the query is a substring of the bidded phrase (narrower query)
None of the above = no coverage. Match kind is surfaced in the digest.
"""
import logging
import os
from typing import Dict, Optional, Tuple

from pipelines.bart_validate.gdoc_read import read_sheet

logger = logging.getLogger("uvicorn.error")

SIGNAL_RADAR_ADS_SHEET_URL = os.getenv("SIGNAL_RADAR_ADS_SHEET_URL", "")


def _find_ads_header(rows) -> Optional[Tuple[int, Dict[str, int]]]:
    """Scan the first 10 rows for a header containing both Keyword and Ad group columns.
    Returns (header_row_index, {logical_name: column_index}) or None."""
    for i, row in enumerate(rows[:10]):
        cols: Dict[str, int] = {}
        for j, cell in enumerate(row):
            low = (cell or "").strip().lower()
            if not low:
                continue
            if "ad group" in low or "adgroup" in low:
                cols.setdefault("ad_group", j)
            elif low == "keyword" or low.startswith("keyword ") or "search keyword" in low:
                cols.setdefault("keyword", j)
            elif low == "campaign" or low.startswith("campaign "):
                cols.setdefault("campaign", j)
            elif "match type" in low or low == "match":
                cols.setdefault("match_type", j)
            elif "keyword status" in low or (low == "status"):
                cols.setdefault("status", j)
        if "keyword" in cols and "ad_group" in cols:
            return i, cols
    return None


async def load_ads_coverage(sheet_url: str = "") -> Dict[str, Dict]:
    """Return {keyword_lowercase: {ad_group, campaign, match_type, status}} from the Ads sheet.
    Returns {} silently on any load/parse failure — Signal Radar treats empty as "no coverage data."
    """
    url = (sheet_url or SIGNAL_RADAR_ADS_SHEET_URL).strip()
    if not url:
        return {}

    try:
        _resolved_tab, rows = await read_sheet(url, "")
    except Exception as e:
        logger.warning("Ads coverage sheet fetch failed: %s", e)
        return {}
    if not rows:
        return {}

    header = _find_ads_header(rows)
    if not header:
        logger.warning("Ads coverage sheet: could not locate a header row with Keyword + Ad group columns")
        return {}
    header_idx, cols = header

    kw_col = cols["keyword"]
    ag_col = cols["ad_group"]
    mt_col = cols.get("match_type")
    st_col = cols.get("status")
    cp_col = cols.get("campaign")

    coverage: Dict[str, Dict] = {}
    for row in rows[header_idx + 1:]:
        kw_raw = (row[kw_col] if kw_col < len(row) else "").strip()
        if not kw_raw:
            continue
        # Skip totals/summary rows that Ads sometimes appends
        low = kw_raw.lower()
        if low.startswith("total") or low.startswith("--"):
            continue
        # Ads exports sometimes wrap phrase-match keywords in double quotes and
        # exact-match ones in [brackets]. Strip these for consistent lookup.
        kw = kw_raw.strip('"').strip("[]").strip().lower()
        if not kw:
            continue

        entry = {
            "ad_group": (row[ag_col] if ag_col < len(row) else "").strip(),
            "keyword_raw": kw_raw,  # preserve original for display
        }
        if mt_col is not None and mt_col < len(row):
            entry["match_type"] = row[mt_col].strip()
        if st_col is not None and st_col < len(row):
            entry["status"] = row[st_col].strip()
        if cp_col is not None and cp_col < len(row):
            entry["campaign"] = row[cp_col].strip()

        coverage[kw] = entry

    logger.info("Ads coverage loaded: %d unique keywords", len(coverage))
    return coverage


def lookup_coverage(query: str, coverage: Dict[str, Dict]) -> Optional[Dict]:
    """Return the best coverage match for a query, or None.
    Match kinds: 'exact', 'contains', 'within'. The returned dict includes 'match_kind'."""
    if not query or not coverage:
        return None
    q = query.lower().strip()

    if q in coverage:
        return {**coverage[q], "match_kind": "exact"}

    # Broader query → find any bidded phrase inside it
    for kw, entry in coverage.items():
        if kw and kw in q and len(kw) >= 3:  # avoid trivial "a" / "of" matches
            return {**entry, "match_kind": "contains", "matched_kw": kw}

    # Narrower query → find any bidded phrase that contains it
    for kw, entry in coverage.items():
        if q and q in kw and len(q) >= 3:
            return {**entry, "match_kind": "within", "matched_kw": kw}

    return None
