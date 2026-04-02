"""
/sync-to-wordpress pipeline.

Reads a Google Doc (using the Docs API), parses the metadata table and body,
converts to Gutenberg blocks, and updates the existing WordPress draft in place.
Does NOT create a new post — it overwrites the draft that /technical-blog created.
"""
import asyncio
import json
import logging
import os
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

from pipelines.technical_blog.wp_publish import (
    _auth,
    _md_to_blocks,
    _inline_md,
    _set_rankmath_meta,
    WP_BASE_URL,
)

logger = logging.getLogger("uvicorn.error")

GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
BLOG_PUBLISHER_CHANNEL = os.getenv("BLOG_PUBLISHER_CHANNEL", "")

_SCOPES = ["https://www.googleapis.com/auth/documents.readonly"]

# Fields preserved from original creation — never overwritten on sync
_SKIP_ACF_FIELDS = {"hero_image", "featured_media", "social_card_image", "hero_title_color"}

_METADATA_KEYS = {
    "title", "meta title", "meta description", "author", "category",
    "url", "slug", "url slug", "resource", "recommended resource",
    "focus keyword", "keyword",
}


# ---------------------------------------------------------------------------
# Google Docs parsing
# ---------------------------------------------------------------------------

def _extract_doc_id(url: str) -> str:
    m = re.search(r"/document/d/([a-zA-Z0-9_-]+)", url)
    if not m:
        raise ValueError(f"Cannot extract doc ID from URL: {url}")
    return m.group(1)


def _get_docs_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    val = GOOGLE_SERVICE_ACCOUNT_JSON or "/etc/secrets/google-service-account.json"
    if val.strip().startswith("{"):
        creds = service_account.Credentials.from_service_account_info(
            json.loads(val), scopes=_SCOPES
        )
    else:
        creds = service_account.Credentials.from_service_account_file(val, scopes=_SCOPES)
    return build("docs", "v1", credentials=creds, cache_discovery=False)


def _cell_text(cell: Dict) -> str:
    parts = []
    for content_el in cell.get("content", []):
        para = content_el.get("paragraph", {})
        for el in para.get("elements", []):
            parts.append(el.get("textRun", {}).get("content", ""))
    return "".join(parts).strip()


def _para_text(para: Dict) -> str:
    return "".join(
        el.get("textRun", {}).get("content", "")
        for el in para.get("elements", [])
    ).strip()


def _para_style(para: Dict) -> str:
    return para.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")


_MONOSPACE_FONTS = {"courier new", "courier", "roboto mono", "consolas", "source code pro", "inconsolata", "monospace"}


def _is_code_para(para: Dict) -> bool:
    """Return True if every text run in the paragraph uses a monospace font."""
    elements = para.get("elements", [])
    if not elements:
        return False
    for el in elements:
        tr = el.get("textRun", {})
        content = tr.get("content", "")
        if content in ("", "\n"):
            continue
        font = tr.get("textStyle", {}).get("weightedFontFamily", {}).get("fontFamily", "").lower()
        if font not in _MONOSPACE_FONTS:
            return False
    return True


def _is_metadata_table(table: Dict) -> bool:
    rows = table.get("tableRows", [])
    for row in rows[:3]:
        cells = row.get("tableCells", [])
        if len(cells) < 2:
            continue
        key = _cell_text(cells[0]).lower()
        if any(mk in key for mk in _METADATA_KEYS):
            return True
    return False


