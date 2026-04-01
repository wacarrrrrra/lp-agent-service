import base64
import logging
import os
import re
from typing import Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger("uvicorn.error")

WP_BASE_URL = os.getenv("WP_BASE_URL", "https://datahub.com")
WP_USER = os.getenv("WP_USER", "")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "")

_AUTHOR_NAME = "John Joyce"


def _auth() -> Dict[str, str]:
    token = base64.b64encode(f"{WP_USER}:{WP_APP_PASSWORD}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Markdown → Gutenberg block conversion
# ---------------------------------------------------------------------------

def _escape_code(text: str) -> str:
    """HTML-escape code block content so special characters render literally."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline_md(text: str) -> str:
    """Convert inline markdown (bold, code, links) to HTML."""
    # Links: [text](url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    # Bold: **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Inline code: `text`
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def _md_to_blocks(markdown: str) -> str:
    """Convert markdown body to Gutenberg block HTML."""
    lines = markdown.splitlines()
    blocks: List[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Fenced code block
        if line.strip().startswith("```"):
            lang = line.strip()[3:].strip()
            code_lines: List[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            code_content = _escape_code("\n".join(code_lines))
            blocks.append(
                f'<!-- wp:code -->\n'
                f'<pre class="wp-block-code"><code lang="{lang}" class="language-{lang}">'
                f'{code_content}</code></pre>\n<!-- /wp:code -->'
            )
            i += 1
            continue

        # Diagram placeholder comment — wrap in wp:html
        if line.strip().startswith("<!-- DIAGRAM_NEEDED:"):
            blocks.append(
                f'<!-- wp:html -->\n{line.strip()}\n<!-- /wp:html -->'
            )
            i += 1
            continue

        # H2
        if line.startswith("## "):
            text = _inline_md(line[3:].strip())
            blocks.append(
                f'<!-- wp:heading {{"level":2}} -->\n'
                f'<h2 class="wp-block-heading">{text}</h2>\n'
                f'<!-- /wp:heading -->'
            )
            i += 1
            continue

        # H3
        if line.startswith("### "):
            text = _inline_md(line[4:].strip())
            blocks.append(
                f'<!-- wp:heading {{"level":3}} -->\n'
                f'<h3 class="wp-block-heading">{text}</h3>\n'
                f'<!-- /wp:heading -->'
            )
            i += 1
            continue

        # H4
        if line.startswith("#### "):
            text = _inline_md(line[5:].strip())
            blocks.append(
                f'<!-- wp:heading {{"level":4}} -->\n'
                f'<h4 class="wp-block-heading">{text}</h4>\n'
                f'<!-- /wp:heading -->'
            )
            i += 1
            continue

        # H1 (skip — title set via post title field)
        if line.startswith("# "):
            i += 1
            continue

        # Unordered list
        if line.startswith("- ") or line.startswith("* "):
            items: List[str] = []
            while i < len(lines) and (lines[i].startswith("- ") or lines[i].startswith("* ")):
                items.append(f"<li>{_inline_md(lines[i][2:].strip())}</li>")
                i += 1
            blocks.append(
                f'<!-- wp:list -->\n<ul>{"".join(items)}</ul>\n<!-- /wp:list -->'
            )
            continue

        # Table
        if line.startswith("|"):
            table_lines: List[str] = []
            while i < len(lines) and lines[i].startswith("|"):
                table_lines.append(lines[i])
                i += 1
            rows = [r for r in table_lines if not re.match(r"^\|[-| :]+\|$", r.strip())]
            html_rows: List[str] = []
            for ri, row in enumerate(rows):
                cells = [c.strip() for c in row.strip("|").split("|")]
                tag = "th" if ri == 0 else "td"
                html_rows.append(
                    "<tr>" + "".join(f"<{tag}>{_inline_md(c)}</{tag}>" for c in cells) + "</tr>"
                )
            table_html = f'<table><tbody>{"".join(html_rows)}</tbody></table>'
            blocks.append(
                f'<!-- wp:table -->\n<figure class="wp-block-table">{table_html}</figure>\n<!-- /wp:table -->'
            )
            continue

        # Blank line — skip
        if not line.strip():
            i += 1
            continue

        # Paragraph
        blocks.append(
            f'<!-- wp:paragraph -->\n<p>{_inline_md(line.strip())}</p>\n<!-- /wp:paragraph -->'
        )
        i += 1

    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# WP REST API helpers
# ---------------------------------------------------------------------------

async def _get_category_id(name: str) -> Optional[int]:
    if not name:
        return None
    # Try the first word if name contains a comma (e.g. "Engineering, AI")
    search_name = name.split(",")[0].strip()
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"{WP_BASE_URL}/wp-json/wp/v2/categories",
            params={"search": search_name},
            headers=_auth(),
        )
    data = r.json()
    if isinstance(data, list) and data:
        return data[0]["id"]
    return None


async def _get_wp_user_id(name: str) -> Optional[int]:
    if not name:
        return None
    search = name.split(",")[0].strip()  # "John Joyce, Co-Founder" → "John Joyce"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"{WP_BASE_URL}/wp-json/wp/v2/users",
            params={"search": search},
            headers=_auth(),
        )
    data = r.json()
    if isinstance(data, list) and data:
        return data[0]["id"]
    return None


async def _get_media_id_by_filename(filename: str) -> Optional[int]:
    """Look up a media item ID by exact filename using the WP media library search."""
    basename = filename.split("/")[-1]
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"{WP_BASE_URL}/wp-json/wp/v2/media",
            params={"search": basename, "media_type": "image", "per_page": 5},
            headers=_auth(),
        )
    if r.status_code != 200:
        return None
    data = r.json()
    if not isinstance(data, list):
        return None
    for item in data:
        source = item.get("source_url", "")
        if basename in source:
            return item["id"]
    return data[0]["id"] if data else None


async def _find_existing_post(slug: str) -> Optional[int]:
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


async def _set_rankmath_meta(
    post_id: int,
    seo_title: str,
    meta_description: str,
    focus_keyword: str,
) -> None:
    rm_meta = {}
    if seo_title:
        rm_meta["rank_math_title"] = seo_title
    if meta_description:
        rm_meta["rank_math_description"] = meta_description
    if focus_keyword:
        rm_meta["rank_math_focus_keyword"] = focus_keyword
    if not rm_meta:
        return
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            f"{WP_BASE_URL}/wp-json/rankmath/v1/updateMeta",
            json={"objectID": post_id, "objectType": "post", "meta": rm_meta},
            headers=_auth(),
        )
    if r.status_code not in (200, 201):
        logger.warning("RankMath meta update failed (%s): %s", r.status_code, r.text[:200])


async def publish_draft(
    title: str,
    slug: str,
    meta_description: str,
    focus_keyword: str,
    category: str,
    markdown_body: str,
    hero_filename: str,
    featured_filename: str,
    socialcard_filename: str,
    diagram_prompt: Optional[str] = None,
) -> Tuple[int, str]:
    """
    Convert markdown to blocks, create/update WP draft, set ACF + RankMath fields.
    Returns (post_id, edit_url).
    """
    # Inject diagram placeholder at top of content if needed
    content_md = markdown_body
    if diagram_prompt:
        placeholder = f"<!-- DIAGRAM_NEEDED: {diagram_prompt} -->"
        content_md = placeholder + "\n\n" + content_md

    block_content = _md_to_blocks(content_md)

    # Look up IDs in parallel
    category_id = await _get_category_id(category)
    author_id = await _get_wp_user_id(_AUTHOR_NAME)
    hero_id = await _get_media_id_by_filename(hero_filename)
    featured_id = await _get_media_id_by_filename(featured_filename)
    socialcard_id = await _get_media_id_by_filename(socialcard_filename)
    existing_id = await _find_existing_post(slug)

    seo_title = f"{title} | DataHub"

    payload: Dict = {
        "title": title,
        "slug": slug,
        "status": "draft",
        "content": block_content,
        "excerpt": meta_description,
    }
    if category_id:
        payload["categories"] = [category_id]
    if author_id:
        payload["author"] = author_id
    if featured_id:
        payload["featured_media"] = featured_id

    async with httpx.AsyncClient(timeout=30) as client:
        if existing_id:
            url = f"{WP_BASE_URL}/wp-json/wp/v2/posts/{existing_id}"
            r = await client.post(url, json=payload, headers=_auth())
        else:
            url = f"{WP_BASE_URL}/wp-json/wp/v2/posts"
            r = await client.post(url, json=payload, headers=_auth())

    r.raise_for_status()
    post = r.json()
    post_id: int = post["id"]

    # ACF fields
    acf_fields: Dict = {"hero_title_color": "light"}
    if hero_id:
        acf_fields["hero_image"] = hero_id
    if socialcard_id:
        acf_fields["social_card_image"] = socialcard_id

    async with httpx.AsyncClient(timeout=20) as client:
        r2 = await client.post(
            f"{WP_BASE_URL}/wp-json/wp/v2/posts/{post_id}",
            json={"acf": acf_fields},
            headers=_auth(),
        )
    if r2.status_code not in (200, 201):
        logger.warning("ACF update failed (%s): %s", r2.status_code, r2.text[:200])

    # RankMath SEO fields
    await _set_rankmath_meta(post_id, seo_title, meta_description, focus_keyword)

    edit_url = f"{WP_BASE_URL}/wp-admin/post.php?post={post_id}&action=edit"
    return post_id, edit_url
