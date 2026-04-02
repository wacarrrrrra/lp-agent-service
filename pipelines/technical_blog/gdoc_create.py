"""
Creates a Google Doc in the Blog Drafts Drive folder from a markdown draft.

Uses the Drive API's HTML-to-Doc conversion (uploadType=multipart) so we don't
have to manually manage Docs API batchUpdate indices.

The resulting doc mirrors the format the blog publisher's parse_gdoc.py already
understands — metadata table first, then headings and body — so /sync-to-wordpress
and /publish-blog both work on it directly.
"""
import asyncio
import io
import json
import logging
import os
import re
from typing import Optional

logger = logging.getLogger("uvicorn.error")

GDOC_BLOG_DRAFTS_FOLDER_ID = os.getenv("GDOC_BLOG_DRAFTS_FOLDER_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_DRIVE_DOMAIN = os.getenv("GOOGLE_DRIVE_DOMAIN", "")  # e.g. "datahub.com"

_SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]


def _get_credentials():
    from google.oauth2 import service_account

    val = GOOGLE_SERVICE_ACCOUNT_JSON or "/etc/secrets/google-service-account.json"
    if val.strip().startswith("{"):
        return service_account.Credentials.from_service_account_info(
            json.loads(val), scopes=_SCOPES
        )
    return service_account.Credentials.from_service_account_file(val, scopes=_SCOPES)


def _get_services():
    from googleapiclient.discovery import build

    creds = _get_credentials()
    docs = build("docs", "v1", credentials=creds, cache_discovery=False)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    return docs, drive


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


def _inline_html(text: str) -> str:
    """Convert inline markdown to HTML for Drive import."""
    text = _escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def _md_to_html(
    markdown_body: str,
    diagram_prompt: Optional[str] = None,
) -> str:
    """Convert markdown body to HTML suitable for Drive → Docs conversion."""
    lines = markdown_body.splitlines()
    html_parts = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # [NOTE: ...] — skip entirely
        if re.match(r"^\[NOTE:", stripped, re.IGNORECASE):
            i += 1
            continue

        # [DIAGRAM: description] — render as styled placeholder paragraph
        m_diag = re.match(r"^\[DIAGRAM:\s*(.+)\]$", stripped, re.IGNORECASE)
        if m_diag:
            html_parts.append(
                f'<p style="background:#FFF3CD;border:1px solid #FFC107;padding:8px;border-radius:4px">'
                f'<strong>📊 Diagram needed:</strong> {_escape(m_diag.group(1).strip())}</p>'
            )
            i += 1
            continue

        # [DEFINITION: Title | Body] — styled definition box
        m_def = re.match(r"^\[DEFINITION:\s*(.+?)\s*\|\s*(.+)\]$", stripped, re.IGNORECASE | re.DOTALL)
        if m_def:
            html_parts.append(
                f'<div style="border:1.5px solid #E3E1D6;border-radius:8px;background:#F3F3F6;padding:16px;margin:12px 0">'
                f'<h2 style="margin-top:0">{_inline_html(m_def.group(1).strip())}</h2>'
                f'<p style="margin:0">{_inline_html(m_def.group(2).strip())}</p>'
                f'</div>'
            )
            i += 1
            continue

        # [CALLOUT: Title | Body] — styled callout box
        m_call = re.match(r"^\[CALLOUT:\s*(.+?)\s*\|\s*(.+)\]$", stripped, re.IGNORECASE | re.DOTALL)
        if m_call:
            html_parts.append(
                f'<div style="border:1.5px solid #E3E1D6;border-radius:8px;background:#F3F3F6;padding:16px;margin:12px 0">'
                f'<h3 style="margin-top:0">{_inline_html(m_call.group(1).strip())}</h3>'
                f'<p style="margin:0">{_inline_html(m_call.group(2).strip())}</p>'
                f'</div>'
            )
            i += 1
            continue

        # [FAQ] — render as a styled heading so it's visible as a section marker
        if stripped.upper() == "[FAQ]":
            html_parts.append(
                '<p style="background:#E8F4F8;border-left:4px solid #006DCD;padding:8px 12px;font-weight:bold">'
                'FAQ section — questions below will become accordion blocks in WordPress</p>'
            )
            i += 1
            continue

        # Fenced code block
        if stripped.startswith("```"):
            lang = stripped[3:].strip() or "code"
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(_escape(lines[i]))
                i += 1
            html_parts.append(
                f'<div style="border:1px solid #ddd;border-radius:4px;margin:8px 0">'
                f'<div style="background:#e8e8e8;padding:3px 8px;font-size:11px;font-family:monospace;color:#555;border-bottom:1px solid #ddd">{_escape(lang)}</div>'
                f'<pre style="font-family:\'Courier New\',monospace;background:#f5f5f5;padding:8px;margin:0;white-space:pre-wrap">'
                + "\n".join(code_lines)
                + "</pre></div>"
            )
            i += 1
            continue

        if line.startswith("## "):
            html_parts.append(f"<h2>{_inline_html(line[3:].strip())}</h2>")
        elif line.startswith("### "):
            html_parts.append(f"<h3>{_inline_html(line[4:].strip())}</h3>")
        elif line.startswith("#### "):
            html_parts.append(f"<h4>{_inline_html(line[5:].strip())}</h4>")
        elif line.startswith("# "):
            html_parts.append(f"<h1>{_inline_html(line[2:].strip())}</h1>")
        elif line.startswith("- ") or line.startswith("* "):
            items = []
            while i < len(lines) and (lines[i].startswith("- ") or lines[i].startswith("* ")):
                items.append(f"<li>{_inline_html(lines[i][2:].strip())}</li>")
                i += 1
            html_parts.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif line.startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].startswith("|"):
                table_lines.append(lines[i])
                i += 1
            rows = [r for r in table_lines if not re.match(r"^\|[-| :]+\|$", r.strip())]
            html_rows = []
            for ri, row in enumerate(rows):
                cells = [c.strip() for c in row.strip("|").split("|")]
                tag = "th" if ri == 0 else "td"
                html_rows.append(
                    "<tr>" + "".join(f"<{tag}>{_inline_html(c)}</{tag}>" for c in cells) + "</tr>"
                )
            html_parts.append(
                '<table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse">'
                + "".join(html_rows)
                + "</table>"
            )
            continue
        elif stripped:
            html_parts.append(f"<p>{_inline_html(stripped)}</p>")

        i += 1

    # Inject diagram placeholder at the top of the body if a diagram_prompt was supplied
    if diagram_prompt:
        short_desc = diagram_prompt.split(".")[0].strip()
        placeholder = (
            f'<p style="background:#FFF3CD;border:1px solid #FFC107;padding:8px;border-radius:4px">'
            f'<strong>📊 Diagram needed:</strong> {_escape(short_desc)}</p>'
        )
        html_parts.insert(0, placeholder)

    return "\n".join(html_parts)