def _parse_doc(doc: Dict) -> Tuple[Dict, str]:
    """
    Parse a Google Doc into (metadata_dict, markdown_body).
    Metadata comes from the first table that looks like a metadata table.
    Body content is converted back to markdown for the Gutenberg block converter.
    """
    body_content = doc.get("body", {}).get("content", [])
    meta: Dict = {}
    md_lines: List[str] = []
    meta_table_found = False
    in_code_block = False

    for el in body_content:
        if "table" in el:
            table = el["table"]
            if not meta_table_found and _is_metadata_table(table):
                # Parse metadata table
                meta_table_found = True
                for row in table.get("tableRows", []):
                    cells = row.get("tableCells", [])
                    if len(cells) < 2:
                        continue
                    key = _cell_text(cells[0]).lower().strip()
                    val = _cell_text(cells[1]).strip()
                    if "title" in key and "meta" not in key:
                        meta["title"] = val
                    elif "meta" in key and "desc" in key:
                        meta["meta_description"] = val
                    elif "author" in key:
                        meta["author"] = val
                    elif "category" in key:
                        meta["category"] = val
                    elif "slug" in key or "url" in key:
                        if val:
                            meta["url_slug"] = val.rstrip("/").split("/")[-1]
                    elif "focus" in key or "keyword" in key:
                        meta["focus_keyword"] = val
                    elif "resource" in key:
                        raw = [r.strip() for r in re.split(r"[\n,\s]+", val) if r.strip()]
                        meta["recommended_resources"] = [
                            r.rstrip("/").split("/")[-1] for r in raw
                        ]
                continue  # skip meta table from body

            # Non-metadata table → markdown table
            rows = table.get("tableRows", [])
            for ri, row in enumerate(rows):
                cells = row.get("tableCells", [])
                cell_texts = [_cell_text(c) for c in cells]
                md_lines.append("| " + " | ".join(cell_texts) + " |")
                if ri == 0:
                    md_lines.append("| " + " | ".join(["---"] * len(cells)) + " |")
            md_lines.append("")
            continue

        if "paragraph" in el:
            para = el["paragraph"]
            text = _para_text(para)
            style = _para_style(para)

            if not text:
                if in_code_block:
                    pass  # blank line inside code — keep collecting
                else:
                    md_lines.append("")
                continue

            # Code block detection: monospace-font paragraph → fenced code block
            if _is_code_para(para) and style == "NORMAL_TEXT":
                if not in_code_block:
                    md_lines.append("```")  # open fence (language unknown after GDoc round-trip)
                    in_code_block = True
                md_lines.append(text)
                continue

            # Non-code paragraph — close any open code fence first
            if in_code_block:
                md_lines.append("```")
                in_code_block = False

            if style == "HEADING_1":
                md_lines.append(f"# {text}")
            elif style == "HEADING_2":
                md_lines.append(f"## {text}")
            elif style == "HEADING_3":
                md_lines.append(f"### {text}")
            elif style == "HEADING_4":
                md_lines.append(f"#### {text}")
            else:
                md_lines.append(text)

    if in_code_block:
        md_lines.append("```")  # close any dangling fence

    markdown_body = "\n".join(md_lines).strip()
    return meta, markdown_body


def _fetch_and_parse_sync(gdoc_url: str) -> Tuple[Dict, str]:
    service = _get_docs_service()
    doc_id = _extract_doc_id(gdoc_url)
    doc = service.documents().get(documentId=doc_id).execute()
    return _parse_doc(doc)


async def _fetch_and_parse(gdoc_url: str) -> Tuple[Dict, str]:
    return await asyncio.to_thread(_fetch_and_parse_sync, gdoc_url)


# ---------------------------------------------------------------------------
# WordPress update (slug-based lookup, no image fields overwritten)
# ---------------------------------------------------------------------------

async def _find_post_by_slug(slug: str) -> Optional[int]:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"{WP_BASE_URL}/wp-json/wp/v2/posts",
            params={"slug": slug.strip("/"), "status": "any", "per_page": 1},
            headers=_auth(),
        )
    data = r.json()
    if isinstance(data, list) and data:
        return data[0]["id"]
    return None


