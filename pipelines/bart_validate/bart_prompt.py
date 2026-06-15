"""
Build the @Bart Slack prompt for the /bart-validate pipeline.

Two shapes: `keywords` (numbered list from a Google Sheet) and `lp_content`
(prose from a Google Doc, with [BART:] callouts surfaced). Bart replies in the
same thread and ends with BART_DONE.
"""
import os
from typing import List

BART_USER_ID = os.getenv("BART_USER_ID", "")


def _format_keywords_block(sheet_rows: List[List[str]]) -> str:
    """Render sheet rows as a numbered list. Skips fully-empty rows."""
    if not sheet_rows:
        return "_(no rows found in the sheet)_"

    header = [c.strip() for c in (sheet_rows[0] if sheet_rows else [])]
    keyword_idx = 0
    volume_idx = None
    for i, h in enumerate(header):
        low = h.lower()
        if any(t in low for t in ("keyword", "term", "query")) and keyword_idx == 0:
            keyword_idx = i
        if "volume" in low or "searches" in low:
            volume_idx = i

    data_rows = sheet_rows[1:] if header else sheet_rows
    lines = []
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
    """Pass the doc through, lightly marking any [BART: ...] validation asks."""
    if not (doc_text or "").strip():
        return "_(doc appears empty)_"
    # Just return the doc text. Bart's `[BART:]` markers are preserved inline.
    return doc_text.strip()


def build_bart_validate_prompt(
    *,
    request_id: str,
    source_type: str,
    source_url: str,
    context: str,
    content_block: str,
) -> str:
    """Compose the @Bart validation request Slack message."""
    label = "keywords" if source_type == "keywords" else "LP content"
    return (
        f"<@{BART_USER_ID}> {label} validation request for DataHub SEM.\n\n"
        f"*REQUEST ID:* {request_id}\n"
        f"*CONTEXT:* {context}\n"
        f"*SOURCE:* {source_url}\n\n"
        "---\n\n"
        "*CONTENT TO VALIDATE:*\n"
        f"{content_block}\n\n"
        "---\n\n"
        "*FOR EACH ITEM, PLEASE CONFIRM:*\n"
        "1. Does DataHub have documented features or capabilities that genuinely match this query/claim?\n"
        "2. What specific DataHub features, APIs, or docs pages support it?\n"
        "3. Is there anything technically inaccurate or that would be a stretch to claim?\n"
        "4. Flag items where DataHub has NO legitimate coverage and we should exclude.\n\n"
        "*RELEVANT DOCS TO CHECK:*\n"
        "- https://docs.datahub.com/docs/features\n"
        "- https://docs.datahub.com/docs/authorization/access-policies-guide\n"
        "- https://docs.datahub.com/docs/managed-datahub/observe/assertions\n"
        "- https://docs.datahub.com/docs/features/feature-guides/compliance-forms/overview\n"
        "- https://docs.datahub.com/docs/features/feature-guides/lineage\n"
        "- https://docs.datahub.com/docs/glossary/business-glossary\n\n"
        "Add any additional docs pages that are relevant to the specific content being validated.\n\n"
        "Reply `BART_DONE` on its own line when complete."
    )


def format_content_block(source_type: str, sheet_rows, doc_text) -> str:
    """Dispatch to the right formatter based on source_type."""
    if source_type == "keywords":
        return _format_keywords_block(sheet_rows or [])
    return _format_lp_content_block(doc_text or "")