def _build_doc_html(
    title: str,
    meta_description: str,
    slug: str,
    focus_keyword: str,
    markdown_body: str,
    author: str = "DataHub",
    diagram_prompt: Optional[str] = None,
) -> str:
    """Assemble the full HTML document: metadata table + body."""
    meta_table = f"""
<table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;margin-bottom:24px">
  <tr><td><strong>Title</strong></td><td>{_escape(title)}</td></tr>
  <tr><td><strong>Meta description</strong></td><td>{_escape(meta_description)}</td></tr>
  <tr><td><strong>Author</strong></td><td>{_escape(author or "DataHub")}</td></tr>
  <tr><td><strong>Category</strong></td><td>Engineering</td></tr>
  <tr><td><strong>Url slug</strong></td><td>{_escape(slug)}</td></tr>
  <tr><td><strong>Focus keyword</strong></td><td>{_escape(focus_keyword)}</td></tr>
  <tr><td><strong>Recommended resources</strong></td><td></td></tr>
</table>
""".strip()

    body_html = _md_to_html(markdown_body, diagram_prompt=diagram_prompt)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>{_escape(title)}</title></head>
<body>
{meta_table}
<h1>{_escape(title)}</h1>
{body_html}
</body>
</html>"""


def _create_doc_sync(
    title: str,
    meta_description: str,
    slug: str,
    focus_keyword: str,
    markdown_body: str,
    author: str = "DataHub",
    diagram_prompt: Optional[str] = None,
) -> str:
    """Synchronous inner function — runs in a thread via asyncio.to_thread."""
    from googleapiclient.http import MediaIoBaseUpload

    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON not set")
    if not GDOC_BLOG_DRAFTS_FOLDER_ID:
        raise RuntimeError("GDOC_BLOG_DRAFTS_FOLDER_ID not set")

    _, drive = _get_services()

    html_content = _build_doc_html(
        title=title,
        meta_description=meta_description,
        slug=slug,
        focus_keyword=focus_keyword,
        markdown_body=markdown_body,
        author=author,
        diagram_prompt=diagram_prompt,
    )

    media = MediaIoBaseUpload(
        io.BytesIO(html_content.encode("utf-8")),
        mimetype="text/html",
        resumable=False,
    )
    file_metadata = {
        "name": title,
        "mimeType": "application/vnd.google-apps.document",
        "parents": [GDOC_BLOG_DRAFTS_FOLDER_ID],
    }
    doc = drive.files().create(
        body=file_metadata,
        media_body=media,
        fields="id",
        supportsAllDrives=True,
    ).execute()

    doc_id = doc["id"]

    # Share with the Google Workspace domain (org-only) if GOOGLE_DRIVE_DOMAIN is set.
    # If not set, no public permission is added — the doc is accessible only to the service account.
    if GOOGLE_DRIVE_DOMAIN:
        drive.permissions().create(
            fileId=doc_id,
            body={"type": "domain", "role": "writer", "domain": GOOGLE_DRIVE_DOMAIN},
            fields="id",
            supportsAllDrives=True,
        ).execute()

    return f"https://docs.google.com/document/d/{doc_id}/edit"


async def create_blog_draft_doc(
    title: str,
    meta_description: str,
    slug: str,
    focus_keyword: str,
    markdown_body: str,
    author: str = "DataHub",
    diagram_prompt: Optional[str] = None,
) -> str:
    """Create a Google Doc in the Blog Drafts folder. Returns the doc URL."""
    return await asyncio.to_thread(
        _create_doc_sync,
        title,
        meta_description,
        slug,
        focus_keyword,
        markdown_body,
        author,
        diagram_prompt,
    )
