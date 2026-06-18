"""
Read source content for /bart-validate from one of:
  - Google Sheet  → read_sheet(url, tab_name) → (resolved_tab, rows)
  - Google Doc    → read_doc(url) → plain text
  - Hosted HTML   → read_html_url(url) → plain text (tags stripped)

Google APIs use the bart-validate service account (`spreadsheets.readonly` +
`documents.readonly`). HTML URLs are fetched anonymously over public HTTP.
"""
import asyncio
import json
import logging
import os
import re
from typing import List, Optional, Tuple

import httpx

logger = logging.getLogger("uvicorn.error")

BART_VALIDATE_SERVICE_ACCOUNT_JSON = os.getenv("BART_VALIDATE_SERVICE_ACCOUNT_JSON", "")
_DEFAULT_SECRET_FILE = "/etc/secrets/bart-validate-sa.json"

_READ_SCOPES = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _get_credentials():
    from google.oauth2 import service_account

    val = BART_VALIDATE_SERVICE_ACCOUNT_JSON or _DEFAULT_SECRET_FILE
    if val.strip().startswith("{"):
        return service_account.Credentials.from_service_account_info(
            json.loads(val), scopes=_READ_SCOPES
        )
    return service_account.Credentials.from_service_account_file(val, scopes=_READ_SCOPES)


def _build(service: str, version: str):
    from googleapiclient.discovery import build

    return build(service, version, credentials=_get_credentials(), cache_discovery=False)


_SHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")
_DOC_ID_RE   = re.compile(r"/document/d/([a-zA-Z0-9_-]+)")
_GID_RE      = re.compile(r"[#&]gid=(\d+)")


def _extract_sheet_id(url: str) -> str:
    m = _SHEET_ID_RE.search(url or "")
    if not m:
        raise ValueError(f"URL does not look like a Google Sheet: {url!r}")
    return m.group(1)


def _extract_doc_id(url: str) -> str:
    m = _DOC_ID_RE.search(url or "")
    if not m:
        raise ValueError(f"URL does not look like a Google Doc: {url!r}")
    return m.group(1)


def _extract_gid(url: str) -> Optional[int]:
    m = _GID_RE.search(url or "")
    return int(m.group(1)) if m else None


def _read_sheet_sync(url: str, tab_name: str = "") -> Tuple[str, List[List[str]]]:
    """Return (resolved_tab_name, values_rows). Raises a clear error on permission/missing-tab issues."""
    sheet_id = _extract_sheet_id(url)
    sheets = _build("sheets", "v4")

    meta = sheets.spreadsheets().get(spreadsheetId=sheet_id, fields="sheets.properties").execute()
    tabs = [s["properties"] for s in meta.get("sheets", [])]
    if not tabs:
        raise RuntimeError(f"Spreadsheet {sheet_id} has no tabs")

    resolved = None
    if tab_name:
        for t in tabs:
            if t.get("title", "").strip().lower() == tab_name.strip().lower():
                resolved = t["title"]
                break
        if resolved is None:
            available = ", ".join(t.get("title", "") for t in tabs)
            raise RuntimeError(f"Tab {tab_name!r} not found. Available tabs: {available}")
    else:
        gid = _extract_gid(url)
        if gid is not None:
            for t in tabs:
                if t.get("sheetId") == gid:
                    resolved = t["title"]
                    break
        if resolved is None:
            resolved = tabs[0]["title"]

    range_a1 = f"'{resolved}'"
    resp = sheets.spreadsheets().values().get(spreadsheetId=sheet_id, range=range_a1).execute()
    values = resp.get("values", [])
    return resolved, values


def _read_doc_sync(url: str) -> str:
    """Return the doc's plain text content (paragraphs joined by newlines)."""
    doc_id = _extract_doc_id(url)
    docs = _build("docs", "v1")
    doc = docs.documents().get(documentId=doc_id).execute()
    return _doc_body_to_text(doc.get("body", {}).get("content", []))


def _doc_body_to_text(content_blocks: list) -> str:
    out: List[str] = []
    for block in content_blocks:
        para = block.get("paragraph")
        if para:
            line_parts = []
            for el in para.get("elements", []):
                tr = el.get("textRun")
                if tr and tr.get("content"):
                    line_parts.append(tr["content"])
            out.append("".join(line_parts))
            continue
        table = block.get("table")
        if table:
            for row in table.get("tableRows", []):
                cell_texts = []
                for cell in row.get("tableCells", []):
                    cell_texts.append(_doc_body_to_text(cell.get("content", [])).strip())
                out.append(" | ".join(cell_texts))
            out.append("")
    return "".join(out)


async def read_sheet(url: str, tab_name: str = "") -> Tuple[str, List[List[str]]]:
    return await asyncio.to_thread(_read_sheet_sync, url, tab_name)


async def read_doc(url: str) -> str:
    return await asyncio.to_thread(_read_doc_sync, url)


_HTML_ENTITIES = {
    "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
    "&quot;": '"', "&#39;": "'", "&apos;": "'",
}


async def read_html_url(url: str) -> str:
    """Fetch a public HTML URL and return a text-only rendering suitable for Bart to read."""
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(
            url,
            headers={"User-Agent": "bart-validate/1.0 (DataHub SEM validation)"},
        )
        resp.raise_for_status()
        html = resp.text

    # Drop script/style blocks entirely
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # Block-level closes become newlines so structure survives the strip
    html = re.sub(r"</(h[1-6]|p|li|div|section|article|tr|br)\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Decode common entities
    for entity, repl in _HTML_ENTITIES.items():
        text = text.replace(entity, repl)
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
    # Collapse whitespace within each line, drop empty lines
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)
