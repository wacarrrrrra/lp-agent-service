import base64
import json
import logging
import os
import re
import uuid
from typing import Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger("uvicorn.error")

WP_BASE_URL = os.getenv("WP_BASE_URL", "https://datahub.com")
WP_USER = os.getenv("WP_USER", "")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "")

_AUTHOR_NAME = "DataHub"


def _auth() -> Dict[str, str]:
    token = base64.b64encode(f"{WP_USER}:{WP_APP_PASSWORD}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Unique ID helper (Kadence blocks)
# ---------------------------------------------------------------------------

def _uid(post_id: str = "new") -> str:
    short = uuid.uuid4().hex
    return f"{post_id}_{short[:6]}-{short[6:8]}"


# ---------------------------------------------------------------------------
# Markdown → Gutenberg block conversion
# ---------------------------------------------------------------------------

def _escape_code(text: str) -> str:
    """HTML-escape code block content so special characters render literally."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline_md(text: str) -> str:
    """Convert inline markdown (bold, code, links) to HTML."""
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


# ---------------------------------------------------------------------------
# Table block helpers (port of build_blocks.py wide-table treatment)
# ---------------------------------------------------------------------------

def _count_table_cols(table_html: str) -> int:
    """Count columns from the first <tr> in the table HTML."""
    m = re.search(r"<tr>(.*?)</tr>", table_html, re.DOTALL | re.IGNORECASE)
    if not m:
        return 0
    return len(re.findall(r"<t[dh][\s>]", m.group(1), re.IGNORECASE))


def _style_table_cells(table_html: str, compact: bool) -> str:
    """
    Inject inline styles onto every <td>:
    - First row cells get a bold header treatment (gray bg).
    - Remaining cells get padding/border styling.
    """
    pad = "7px 10px" if compact else "10px 14px"
    header_td = (
        f'<td style="font-weight:600;background:#F3F3F6;padding:{pad};'
        f'border:1px solid #E3E1D6;vertical-align:top;white-space:nowrap">'
    )
    body_td = (
        f'<td style="padding:{pad};border:1px solid #E3E1D6;vertical-align:top">'
    )

    rows = re.split(r"(<tr>|</tr>)", table_html)
    result = []
    in_first_row = False
    first_row_done = False
    for part in rows:
        if part == "<tr>" and not first_row_done:
            in_first_row = True
            result.append(part)
        elif part == "</tr>" and in_first_row:
            in_first_row = False
            first_row_done = True
            result.append(part)
        elif in_first_row:
            result.append(
                part.replace("<td>", header_td).replace("<td ", header_td[:-1] + " ")
            )
        else:
            result.append(
                part.replace("<td>", body_td).replace("<td ", body_td[:-1] + " ")
            )
    return "".join(result)


def _block_table(table_html: str) -> str:
    col_count = _count_table_cols(table_html)

    if col_count <= 2:
        # Standard wp:table — fits comfortably in the content column
        return (
            f'<!-- wp:table {{"hasFixedLayout":true,"className":"header-only-gray is-style-stripes"}} -->\n'
            f'<figure class="wp-block-table header-only-gray is-style-stripes">'
            f'<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;">'
            f'<table class="has-fixed-layout">{table_html}</table>'
            f'</div></figure>\n'
            f"<!-- /wp:table -->"
        )

    # 3+ columns: wp:html with negative horizontal margin for wide treatment
    min_width = col_count * 180
    styled_html = _style_table_cells(table_html, compact=True)
    return (
        f"<!-- wp:html -->\n"
        f'<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;'
        f'margin:0 -32px 24px -32px;padding:0 32px">'
        f'<table style="width:100%;border-collapse:collapse;font-size:0.875em;'
        f'min-width:{min_width}px">'
        f'{re.sub(r"^<table>|</table>$", "", styled_html.strip())}'
        f"</table>"
        f"</div>\n"
        f"<!-- /wp:html -->"
    )


# ---------------------------------------------------------------------------
# Shortcode block renderers
# ---------------------------------------------------------------------------

def _block_definition_box(title: str, text: str) -> str:
    heading = title if title.lower().startswith("quick definition") else f"Quick definition: {title}"
    heading_id = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")
    return (
        f"<!-- wp:html -->\n"
        f'<div class="quick-definition-box" style="border:1.5px solid #E3E1D6;border-radius:8px;background-color:#F3F3F6;padding:24px;margin:0 0 24px 0">'
        f'<h2 class="wp-block-heading has-large-font-size" id="{heading_id}" style="margin-top:0;margin-bottom:16px">{heading}</h2>'
        f'<p style="margin:0">{text}</p>'
        f"</div>\n"
        f"<!-- /wp:html -->"
    )


def _block_callout_box(title: str, text: str) -> str:
    return (
        f"<!-- wp:html -->\n"
        f'<div class="callout-box" style="border:1.5px solid #E3E1D6;border-radius:8px;background-color:#F3F3F6;padding:24px;margin:0 0 24px 0">'
        f'<h3 style="margin-top:0;margin-bottom:16px">{title}</h3>'
        f'<p style="margin:0">{text}</p>'
        f"</div>\n"
        f"<!-- /wp:html -->"
    )


def _block_faq_accordion(items: List[Dict]) -> str:
    """Render FAQ items as a Kadence accordion."""
    uid_acc = _uid()
    n = len(items)
    panes_html = ""
    for idx, item in enumerate(items):
        uid_pane = _uid()
        answer_block = f"<!-- wp:paragraph --><p>{item['answer']}</p><!-- /wp:paragraph -->"
        pane_attrs = json.dumps({"titleTag": "h3", "uniqueID": uid_pane}, separators=(",", ":"))
        panes_html += (
            f"<!-- wp:kadence/pane {pane_attrs} -->\n"
            f'<div class="wp-block-kadence-pane kt-accordion-pane kt-accordion-pane-{idx + 1} kt-pane{uid_pane}">'
            f'<div class="kt-accordion-header-wrap"><button class="kt-blocks-accordion-header kt-acccordion-button-label-show" type="button">'
            f'<span class="kt-blocks-accordion-title-wrap"><span class="kt-blocks-accordion-title">{item["question"]}</span></span>'
            f'<span class="kt-blocks-accordion-icon-trigger"></span></button></div>'
            f'<div class="kt-accordion-panel"><div class="kt-accordion-panel-inner">'
            f"{answer_block}"
            f"</div></div></div>\n<!-- /wp:kadence/pane -->\n"
        )

    title_styles = [{"size": ["md", "", ""], "sizeType": "px", "lineHeight": ["", "", ""], "lineType": "", "letterSpacing": "", "family": "", "google": "", "style": "", "weight": "600", "variant": "", "subset": "", "loadGoogle": True, "padding": ["xs", "0", "0", "0"], "marginTop": 16, "color": "", "background": "palette9", "border": ["", "", "", ""], "borderRadius": ["", "", "", ""], "borderWidth": ["", "", "", ""], "colorHover": "palette2", "backgroundHover": "#FFFFFF", "borderHover": ["", "", "", ""], "colorActive": "palette1", "backgroundActive": "#FFFFFF", "borderActive": ["", "", "", ""], "textTransform": ""}]
    title_border = [{"top": ["palette7", "", 1], "right": ["palette7", "", ""], "bottom": ["palette7", "", ""], "left": ["palette7", "", ""], "unit": "px"}]
    content_border = [{"top": ["palette9", "", 0], "right": ["palette9", "", 0], "bottom": ["palette9", "", 0], "left": ["palette9", "", 0], "unit": "px"}]

    acc_attrs = json.dumps({
        "uniqueID": uid_acc,
        "paneCount": n,
        "startCollapsed": True,
        "linkPaneCollapse": False,
        "contentBorderStyle": content_border,
        "contentPadding": ["xs", "0", "0", "0"],
        "titleStyles": title_styles,
        "titleBorder": title_border,
        "titleBorderRadius": ["", 0, 0, 0],
        "iconStyle": "arrow",
        "iconSide": "left",
        "faqSchema": True,
    }, separators=(",", ":"))

    return (
        f"<!-- wp:kadence/accordion {acc_attrs} -->\n"
        f'<div class="wp-block-kadence-accordion alignnone">'
        f'<div class="kt-accordion-wrap kt-accordion-id{uid_acc} kt-accordion-has-{n}-panes kt-active-pane-0 kt-accordion-block kt-pane-header-alignment-left kt-accodion-icon-style-arrow kt-accodion-icon-side-left" style="max-width:none">'
        f'<div class="kt-accordion-inner-wrap" data-allow-multiple-open="true" data-start-open="none">'
        f"{panes_html}"
        f"</div></div></div>\n<!-- /wp:kadence/accordion -->"
    )


# ---------------------------------------------------------------------------
# Kadence rowlayout with sticky TOC
# ---------------------------------------------------------------------------

def _mobile_toc_accordion(post_id: str = "new") -> str:
    uid_acc = _uid(post_id)
    uid_pane = _uid(post_id)
    uid_toc = _uid(post_id)
    return (
        f'<!-- wp:kadence/accordion {{"uniqueID":"{uid_acc}","startCollapsed":true,"contentBgColor":"palette8",'
        f'"contentBorderStyle":[{{"top":["palette9","",0],"right":["palette9","",0],"bottom":["palette9","",0],"left":["palette9","",0],"unit":"px"}}],'
        f'"blockVisibility":{{"controlSets":[{{"id":1,"enable":true,"controls":{{"screenSize":{{"hideOnScreenSize":{{"large":true,"medium":true}}}}}}}}]}}}} -->\n'
        f'<div class="wp-block-kadence-accordion alignnone"><div class="kt-accordion-wrap kt-accordion-id{uid_acc} kt-accordion-has-2-panes kt-active-pane-0 kt-accordion-block kt-pane-header-alignment-left kt-accodion-icon-style-basic kt-accodion-icon-side-right" style="max-width:none"><div class="kt-accordion-inner-wrap" data-allow-multiple-open="false" data-start-open="none">'
        f'<!-- wp:kadence/pane {{"uniqueID":"{uid_pane}"}} -->\n'
        f'<div class="wp-block-kadence-pane kt-accordion-pane kt-accordion-pane-1 kt-pane{uid_pane}">'
        f'<div class="kt-accordion-header-wrap"><button class="kt-blocks-accordion-header kt-acccordion-button-label-show" type="button">'
        f'<span class="kt-blocks-accordion-title-wrap"><span class="kt-blocks-accordion-title">Table of Contents</span></span>'
        f'<span class="kt-blocks-accordion-icon-trigger"></span></button></div>'
        f'<div class="kt-accordion-panel"><div class="kt-accordion-panel-inner">'
        f'<!-- wp:kadence/tableofcontents {{"uniqueID":"{uid_toc}","allowedHeaders":[{{"h1":false,"h2":true,"h3":false,"h4":false,"h5":false,"h6":false}}],"listStyle":"numbered","containerPadding":["0","0","0","0"],"containerBackground":"palette8","title":"","titleBorderColor":"","listGap":[12,"",""],"borderRadius":[16,16,16,16],"containerMargin":["0","0","0","0"],"titleBorderStyle":[{{"top":[null,"",""],"right":[null,"",""],"bottom":[null,"",""],"left":[null,"",""],"unit":"px"}}]}} /-->'
        f"</div></div></div>\n<!-- /wp:kadence/pane -->"
        f"</div></div></div>\n<!-- /wp:kadence/accordion -->\n"
    )


def _wrap_in_rowlayout(left_content: str, post_id: str = "new") -> str:
    uid_row = _uid(post_id)
    uid_left = _uid(post_id)
    uid_right = _uid(post_id)
    uid_toc = _uid(post_id)

    left_inner = _mobile_toc_accordion(post_id) + left_content

    right_inner = (
        f'<!-- wp:kadence/tableofcontents {{"uniqueID":"{uid_toc}",'
        f'"allowedHeaders":[{{"h1":false,"h2":true,"h3":false,"h4":false,"h5":false,"h6":false}}],'
        f'"listStyle":"numbered","containerBackground":"palette8","titleBorderColor":"",'
        f'"listGap":[12,"",""],"borderRadius":[16,16,16,16],"containerMargin":["0","0","lg","0"],'
        f'"titleBorderStyle":[{{"top":[null,"",""],"right":[null,"",""],"bottom":[null,"",""],"left":[null,"",""],"unit":"px"}}]}} /-->'
    )

    border_style = '[{"top":["palette3","",""],"right":["palette3","",""],"bottom":["palette3","",""],"left":["palette3","",""],"unit":"px"}]'
    sticky_col_close = ',"blockVisibility":{"controlSets":[{"id":1,"enable":true,"controls":{"screenSize":{"hideOnScreenSize":{"small":true}}}}]}}'

    return (
        f'<!-- wp:kadence/rowlayout {{"uniqueID":"{uid_row}","columnGutter":"wider","customGutter":[64,"",""],'
        f'"colLayout":"left-golden","firstColumnWidth":0,"secondColumnWidth":0,"thirdColumnWidth":0,'
        f'"fourthColumnWidth":0,"fifthColumnWidth":0,"sixthColumnWidth":0,"padding":["0","0",1,"0"],"kbVersion":2}} -->\n'
        f'<!-- wp:kadence/column {{"borderWidth":["","","",""],"borderRadius":[16,16,16,16],"uniqueID":"{uid_left}",'
        f'"padding":["0","0","0","0"],"borderStyle":{border_style},"kbVersion":2}} -->\n'
        f'<div class="wp-block-kadence-column kadence-column{uid_left}"><div class="kt-inside-inner-col">\n'
        f"{left_inner}"
        f"</div></div>\n<!-- /wp:kadence/column -->\n"
        f'<!-- wp:kadence/column {{"id":2,"borderWidth":["","","",""],"borderRadius":[16,16,16,16],"uniqueID":"{uid_right}",'
        f'"sticky":true,"stickyOffset":[32,"",""],"padding":["0","0","0","0"],"borderStyle":{border_style},'
        f'"kbVersion":2{sticky_col_close} -->\n'
        f'<div class="wp-block-kadence-column kadence-column{uid_right} kb-section-is-sticky"><div class="kt-inside-inner-col">'
        f"{right_inner}"
        f"</div></div>\n<!-- /wp:kadence/column -->\n"
        f"<!-- /wp:kadence/rowlayout -->\n"
    )


# ---------------------------------------------------------------------------
# Main markdown → blocks converter
# ---------------------------------------------------------------------------

def _md_to_blocks(markdown: str) -> str:
    """Convert markdown body to Gutenberg block HTML wrapped in Kadence rowlayout."""
    lines = markdown.splitlines()
    blocks: List[str] = []
    i = 0
    in_faq = False
    faq_items: List[Dict] = []
    faq_current_q: Optional[str] = None
    faq_current_a: List[str] = []

    def _flush_faq() -> None:
        nonlocal faq_items, faq_current_q, faq_current_a
        if faq_current_q and faq_current_a:
            faq_items.append({"question": faq_current_q, "answer": " ".join(faq_current_a).strip()})
        faq_current_q = None
        faq_current_a = []

    def _close_faq_section() -> None:
        nonlocal in_faq, faq_items
        _flush_faq()
        if faq_items:
            blocks.append(_block_faq_accordion(faq_items))
        in_faq = False
        faq_items = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # [NOTE: ...] — skip entirely
        if re.match(r"^\[NOTE:", stripped, re.IGNORECASE):
            i += 1
            continue

        # [DIAGRAM: description] — empty image block placeholder (not visible text in WP)
        m_diag = re.match(r"^\[DIAGRAM:\s*(.+)\]$", stripped, re.IGNORECASE)
        if m_diag:
            desc = _inline_md(m_diag.group(1).strip())
            blocks.append(
                f"<!-- wp:image -->\n"
                f'<figure class="wp-block-image"><img src="" alt="{desc}"/>'
                f'<figcaption class="wp-element-caption">{desc}</figcaption></figure>\n'
                f"<!-- /wp:image -->"
            )
            i += 1
            continue

        # Legacy diagram comment from pipeline injection — same treatment
        if stripped.startswith("<!-- DIAGRAM_NEEDED:"):
            m = re.search(r"<!-- DIAGRAM_NEEDED:\s*(.+?)-->", stripped)
            desc = _inline_md(m.group(1).strip()) if m else "Diagram"
            blocks.append(
                f"<!-- wp:image -->\n"
                f'<figure class="wp-block-image"><img src="" alt="{desc}"/>'
                f'<figcaption class="wp-element-caption">{desc}</figcaption></figure>\n'
                f"<!-- /wp:image -->"
            )
            i += 1
            continue

        # [DEFINITION: Title | Body]
        m_def = re.match(r"^\[DEFINITION:\s*(.+?)\s*\|\s*(.+)\]$", stripped, re.IGNORECASE)
        if m_def:
            if in_faq:
                _close_faq_section()
            blocks.append(_block_definition_box(m_def.group(1).strip(), _inline_md(m_def.group(2).strip())))
            i += 1
            continue

        # [CALLOUT: Title | Body]
        m_call = re.match(r"^\[CALLOUT:\s*(.+?)\s*\|\s*(.+)\]$", stripped, re.IGNORECASE)
        if m_call:
            if in_faq:
                _close_faq_section()
            blocks.append(_block_callout_box(m_call.group(1).strip(), _inline_md(m_call.group(2).strip())))
            i += 1
            continue

        # [FAQ] — enter FAQ mode
        if stripped == "[FAQ]":
            in_faq = True
            i += 1
            continue

        # While in FAQ mode: collect H3 + answer pairs
        if in_faq:
            if line.startswith("### "):
                _flush_faq()
                faq_current_q = line[4:].strip()
            elif line.startswith("## ") or line.startswith("# "):
                # New H2 closes the FAQ section
                _close_faq_section()
                # Fall through to process this heading normally (don't continue)
            elif stripped and faq_current_q is not None:
                faq_current_a.append(_inline_md(stripped))
                i += 1
                continue
            else:
                i += 1
                continue

            if in_faq:
                i += 1
                continue

        # Fenced code block
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            code_lines: List[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            code_content = _escape_code("\n".join(code_lines))
            blocks.append(
                f"<!-- wp:code -->\n"
                f'<pre class="wp-block-code"><code lang="{lang}" class="language-{lang}">'
                f"{code_content}</code></pre>\n<!-- /wp:code -->"
            )
            i += 1
            continue

        # H1 (skip — title set via post title field)
        if line.startswith("# "):
            i += 1
            continue

        # H2 — with top margin to match blog builder
        if line.startswith("## "):
            text = _inline_md(line[3:].strip())
            blocks.append(
                f'<!-- wp:heading {{"level":2,"style":{{"spacing":{{"margin":{{"top":"24px"}}}}}}}} -->\n'
                f'<h2 class="wp-block-heading" style="margin-top:24px">{text}</h2>\n'
                f"<!-- /wp:heading -->"
            )
            i += 1
            continue

        # H3
        if line.startswith("### "):
            text = _inline_md(line[4:].strip())
            blocks.append(
                f'<!-- wp:heading {{"level":3}} -->\n'
                f'<h3 class="wp-block-heading">{text}</h3>\n'
                f"<!-- /wp:heading -->"
            )
            i += 1
            continue

        # H4
        if line.startswith("#### "):
            text = _inline_md(line[5:].strip())
            blocks.append(
                f'<!-- wp:heading {{"level":4}} -->\n'
                f'<h4 class="wp-block-heading">{text}</h4>\n'
                f"<!-- /wp:heading -->"
            )
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

        # Table — use wide table treatment for 3+ columns
        if line.startswith("|"):
            table_lines: List[str] = []
            while i < len(lines) and lines[i].startswith("|"):
                table_lines.append(lines[i])
                i += 1
            rows = [r for r in table_lines if not re.match(r"^\|[-| :]+\|$", r.strip())]
            html_rows: List[str] = []
            for row in rows:
                cells = [c.strip() for c in row.strip("|").split("|")]
                html_rows.append(
                    "<tr>" + "".join(f"<td>{_inline_md(c)}</td>" for c in cells) + "</tr>"
                )
            table_html = f'<table><tbody>{"".join(html_rows)}</tbody></table>'
            blocks.append(_block_table(table_html))
            continue

        # Blank line — skip
        if not stripped:
            i += 1
            continue

        # Paragraph
        blocks.append(
            f"<!-- wp:paragraph -->\n<p>{_inline_md(stripped)}</p>\n<!-- /wp:paragraph -->"
        )
        i += 1

    # Flush any open FAQ section at end of document
    if in_faq:
        _close_faq_section()

    body_content = "\n\n".join(blocks)
    return _wrap_in_rowlayout(body_content)


# ---------------------------------------------------------------------------
# WP REST API helpers
# ---------------------------------------------------------------------------

async def _get_category_id(name: str) -> Optional[int]:
    if not name:
        return None
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
    """Look up a WordPress user ID by display name (core Author sidebar field)."""
    if not name:
        return None
    search = name.split(",")[0].strip()
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


async def _get_people_id(name: str) -> Optional[int]:
    """Look up a 'People' CPT post ID by name (ACF article_author relationship field)."""
    if not name:
        return None
    search = name.split(",")[0].strip()
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"{WP_BASE_URL}/wp-json/wp/v2/people",
            params={"search": search},
            headers=_auth(),
        )
    if r.status_code != 200:
        return None
    data = r.json()
    if isinstance(data, list) and data:
        return data[0]["id"]
    return None


async def _get_media_info_by_filename(filename: str) -> Tuple[Optional[int], Optional[str]]:
    """Look up a media item by filename. Returns (id, source_url)."""
    basename = filename.split("/")[-1]
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"{WP_BASE_URL}/wp-json/wp/v2/media",
            params={"search": basename, "media_type": "image", "per_page": 10},
            headers=_auth(),
        )
    if r.status_code != 200:
        return None, None
    data = r.json()
    if not isinstance(data, list):
        return None, None
    # Prefer exact basename match in source_url
    for item in data:
        source = item.get("source_url", "")
        if basename in source:
            return item["id"], source
    if data:
        return data[0]["id"], data[0].get("source_url")
    return None, None


async def _get_media_id_by_filename(filename: str) -> Optional[int]:
    """Convenience wrapper — returns just the media ID."""
    media_id, _ = await _get_media_info_by_filename(filename)
    return media_id


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
    social_image_url: Optional[str] = None,
) -> None:
    rm_meta = {}
    if seo_title:
        rm_meta["rank_math_title"] = seo_title
    if meta_description:
        rm_meta["rank_math_description"] = meta_description
    if focus_keyword:
        rm_meta["rank_math_focus_keyword"] = focus_keyword
    if social_image_url:
        rm_meta["rank_math_facebook_image"] = social_image_url
        rm_meta["rank_math_twitter_image"] = social_image_url
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


# ---------------------------------------------------------------------------
# Main publish function
# ---------------------------------------------------------------------------

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

    # block content is already wrapped in Kadence rowlayout with sticky TOC
    block_content = _md_to_blocks(content_md)

    import asyncio as _asyncio
    (
        category_id,
        author_id,
        people_id,
        hero_id,
        featured_id,
        socialcard_info,
        existing_id,
    ) = await _asyncio.gather(
        _get_category_id(category),
        _get_wp_user_id(_AUTHOR_NAME),
        _get_people_id(_AUTHOR_NAME),
        _get_media_id_by_filename(hero_filename),
        _get_media_id_by_filename(featured_filename),
        _get_media_info_by_filename(socialcard_filename),
        _find_existing_post(slug),
    )
    socialcard_id, socialcard_url = socialcard_info

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

    # ACF fields — full set matching the blog builder
    acf_fields: Dict = {
        "hero_title_color": "light",
        "subtitle": "",
        "related_resources_style": "none",
        "recommended_resources": [],
    }
    if hero_id:
        acf_fields["hero_image"] = hero_id
    if socialcard_id:
        acf_fields["social_card_image"] = socialcard_id
    if people_id:
        acf_fields["article_author"] = [people_id]

    async with httpx.AsyncClient(timeout=20) as client:
        r2 = await client.post(
            f"{WP_BASE_URL}/wp-json/wp/v2/posts/{post_id}",
            json={"acf": acf_fields},
            headers=_auth(),
        )
    if r2.status_code not in (200, 201):
        logger.warning("ACF update failed (%s): %s", r2.status_code, r2.text[:200])

    # RankMath SEO fields — include socialcard URL as OG/Twitter image
    await _set_rankmath_meta(post_id, seo_title, meta_description, focus_keyword, socialcard_url)

    edit_url = f"{WP_BASE_URL}/wp-admin/post.php?post={post_id}&action=edit"
    return post_id, edit_url