async def _update_wp_draft(
    post_id: int,
    title: str,
    slug: str,
    meta_description: str,
    focus_keyword: str,
    block_content: str,
    recommended_resources: Optional[List[str]] = None,
) -> str:
    payload: Dict[str, Any] = {
        "title": title,
        "slug": slug,
        "content": block_content,
        "excerpt": meta_description,
        "status": "draft",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{WP_BASE_URL}/wp-json/wp/v2/posts/{post_id}",
            json=payload,
            headers=_auth(),
        )
    r.raise_for_status()

    await _set_rankmath_meta(
        post_id,
        seo_title=f"{title} | DataHub",
        meta_description=meta_description,
        focus_keyword=focus_keyword,
    )

    # Update recommended resources if the reviewer filled them in
    if recommended_resources:
        from pipelines.technical_blog.wp_publish import _get_media_id_by_filename
        # Look up post IDs by slug across known post types
        resource_ids = []
        for res_slug in recommended_resources:
            pid = await _lookup_post_id_by_slug(res_slug)
            if pid:
                resource_ids.append(pid)
        if resource_ids:
            async with httpx.AsyncClient(timeout=20) as client:
                await client.post(
                    f"{WP_BASE_URL}/wp-json/wp/v2/posts/{post_id}",
                    json={"acf": {
                        "related_resources_style": "custom",
                        "recommended_resources": resource_ids,
                    }},
                    headers=_auth(),
                )

    return f"{WP_BASE_URL}/wp-admin/post.php?post={post_id}&action=edit"


async def _lookup_post_id_by_slug(slug: str) -> Optional[int]:
    endpoints = [
        "/wp/v2/posts", "/wp/v2/articles", "/wp/v2/guides",
        "/wp/v2/news", "/wp/v2/use-cases", "/wp/v2/webinars",
        "/wp/v2/customer-stories", "/wp/v2/events", "/wp/v2/demos",
    ]
    async with httpx.AsyncClient(timeout=20) as client:
        for endpoint in endpoints:
            r = await client.get(
                f"{WP_BASE_URL}/wp-json{endpoint}",
                params={"slug": slug.strip("/")},
                headers=_auth(),
            )
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and data:
                    return data[0]["id"]
    return None


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

async def run_sync_pipeline(
    gdoc_url: str,
    requester_channel: str,
    thread_ts: str,
    post_message: Callable,
) -> None:
    """
    Parse the Google Doc and update the matching WordPress draft in place.
    Called directly from the /sync-to-wordpress slash command handler.
    """
    try:
        await post_message(
            requester_channel,
            "🔄 Syncing Google Doc to WordPress…",
            thread_ts=thread_ts,
        )

        meta, markdown_body = await _fetch_and_parse(gdoc_url)

        title = meta.get("title", "").strip()
        slug = meta.get("url_slug", "").strip()
        meta_description = meta.get("meta_description", "").strip()
        focus_keyword = meta.get("focus_keyword", "").strip()
        recommended_resources = meta.get("recommended_resources")

        if not slug:
            await post_message(
                requester_channel,
                "❌ Sync failed — no URL slug found in the Google Doc metadata table.",
                thread_ts=thread_ts,
            )
            return

        post_id = await _find_post_by_slug(slug)
        if not post_id:
            await post_message(
                requester_channel,
                f"❌ Sync failed — no WordPress draft found with slug `{slug}`. "
                f"The draft must be created first via `/technical-blog`.",
                thread_ts=thread_ts,
            )
            return

        block_content = _md_to_blocks(markdown_body)
        edit_url = await _update_wp_draft(
            post_id=post_id,
            title=title,
            slug=slug,
            meta_description=meta_description,
            focus_keyword=focus_keyword,
            block_content=block_content,
            recommended_resources=recommended_resources,
        )

        await post_message(
            requester_channel,
            f"✅ *WordPress draft updated*\n\n"
            f"*{title}*\n"
            f"{edit_url}\n\n"
            f"Synced from: {gdoc_url}\n"
            f"Ready to publish when you are.",
            thread_ts=thread_ts,
        )

    except Exception as e:
        logger.exception("run_sync_pipeline failed: %s", e)
        try:
            await post_message(
                requester_channel,
                f"❌ Sync failed: `{e}`",
                thread_ts=thread_ts,
            )
        except Exception:
            pass
