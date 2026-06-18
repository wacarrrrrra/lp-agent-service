"""
Build the @Bart Slack prompt for the /bart-validate pipeline.

Three input shapes:
  - keywords     → numbered list from a Google Sheet
  - lp_content   → prose from a Google Doc (with [BART:] callouts surfaced)
  - html_url     → text extracted from a hosted HTML page

Bart replies in the same thread, classifies each item into one of three
buckets (Confirmed / Conditional / Exclude), ends with a markdown summary
table, and writes BART_DONE on its own line.
"""
import os
import re
from typing import Iterable, List, Optional, Sequence

BART_USER_ID = os.getenv("BART_USER_ID", "")

# ── content-block formatters ──────────────────────────────────────────────────

def _format_keywords_block(sheet_rows: Sequence[Sequence[str]]) -> str:
    """Render sheet rows as a numbered list. Skips fully-empty rows."""
    if not sheet_rows:
        return "_(no rows found in the sheet)_"

    header = [c.strip() for c in (sheet_rows[0] if sheet_rows else [])]
    keyword_idx = 0
    volume_idx: Optional[int] = None
    for i, h in enumerate(header):
        low = h.lower()
        if any(t in low for t in ("keyword", "term", "query")) and keyword_idx == 0:
            keyword_idx = i
        if "volume" in low or "searches" in low:
            volume_idx = i

    data_rows = sheet_rows[1:] if header else sheet_rows
    lines: List[str] = []
    n = 0
    for row in data_rows:
        kw = (row[keyword_idx] if keyword_idx < len(row) else "").strip()
        if not kw:
            continue
        n += 1
        if volume_idx is not None and volume_idx < len(row) and row[volume_idx]:
            lines.append(f"{n}. {kw} — {row[volume_idx]}")
        else:
            lines.append(f"{n}. {kw}")
    return "\n".join(lines) if lines else "_(no keywords parsed)_"


def _format_lp_content_block(doc_text: str) -> str:
    """Pass the doc through, preserving any [BART: ...] validation asks inline."""
    if not (doc_text or "").strip():
        return "_(doc appears empty)_"
    return doc_text.strip()


def _format_html_block(html_text: str) -> str:
    """Pass the stripped HTML text through."""
    if not (html_text or "").strip():
        return "_(page appears empty after stripping HTML)_"
    return html_text.strip()


def format_content_block(
    source_type: str,
    sheet_rows: Optional[Sequence[Sequence[str]]],
    doc_text: Optional[str],
    html_text: Optional[str] = None,
) -> str:
    if source_type == "keywords":
        return _format_keywords_block(sheet_rows or [])
    if source_type == "html_url":
        return _format_html_block(html_text or "")
    return _format_lp_content_block(doc_text or "")


# ── prompt builder ────────────────────────────────────────────────────────────

_LABEL_BY_TYPE = {
    "keywords":   "keyword list",
    "lp_content": "LP copy",
    "html_url":   "hosted page",
}


def build_bart_validate_prompt(
    *,
    request_id: str,
    source_type: str,
    source_url: str,
    context: str,
    content_block: str,
) -> str:
    """Compose the @Bart validation request Slack message."""
    label = _LABEL_BY_TYPE.get(source_type, "content")
    return (
        f"<@{BART_USER_ID}> {label} validation request for DataHub SEM.\n\n"
        f"*REQUEST ID:* {request_id}\n"
        f"*CONTEXT:* {context}\n"
        f"*SOURCE:* {source_url}\n\n"
        "---\n\n"
        "*CONTENT TO VALIDATE:*\n"
        f"{content_block}\n\n"
        "---\n\n"
        "*FOR EACH ITEM, CLASSIFY INTO ONE OF THREE BUCKETS:*\n\n"
        "✅ *Confirmed* — DataHub has documented, shipped capabilities that match. "
        "Cite the specific feature, API, or docs page.\n\n"
        "⚠️ *Conditional (needs SME review)* — DataHub has adjacent or partial coverage, "
        "but the framing in the source would be a stretch without SME confirmation. "
        "Example: \"governance maturity model\" — the concept exists but not as a named "
        "framework, so a PM needs to confirm how we'd position it.\n\n"
        "❌ *Exclude* — DataHub has no legitimate coverage; using this would misrepresent "
        "the product. Anything tied to specific analyst content we don't have (Gartner, "
        "McKinsey, Forrester reports we haven't been featured in) defaults here.\n\n"
        "*RELEVANT DOCS TO CHECK:*\n"
        "- https://docs.datahub.com/docs/features\n"
        "- https://docs.datahub.com/docs/authorization/access-policies-guide\n"
        "- https://docs.datahub.com/docs/managed-datahub/observe/assertions\n"
        "- https://docs.datahub.com/docs/features/feature-guides/compliance-forms/overview\n"
        "- https://docs.datahub.com/docs/features/feature-guides/lineage\n"
        "- https://docs.datahub.com/docs/glossary/business-glossary\n\n"
        "Add any additional docs pages that are relevant to the specific content being validated.\n\n"
        "---\n\n"
        "*REQUIRED OUTPUT FORMAT:*\n"
        "1. Per-item analysis (one item per paragraph): the item, the verdict (Confirmed / "
        "Conditional / Exclude), and your reasoning with specific feature/doc references.\n"
        "2. End with a markdown summary table in this exact shape (one row per item):\n\n"
        "```\n"
        "| # | Item | Verdict | Notes |\n"
        "|---|------|---------|-------|\n"
        "| 1 | <item> | ✅ Confirmed | <one-line note + doc ref> |\n"
        "| 2 | <item> | ⚠️ Conditional | <one-line note + what an SME needs to check> |\n"
        "| 3 | <item> | ❌ Exclude | <one-line reason> |\n"
        "```\n\n"
        "3. After the table, reply `BART_DONE` on its own line."
    )


# ── response parsing ──────────────────────────────────────────────────────────

_TABLE_LINE_RE = re.compile(r"^\s*\|.*\|\s*$")


def extract_summary_table(bart_response: str) -> str:
    """Pull the markdown table out of Bart's response. Returns '' if none found."""
    lines = (bart_response or "").splitlines()
    table_lines: List[str] = []
    in_table = False
    for line in lines:
        if _TABLE_LINE_RE.match(line):
            table_lines.append(line.rstrip())
            in_table = True
        elif in_table and not line.strip():
            # Blank line ends the table
            break
        elif in_table:
            # Non-table content right after — also ends it
            break
    return "\n".join(table_lines)


def count_verdicts(summary_table: str) -> dict:
    """Count rows by verdict emoji in the markdown table. Tolerates missing rows."""
    counts = {"confirmed": 0, "conditional": 0, "exclude": 0}
    for line in (summary_table or "").splitlines():
        if "✅" in line:
            counts["confirmed"] += 1
        elif "⚠" in line or "⚠️" in line:
            counts["conditional"] += 1
        elif "❌" in line:
            counts["exclude"] += 1
    return counts
