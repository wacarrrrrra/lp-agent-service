"""
Creates a Google Doc in the Technical LP Shared Drive folder from LP copy markdown.

Uses the Drive API's HTML-to-Doc conversion (uploadType=multipart) so we don't
have to manage Docs API batchUpdate indices manually. Mirrors the pattern in
pipelines/technical_blog/gdoc_create.py with a leaner HTML template (no metadata
table, no shortcodes — just title + body).
"""
import asyncio
import io
import json
import logging
import os
import re
from typing import Optional

logger = logging.getLogger("uvicorn.error")

GDOC_TECHNICAL_LP_FOLDER_ID = os.getenv(
    "GDOC_TECHNICAL_LP_FOLDER_ID", "1co9SGQqJYZNdG-HGBj7BKuD4AXixnXOa"
)
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_DRIVE_DOMAIN = os.getenv("GOOGLE_DRIVE_DOMAIN", "")

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


def _get_drive_service():
    from googleapiclient.discovery import build

    creds = _get_credentials()
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


def _inline_html(text: str) -> str:
    text = _escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def _md_to_html(markdown_body: str) -> str:
    """Convert LP copy markdown to HTML. Supports h1-h3, paragraphs, bullets."""
    lines = markdown_body.splitlines()
    html_parts = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if line.startswith("### "):
            html_parts.append(f"<h3>{_inline_html(line[4:].strip())}</h3>")
        elif line.startswith("## "):
            html_parts.append(f"<h2>{_inline_html(line[3:].strip())}</h2>")
        elif line.startswith("# "):
            html_parts.append(f"<h1>{_inline_html(line[2:].strip())}</h1>")
        elif line.startswith("- ") or line.startswith("* "):
            items = []
            while i < len(lines) and (lines[i].startswith("- ") or lines[i].startswith("* ")):
                items.append(f"<li>{_inline_html(lines[i][2:].strip())}</li>")
                i += 1
            html_parts.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif stripped:
            html_parts.append(f"<p>{_inline_html(stripped)}</p>")

        i += 1

    return "\n".join(html_parts)


def _build_doc_html(title: str, markdown_body: str) -> str:
    body_html = _md_to_html(markdown_body)
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>{_escape(title)}</title></head>
<body>
{body_html}
</body>
</html>"""


def _create_doc_sync(title: str, markdown_body: str) -> str:
    from googleapiclient.http import MediaIoBaseUpload

    if not GDOC_TECHNICAL_LP_FOLDER_ID:
        raise RuntimeError("GDOC_TECHNICAL_LP_FOLDER_ID not set")

    drive = _get_drive_service()
    html_content = _build_doc_html(title, markdown_body)

    media = MediaIoBaseUpload(
        io.BytesIO(html_content.encode("utf-8")),
        mimetype="text/html",
        resumable=False,
    )
    file_metadata = {
        "name": title,
        "mimeType": "application/vnd.google-apps.document",
        "parents": [GDOC_TECHNICAL_LP_FOLDER_ID],
    }
    doc = drive.files().create(
        body=file_metadata,
        media_body=media,
        fields="id",
        supportsAllDrives=True,
    ).execute()
    doc_id = doc["id"]

    if GOOGLE_DRIVE_DOMAIN:
        drive.permissions().create(
            fileId=doc_id,
            body={"type": "domain", "role": "writer", "domain": GOOGLE_DRIVE_DOMAIN},
            fields="id",
            supportsAllDrives=True,
        ).execute()

    return f"https://docs.google.com/document/d/{doc_id}/edit"


async def create_technical_lp_doc(title: str, markdown_body: str) -> str:
    """Create a Google Doc in the Technical LP Shared Drive folder. Returns the doc URL."""
    return await asyncio.to_thread(_create_doc_sync, title, markdown_body)
