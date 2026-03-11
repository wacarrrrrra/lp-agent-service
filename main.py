import os
import time
import hmac
import hashlib
import json
import base64
import logging
import asyncio
import re
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

import httpx
from anthropic import Anthropic
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

# ----------------------------
# App + Logging
# ----------------------------
app = FastAPI()
logger = logging.getLogger("uvicorn.error")

# ----------------------------
# Env Vars — existing
# ----------------------------
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_DEFAULT_CHANNEL = os.getenv("SLACK_DEFAULT_CHANNEL", "")  # e.g. C0AHY0FAN4C
BART_USER_ID = os.getenv("BART_USER_ID", "")  # e.g. U09RYUJDUQL

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-latest")
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

SLACK_API_BASE = "https://slack.com/api"

# ----------------------------
# Env Vars — new
# ----------------------------
SEM_LP_BUILD_KITS_CHANNEL = os.getenv("SEM_LP_BUILD_KITS_CHANNEL", "")  # public results channel
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")   # e.g. wacarrrrrra/lp-agent-service
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")

# ----------------------------
# In-memory job state (v1)
# Keyed by thread_ts
# ----------------------------
JOBS: Dict[str, Dict[str, Any]] = {}

# ----------------------------
# Repo doc loading
# ----------------------------
def load_text(path: str, max_chars: int) -> str:
    try:
        txt = Path(path).read_text(encoding="utf-8")
        return txt[:max_chars]
    except Exception as e:
        logger.warning("Could not load %s: %s", path, e)
        return f"[Missing file: {path}]"

# Existing docs (keep for backward compatibility)
SEM_STRUCTURE = load_text("SEM-LP-Structure.md", 18000)
SEO_RULES = load_text("SEO-Best-Practices.md", 14000)
EDITORIAL_STYLE = load_text("datahub-editorial-style.md", 14000)
GARTNER_SNIPPETS = load_text("datahub-gartner-peer-insights.md", 9000)
BRAND_GUIDELINES = load_text("brand-guidelines.md", 14000)
HTML_TEMPLATE = load_text("datahub-observability-final.html", 20000)

# DataHub brand system docs (add these files to the lp-agent-service repo)
BRAND_SKILL_MD = load_text(".claude/skills/front-end-design/SKILL.md", 22000)
SAMPLE_LP_HTML = load_text("templates/datahub-governance-lp1.html", 28000)

# ----------------------------
# Slack signature verification
# ----------------------------
def verify_slack_signature(raw_body: bytes, timestamp: str, signature: str) -> None:
    if not SLACK_SIGNING_SECRET:
        raise HTTPException(status_code=500, detail="Missing SLACK_SIGNING_SECRET")

    if not timestamp or not signature:
        raise HTTPException(status_code=400, detail="Missing Slack signature headers")

    now = int(time.time())
    try:
        ts = int(timestamp)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid X-Slack-Request-Timestamp")

    if abs(now - ts) > 60 * 5:
        raise HTTPException(status_code=400, detail="Stale Slack request (possible replay)")

    basestring = f"v0:{timestamp}:".encode("utf-8") + raw_body
    expected = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode("utf-8"),
        basestring,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

# ----------------------------
# Slack helpers
# ----------------------------
async def slack_api(method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not SLACK_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Missing SLACK_BOT_TOKEN")

    url = f"{SLACK_API_BASE}/{method}"
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
            json=payload,
        )
    data = resp.json()
    if not data.get("ok"):
        raise HTTPException(status_code=500, detail=f"Slack API {method} failed: {data}")
    return data

async def post_message(channel: str, text: str, thread_ts: Optional[str] = None) -> str:
    payload: Dict[str, Any] = {"channel": channel, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    data = await slack_api("chat.postMessage", payload)
    return data.get("ts")

# ----------------------------
# General helpers
# ----------------------------
def generate_request_id() -> str:
    return datetime.now().strftime("LP-%Y%m%d-%H%M")

def slugify(text: str, max_len: int = 50) -> str:
    t = (text or "").strip().lower()
    t = "-".join(t.split())
    cleaned = []
    for ch in t:
        if ch.isalnum() or ch == "-":
            cleaned.append(ch)
    out = "".join(cleaned)
    return out[:max_len] if len(out) > max_len else out

def safe_truncate(s: str, n: int = 3500) -> str:
    return s if len(s) <= n else s[:n] + "\n...(truncated)"

def parse_secondary_keywords(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    raw = raw.replace(",", "\n")
    out: List[str] = []
    seen = set()
    for line in raw.splitlines():
        k = line.strip()
        if not k:
            continue
        lk = k.lower()
        if lk in seen:
            continue
        seen.add(lk)
        out.append(k)
    return out

# ----------------------------
# Thread accumulation (multi-part BartBot messages)
# ----------------------------
async def fetch_thread_messages(channel: str, thread_ts: str) -> List[Dict[str, Any]]:
    """Fetch all messages in a Slack thread."""
    try:
        data = await slack_api(
            "conversations.replies",
            {"channel": channel, "ts": thread_ts, "limit": 200},
        )
        return data.get("messages", [])
    except Exception as e:
        logger.warning("Could not fetch thread %s: %s", thread_ts, e)
        return []

def accumulate_bart_brief(messages: List[Dict[str, Any]], bart_user_id: str) -> str:
    """Join all BartBot messages from a thread into a single brief string."""
    parts = []
    for msg in messages:
        if msg.get("user") == bart_user_id:
            text = (msg.get("text") or "").strip()
            if text:
                parts.append(text)
    return "\n\n---\n\n".join(parts) if parts else ""

# ----------------------------
# Image reference parsing
# ----------------------------
def parse_image_refs(bart_brief: str) -> List[Dict[str, str]]:
    """
    Extract image references from a BartBot brief.
    Returns list of {filename, description, path} dicts.
    """
    images: List[Dict[str, str]] = []
    seen: set = set()

    # Markdown images: ![alt text](path/to/image.png)
    for alt, path in re.findall(
        r'!\[([^\]]*)\]\(([^)]+\.(?:png|jpg|jpeg))\)', bart_brief, re.IGNORECASE
    ):
        name = Path(path).name
        if name not in seen:
            seen.add(name)
            images.append({"filename": name, "description": alt, "path": path})

    # Bare filenames like datahub-foo.png
    for name in re.findall(r'\b([\w-]+\.png)\b', bart_brief, re.IGNORECASE):
        if name not in seen:
            seen.add(name)
            images.append({
                "filename": name,
                "description": name.replace("-", " ").replace(".png", ""),
                "path": f"images/{name}",
            })

    return images

# ----------------------------
# SVG generation
# ----------------------------
def build_svg_prompt(image_info: Dict[str, str], bart_brief: str, slug: str) -> str:
    fname = image_info["filename"].lower()
    if "workflow" in fname or "process" in fname or "policy" in fname:
        diagram_type = "Explainer (horizontal workflow)"
        viewbox = '0 0 960 540'
    elif "ui" in fname or "screenshot" in fname:
        diagram_type = "Stylized UI"
        viewbox = '0 0 960 680'
    else:
        diagram_type = "Explainer (architecture)"
        viewbox = '0 0 960 680'

    svg_name = image_info["filename"].replace(".png", ".svg")

    return f"""You are operating in SVG Conversion Mode from the DataHub brand system.

[DATAHUB BRAND SYSTEM]
{BRAND_SKILL_MD}

[SOURCE BRIEF — use this as the source of truth for diagram content]
{bart_brief[:6000]}

Task: Generate a brand-compliant DataHub SVG illustration for the following image.

Image reference:
- Original filename: {image_info["filename"]}
- Description: {image_info["description"]}
- Diagram type: {diagram_type}
- Output filename: {svg_name}
- Page slug: {slug}

SVG requirements (non-negotiable):
- Opening tag: <svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" role="img">
- Must include <title> and <desc> elements immediately after the opening tag
- Import Castoro + Geist from Google Fonts inside a <defs><style> block
- Brand colors only: #002131, #0A4170, #3CBBEB, #B0EAFC, #F2F1EE, #1E1E1E, #767473
- Minimum font-size attribute: 9 — no text below this value
- Flat tile-and-frame layout; no drop shadows, gradients, or glow
- Arrow markers using fill="#3CBBEB"
- Page background: <rect width="100%" height="100%" fill="#F2F1EE"/>

Run the SVG Conversion QA Checklist from the brand system before outputting.

Return ONLY the complete SVG markup — starting with <svg and ending with </svg>.
No code fences, no explanation, no preamble.
""".strip()

async def generate_svgs(bart_brief: str, slug: str) -> Dict[str, str]:
    """Generate brand-compliant SVGs for every image referenced in the brief."""
    image_refs = parse_image_refs(bart_brief)
    if not image_refs:
        return {}

    async def gen_one(img_info: Dict[str, str]) -> Tuple[str, str]:
        prompt = build_svg_prompt(img_info, bart_brief, slug)
        try:
            svg_content = await claude_text(prompt, max_tokens=4500)
            # Strip any accidental code fences
            match = re.search(r'<svg[\s\S]*?</svg>', svg_content, re.DOTALL)
            if match:
                svg_content = match.group(0)
            svg_name = img_info["filename"].replace(".png", ".svg")
            return svg_name, svg_content
        except Exception as e:
            logger.warning("SVG generation failed for %s: %s", img_info["filename"], e)
            return img_info["filename"].replace(".png", ".svg"), ""

    results = await asyncio.gather(*[gen_one(img) for img in image_refs])
    return {name: content for name, content in results if content}

# ----------------------------
# LP package generation
# ----------------------------
def _hubspot_form_id(cta_type: str) -> str:
    return {
        "Demo": "ed2447d6-e6f9-4771-8f77-825b114a9421",
        "Free Trial": "42182785-f711-40b4-92e7-11468579321b",
        "Bi-weekly Demo": "2bf16106-3e8e-4dc3-9ae4-5b0bce901d88",
        "Product Tour": "aa56e90c-044a-46d8-a92f-cb905ad662f8",
    }.get(cta_type, "ed2447d6-e6f9-4771-8f77-825b114a9421")

def build_lp_writer_prompt(
    fields: dict, bart_brief: str, secondary_keywords: List[str]
) -> str:
    secondary_block = (
        "\n".join(f"- {k}" for k in secondary_keywords) if secondary_keywords else "(none)"
    )
    form_id = _hubspot_form_id(fields.get("primary_cta", "Demo"))
    return f"""You are the SEM Landing Page Writer for DataHub.

HARD CONSTRAINTS — follow these documents exactly:

[SEM PAGE STRUCTURE]
{SEM_STRUCTURE}

[SEO BEST PRACTICES]
{SEO_RULES}

[EDITORIAL STYLE]
{EDITORIAL_STYLE}

[GARTNER PEER INSIGHTS — use sparingly, never fabricate]
{GARTNER_SNIPPETS}

Inputs:
- search_term (primary keyword, exact): "{fields["search_term"]}"
- secondary_keywords:
{secondary_block}
- primary_cta: "{fields.get("primary_cta","Demo")}"
- intent: "{fields.get("intent","Commercial")}"
- primary_audience: "{fields.get("primary_audience","")}"
- offer: "{fields.get("offer","")}"
- must_include: "{fields.get("must_include","")}"
- must_not_say: "{fields.get("must_not_say","")}"

BART_VALIDATED_OUTPUT — technical source of truth (only use claims from here):
{bart_brief[:8000]}

Rules:
- Page word count: 900–1,500 words
- Primary keyword must appear verbatim in: title tag (≤60 chars), H1 (≤80 chars, Title Case),
  first 100 words, meta description (≤140 chars), and at least one H2
- Each secondary keyword must appear in at least one H2/H3/H4
- 30–50% of H2s phrased as questions where natural
- Sentence case for all headings except H1
- No exclamation marks. Active voice. No weasel words — quantify or omit
- Never invent technical claims — only use facts from BART_VALIDATED_OUTPUT
- Required section order (10 sections):
  Hero → Trust Strip → Problem → Solution → How It Works →
  Technical Credibility → Visual → Social Proof → FAQ (3–6 Qs) → Final CTA
- HubSpot portal ID: 14552909, region: na1
- HubSpot form ID for "{fields.get("primary_cta","Demo")}": {form_id}

Return ONLY valid JSON with exactly these keys:
{{
  "seo_json": {{
    "title_tag": "",
    "meta_description": "",
    "slug": "",
    "h1": "",
    "hubspot_form_id": "{form_id}",
    "intent_type": "",
    "cta_type": ""
  }},
  "outline_md": "",
  "copy_md": "",
  "image_briefs_md": "",
  "qa_checklist_md": ""
}}""".strip()

def build_lp_html_prompt(
    fields: dict,
    writer_json: dict,
    svgs: Dict[str, str],
    secondary_keywords: List[str],
) -> str:
    secondary_block = (
        "\n".join(f"- {k}" for k in secondary_keywords) if secondary_keywords else "(none)"
    )

    picture_elements = ""
    for svg_name in svgs:
        png_name = svg_name.replace(".svg", ".png")
        picture_elements += (
            f'\n<picture>\n'
            f'  <source srcset="images/{svg_name}" type="image/svg+xml">\n'
            f'  <img src="images/{png_name}" alt="[descriptive alt text]" loading="lazy">\n'
            f'</picture>'
        )

    form_id = writer_json.get("seo_json", {}).get(
        "hubspot_form_id", _hubspot_form_id(fields.get("primary_cta", "Demo"))
    )

    return f"""You are the HTML Builder. This is the final build step.

HARD CONSTRAINTS — follow these documents exactly:

[DATAHUB BRAND SYSTEM]
{BRAND_SKILL_MD}

[SAMPLE LANDING PAGE TEMPLATE — replicate this structure and style]
{SAMPLE_LP_HTML}

Inputs:
- primary keyword: "{fields["search_term"]}"
- secondary keywords:
{secondary_block}

Content to use exactly (no new claims, no invented product assertions):

SEO_JSON:
{json.dumps(writer_json.get("seo_json", {}), indent=2)}

OUTLINE_MD:
{writer_json.get("outline_md", "")}

COPY_MD:
{writer_json.get("copy_md", "")}

IMAGE_BRIEFS_MD:
{writer_json.get("image_briefs_md", "")}

Available SVG images — use <picture> with SVG primary source and PNG fallback:
{picture_elements if picture_elements else "(none)"}

Non-negotiable design rules:
- Single complete HTML document: <!doctype html> … </html>
- Title tag and meta description verbatim from SEO_JSON
- H1 must include primary keyword verbatim: "{fields["search_term"]}"
- Header: background #F2F1EE, border-bottom 1px solid #DDDBD6
  Logo: <img src="images/dataHub_logo_color_black.svg" alt="DataHub"> — no text logo
- Hero: background #F2F1EE — never dark; all hero text in dark neutrals
- No italic text anywhere — font-style: normal throughout; no <em> or <i> tags
- Visual section: grid-template-columns: 1fr (stacked vertically, never side by side)
- HubSpot form embedded in hero AND final CTA section
  portalId: '14552909', formId: '{form_id}', region: 'na1'
- No global navigation — header contains only logo + one CTA button
- Full DataHub footer: 4 nav columns, social links (LinkedIn/GitHub/Twitter/Slack), legal bar
  matching the sample template footer exactly
- CSS variables only (--dh-*), Google Fonts Castoro + Geist — no system fonts, no Arial/Inter
- No invented metrics, logos, or social proof

Return ONLY the HTML — no code fences, no preamble, no explanation.
""".strip()

async def generate_full_lp(
    fields: dict,
    bart_brief: str,
    svgs: Dict[str, str],
    secondary_keywords: List[str],
) -> Dict[str, str]:
    """Two-stage LP generation: writer then HTML builder."""
    writer_prompt = build_lp_writer_prompt(fields, bart_brief, secondary_keywords)
    writer_raw = await claude_text(writer_prompt, max_tokens=4000)

    try:
        writer_json = json.loads(writer_raw)
    except Exception:
        match = re.search(r'\{[\s\S]*\}', writer_raw)
        if match:
            writer_json = json.loads(match.group(0))
        else:
            raise ValueError(f"Writer did not return valid JSON: {writer_raw[:500]}")

    html_prompt = build_lp_html_prompt(fields, writer_json, svgs, secondary_keywords)
    page_html = await claude_text(html_prompt, max_tokens=5000)

    # Strip accidental code fences from HTML
    html_match = re.search(r'<!doctype html[\s\S]*</html>', page_html, re.IGNORECASE | re.DOTALL)
    if html_match:
        page_html = html_match.group(0)

    # Build metadata.json
    seo = writer_json.get("seo_json", {})
    metadata = {
        "slug": seo.get("slug") or slugify(fields["search_term"]),
        "primary_search_term": fields["search_term"],
        "intent_type": seo.get("intent_type") or fields.get("intent", ""),
        "cta_type": seo.get("cta_type") or fields.get("primary_cta", ""),
        "hubspot_form_id": seo.get("hubspot_form_id") or _hubspot_form_id(fields.get("primary_cta", "Demo")),
        "title_tag": seo.get("title_tag") or "",
        "meta_description": seo.get("meta_description") or "",
        "h1": seo.get("h1") or "",
        "generated_date": datetime.now().strftime("%Y-%m-%d"),
        "bart_done": True,
    }

    return {
        "html": page_html,
        "metadata_json": json.dumps(metadata, indent=2),
        "writer_json": writer_json,
        "slug": metadata["slug"],
    }

# ----------------------------
# GitHub commit helpers
# ----------------------------
async def github_commit_file(
    repo: str, path: str, content: str, message: str, branch: str
) -> bool:
    """Commit a single file to GitHub via the Contents API."""
    if not GITHUB_TOKEN or not repo:
        logger.warning("GitHub commit skipped — GITHUB_TOKEN or GITHUB_REPO not set")
        return False

    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        # Get existing file SHA (needed for updates)
        r = await client.get(url, headers=headers, params={"ref": branch})
        sha = r.json().get("sha") if r.status_code == 200 else None

        payload: Dict[str, Any] = {
            "message": message,
            "content": encoded,
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha

        resp = await client.put(url, headers=headers, json=payload)
        if resp.status_code not in (200, 201):
            logger.error("GitHub commit failed for %s: %s %s", path, resp.status_code, resp.text[:300])
            return False
        return True

async def github_commit_files(
    repo: str,
    files: Dict[str, str],
    commit_message: str,
    branch: str,
) -> Tuple[bool, List[str]]:
    """Commit multiple files sequentially. Returns (all_succeeded, failed_paths)."""
    failed: List[str] = []
    for path, content in files.items():
        ok = await github_commit_file(repo, path, content, commit_message, branch)
        if not ok:
            failed.append(path)
    return (len(failed) == 0, failed)

# ----------------------------
# Modal helpers
# ----------------------------
def build_modal_view(initial_search_term: str = "", channel_id: str = "") -> Dict[str, Any]:
    return {
        "type": "modal",
        "callback_id": "lp_request_modal",
        "private_metadata": channel_id or "",
        "title": {"type": "plain_text", "text": "SEM LP Request"},
        "submit": {"type": "plain_text", "text": "Create"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "search_term_block",
                "label": {"type": "plain_text", "text": "Search term (exact)"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "search_term",
                    "initial_value": initial_search_term or "",
                    "placeholder": {"type": "plain_text", "text": "e.g., datahub lineage"},
                },
            },
            {
                "type": "input",
                "optional": True,
                "block_id": "secondary_keywords_block",
                "label": {"type": "plain_text", "text": "Secondary keywords (optional)"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "secondary_keywords",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "One per line (or comma-separated)\nExample:\nmetadata management\ncolumn-level lineage\ndata observability",
                    },
                },
            },
            {
                "type": "input",
                "block_id": "primary_cta_block",
                "label": {"type": "plain_text", "text": "Primary CTA"},
                "element": {
                    "type": "static_select",
                    "action_id": "primary_cta",
                    "options": [
                        {"text": {"type": "plain_text", "text": "Demo"}, "value": "Demo"},
                        {"text": {"type": "plain_text", "text": "Free Trial"}, "value": "Free Trial"},
                        {"text": {"type": "plain_text", "text": "Product Tour"}, "value": "Product Tour"},
                        {"text": {"type": "plain_text", "text": "Bi-weekly Demo"}, "value": "Bi-weekly Demo"},
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "intent_block",
                "label": {"type": "plain_text", "text": "Intent (required)"},
                "element": {
                    "type": "static_select",
                    "action_id": "intent",
                    "options": [
                        {"text": {"type": "plain_text", "text": "Commercial"}, "value": "Commercial"},
                        {"text": {"type": "plain_text", "text": "Educational"}, "value": "Educational"},
                        {"text": {"type": "plain_text", "text": "Transactional"}, "value": "Transactional"},
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "primary_audience_block",
                "label": {"type": "plain_text", "text": "Primary Audience (required)"},
                "element": {
                    "type": "static_select",
                    "action_id": "primary_audience",
                    "options": [
                        {"text": {"type": "plain_text", "text": "Economic Buyer"}, "value": "Economic Buyer"},
                        {"text": {"type": "plain_text", "text": "Platform Engineer"}, "value": "Platform Engineer"},
                    ],
                },
            },
            {
                "type": "input",
                "optional": True,
                "block_id": "offer_block",
                "label": {"type": "plain_text", "text": "Offer (optional)"},
                "element": {"type": "plain_text_input", "action_id": "offer", "multiline": True},
            },
            {
                "type": "input",
                "optional": True,
                "block_id": "must_include_block",
                "label": {"type": "plain_text", "text": "Must include (optional)"},
                "element": {"type": "plain_text_input", "action_id": "must_include", "multiline": True},
            },
            {
                "type": "input",
                "optional": True,
                "block_id": "must_not_say_block",
                "label": {"type": "plain_text", "text": "Must not say (optional)"},
                "element": {"type": "plain_text_input", "action_id": "must_not_say", "multiline": True},
            },
        ],
    }

def extract_modal_values(view_state: Dict[str, Any]) -> Dict[str, Any]:
    values = view_state.get("values", {})

    def get_value(block_id: str, action_id: str) -> Optional[str]:
        block = values.get(block_id, {})
        action = block.get(action_id, {})
        if "value" in action:
            return action.get("value")
        selected = action.get("selected_option")
        if selected:
            return selected.get("value")
        return None

    return {
        "search_term": get_value("search_term_block", "search_term"),
        "secondary_keywords": get_value("secondary_keywords_block", "secondary_keywords"),
        "primary_cta": get_value("primary_cta_block", "primary_cta"),
        "intent": get_value("intent_block", "intent"),
        "primary_audience": get_value("primary_audience_block", "primary_audience"),
        "offer": get_value("offer_block", "offer"),
        "must_include": get_value("must_include_block", "must_include"),
        "must_not_say": get_value("must_not_say_block", "must_not_say"),
    }

# ----------------------------
# Bart prompt
# ----------------------------
def bart_prompt(search_term: str, primary_cta: str, intent: str, secondary_keywords: List[str]) -> str:
    secondary = "\n".join(f"- {k}" for k in secondary_keywords) if secondary_keywords else "(none)"
    return f"""<@{BART_USER_ID}> You are validating + drafting a technically accurate SEM landing page outline.

Context:
- Audience: Platform Engineer
- Search term (exact): "{search_term}"
- Secondary keywords (optional):
{secondary}
- Primary CTA: {primary_cta}
- Intent: {intent}

TASK A — Codebase validation (required):
Validate any capabilities/claims you mention by checking the codebase.
For each claim include: ✅/⚠️/❌ + evidence (file paths/settings).

TASK B — Landing page outline (required):
Angle (2 sentences), H1 w/ exact search term, H2/H3/H4 outline + bullets, 3–6 FAQs.

TASK C — Image generation (required):
Generate 1–2 visuals (diagram preferred). Upload images to this thread with captions + alt text.

When you're fully done (claims validated + images uploaded), reply with exactly: BART_DONE
"""

# ----------------------------
# Claude helpers
# ----------------------------
def claude_text_sync(prompt: str, max_tokens: int = 3500) -> str:
    if not anthropic_client:
        raise RuntimeError("Missing ANTHROPIC_API_KEY")

    msg = anthropic_client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}],
    )

    parts = []
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(parts).strip()

async def claude_text(prompt: str, max_tokens: int = 3500) -> str:
    return await asyncio.to_thread(claude_text_sync, prompt, max_tokens)

# ----------------------------
# Legacy writer/HTML prompts (kept for reference)
# ----------------------------
def build_writer_prompt(fields: dict, bart_output: str, secondary_keywords: List[str]) -> str:
    secondary_block = "\n".join(f"- {k}" for k in secondary_keywords) if secondary_keywords else "(none)"
    return f"""
You are the SEM Landing Page Writer.

HARD CONSTRAINTS — follow these documents exactly:
[SEM STRUCTURE]
{SEM_STRUCTURE}

[SEO BEST PRACTICES]
{SEO_RULES}

[EDITORIAL STYLE]
{EDITORIAL_STYLE}

[OPTIONAL GARTNER PEER INSIGHTS SNIPPETS — use sparingly and never fabricate]
{GARTNER_SNIPPETS}

Inputs:
- search_term (primary keyword): "{fields["search_term"]}"
- secondary_keywords (optional):
{secondary_block}
- primary_cta: "{fields["primary_cta"]}"
- intent: "{fields["intent"]}"
- primary_audience: "{fields["primary_audience"]}"
- offer: "{fields.get("offer","")}"
- must_include: "{fields.get("must_include","")}"
- must_not_say: "{fields.get("must_not_say","")}"

BART_VALIDATED_OUTPUT (technical source of truth):
{bart_output}

Rules:
- Only use claims validated in BART_VALIDATED_OUTPUT.
- Primary keyword must appear in Title tag, H1, first 100 words, and at least one H2.
- Each secondary keyword MUST appear in at least one heading (H2, H3, or H4).
- CTA above the fold and repeated near the bottom.
- Scannable formatting, short paragraphs + bullets.

Return ONLY valid JSON with keys:
- "seo_json" (object: title_tag, meta_description, slug, h1)
- "outline_md" (string)
- "copy_md" (string)
- "image_briefs_md" (string)
- "qa_checklist_md" (string)
""".strip()

def build_html_prompt(fields: dict, writer_json: dict, secondary_keywords: List[str]) -> str:
    secondary_block = "\n".join(f"- {k}" for k in secondary_keywords) if secondary_keywords else "(none)"
    return f"""
You are the HTML Builder. HTML is the LAST step.

HARD CONSTRAINTS — follow these documents exactly:
[BRAND GUIDELINES]
{BRAND_GUIDELINES}

[HTML TEMPLATE TO REPLICATE (structure + section order)]
{HTML_TEMPLATE}

Inputs:
- primary keyword: "{fields["search_term"]}"
- secondary keywords:
{secondary_block}

Use this content exactly (no new claims, no new product assertions):
SEO_JSON:
{json.dumps(writer_json["seo_json"], indent=2)}

OUTLINE_MD:
{writer_json["outline_md"]}

COPY_MD:
{writer_json["copy_md"]}

IMAGE_BRIEFS_MD:
{writer_json["image_briefs_md"]}

Requirements:
- Output a single complete semantic HTML document (<!doctype html> ...).
- Title/meta from SEO_JSON.
- H1 must include the primary keyword verbatim: "{fields["search_term"]}"
- CTA appears above the fold and at the bottom.
- Add alt text based on IMAGE_BRIEFS_MD.
- Preserve template structure, but swap content with the provided copy.

Return ONLY the HTML.
""".strip()

# ----------------------------
# Routes
# ----------------------------
@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/anthropic/models")
async def anthropic_models():
    if not ANTHROPIC_API_KEY:
        return {"ok": False, "error": "Missing ANTHROPIC_API_KEY"}

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get("https://api.anthropic.com/v1/models", headers=headers)
        return {"status_code": r.status_code, "json": r.json()}

@app.post("/slack/commands")
async def slack_commands(request: Request):
    raw_body = await request.body()
    verify_slack_signature(
        raw_body,
        request.headers.get("X-Slack-Request-Timestamp", ""),
        request.headers.get("X-Slack-Signature", ""),
    )

    form = await request.form()
    command = form.get("command")
    trigger_id = form.get("trigger_id")
    text = (form.get("text") or "").strip()
    channel_id = form.get("channel_id") or ""

    if command != "/sem-lp-request":
        return PlainTextResponse("Unsupported command.", status_code=200)

    view = build_modal_view(initial_search_term=text, channel_id=channel_id)
    await slack_api("views.open", {"trigger_id": trigger_id, "view": view})
    return PlainTextResponse("", status_code=200)

# Support both URLs to avoid config mismatch
@app.post("/slack/interactions")
async def slack_interactions(request: Request):
    return await _handle_interactivity(request)

@app.post("/slack/interactivity")
async def slack_interactivity(request: Request):
    return await _handle_interactivity(request)

async def _handle_interactivity(request: Request):
    raw_body = await request.body()
    logger.info("INTERACTIVITY hit bytes=%s path=%s", len(raw_body), request.url.path)

    try:
        verify_slack_signature(
            raw_body,
            request.headers.get("X-Slack-Request-Timestamp", ""),
            request.headers.get("X-Slack-Signature", ""),
        )

        form = await request.form()
        payload_raw = form.get("payload")
        if not payload_raw:
            return JSONResponse({"ok": True})

        payload = json.loads(payload_raw)
        if payload.get("type") != "view_submission":
            return JSONResponse({"ok": True})

        view = payload.get("view", {})
        if view.get("callback_id") != "lp_request_modal":
            return JSONResponse({"response_action": "clear"})

        fields = extract_modal_values(view.get("state", {}))

        errors = {}
        if not fields.get("search_term"):
            errors["search_term_block"] = "Search term is required."
        if not fields.get("primary_cta"):
            errors["primary_cta_block"] = "Primary CTA is required."
        if not fields.get("intent"):
            errors["intent_block"] = "Intent is required."
        if not fields.get("primary_audience"):
            errors["primary_audience_block"] = "Primary Audience is required."
        if errors:
            return JSONResponse({"response_action": "errors", "errors": errors})

        request_id = generate_request_id()
        slug = slugify(fields["search_term"])
        user_id = (payload.get("user") or {}).get("id") or "unknown"
        channel_id = (view.get("private_metadata") or "").strip() or SLACK_DEFAULT_CHANNEL or ""
        if not channel_id:
            return JSONResponse({"response_action": "clear"})

        secondary_keywords = parse_secondary_keywords(fields.get("secondary_keywords"))

        async def run_pipeline():
            try:
                starter = (
                    f"🚀 *LP request started*\n"
                    f"*Request ID:* {request_id}\n"
                    f"*Search term:* {fields['search_term']}\n"
                    f"*Secondary keywords:* {', '.join(secondary_keywords) if secondary_keywords else '—'}\n"
                    f"*Primary CTA:* {fields['primary_cta']}\n"
                    f"*Intent:* {fields['intent']}\n"
                    f"*Primary Audience:* {fields['primary_audience']}\n"
                    f"*Requester:* <@{user_id}>"
                )

                thread_ts = await post_message(channel_id, starter)

                JOBS[thread_ts] = {
                    "request_id": request_id,
                    "slug": slug,
                    "channel_id": channel_id,
                    "user_id": user_id,
                    "fields": fields,
                    "secondary_keywords": secondary_keywords,
                    "awaiting": "bart",
                    "bart_output": None,
                }

                await post_message(channel_id, "🧠 Step 1/4: Asking Bart…", thread_ts=thread_ts)
                await post_message(
                    channel_id,
                    bart_prompt(fields["search_term"], fields["primary_cta"], fields["intent"], secondary_keywords),
                    thread_ts=thread_ts,
                )
                await post_message(
                    channel_id,
                    "⏳ Waiting for Bart… I'll continue automatically after Bart posts `BART_DONE`.",
                    thread_ts=thread_ts,
                )

            except Exception as e:
                logger.exception("run_pipeline failed: %s", e)
                try:
                    await post_message(channel_id, f"❌ Pipeline failed to start: `{e}`")
                except Exception:
                    pass

        asyncio.create_task(run_pipeline())
        return JSONResponse({"response_action": "clear"})

    except Exception as e:
        logger.exception("Interactivity handler error: %s", e)
        return JSONResponse({"response_action": "clear"})

@app.post("/slack/events")
async def slack_events(request: Request):
    raw_body = await request.body()
    verify_slack_signature(
        raw_body,
        request.headers.get("X-Slack-Request-Timestamp", ""),
        request.headers.get("X-Slack-Signature", ""),
    )
    body = json.loads(raw_body.decode("utf-8") or "{}")

    if body.get("type") == "url_verification":
        return JSONResponse({"challenge": body.get("challenge")})

    event = body.get("event", {}) or {}
    if event.get("type") != "message":
        return JSONResponse({"ok": True})

    if event.get("subtype"):
        return JSONResponse({"ok": True})

    thread_ts = event.get("thread_ts") or event.get("ts")
    user_id = event.get("user") or ""
    text = (event.get("text") or "").strip()

    job = JOBS.get(thread_ts)
    if not job:
        return JSONResponse({"ok": True})

    # Only proceed if waiting for Bart AND it's Bart AND it contains BART_DONE
    if job.get("awaiting") == "bart" and user_id == BART_USER_ID and "BART_DONE" in text:
        job["bart_output"] = text
        job["awaiting"] = "generating"
        JOBS[thread_ts] = job

        channel_id = job["channel_id"]
        request_id = job["request_id"]
        fields = job["fields"]
        slug = job["slug"]
        secondary_keywords = job.get("secondary_keywords", [])

        async def continue_pipeline():
            try:
                # Step 1 — Fetch full thread to accumulate multi-part BartBot brief
                await post_message(
                    channel_id, "📖 Step 2/4: Collecting full brief from thread…", thread_ts=thread_ts
                )
                messages = await fetch_thread_messages(channel_id, thread_ts)
                bart_brief = accumulate_bart_brief(messages, BART_USER_ID)
                if not bart_brief:
                    bart_brief = text  # fallback: use the BART_DONE message itself

                # Step 2 — Generate brand-compliant SVGs for each image in the brief
                image_refs = parse_image_refs(bart_brief)
                svgs: Dict[str, str] = {}
                if image_refs:
                    await post_message(
                        channel_id,
                        f"🎨 Step 3/4: Generating {len(image_refs)} brand-compliant SVG(s)…",
                        thread_ts=thread_ts,
                    )
                    svgs = await generate_svgs(bart_brief, slug)

                # Step 3 — Generate full LP package (writer → HTML builder)
                await post_message(
                    channel_id, "✍️ Step 4/4: Building landing page package…", thread_ts=thread_ts
                )
                lp_package = await generate_full_lp(fields, bart_brief, svgs, secondary_keywords)
                final_slug = lp_package["slug"]

                # Step 4 — Commit all files to GitHub
                files_to_commit: Dict[str, str] = {
                    f"generated-pages/{final_slug}/index.html": lp_package["html"],
                    f"generated-pages/{final_slug}/metadata.json": lp_package["metadata_json"],
                    f"generated-pages/{final_slug}/brief.md": bart_brief,
                }
                for svg_name, svg_content in svgs.items():
                    files_to_commit[f"generated-pages/{final_slug}/images/{svg_name}"] = svg_content

                if GITHUB_TOKEN and GITHUB_REPO:
                    await post_message(
                        channel_id, "📤 Committing files to GitHub…", thread_ts=thread_ts
                    )
                    all_ok, failed_paths = await github_commit_files(
                        GITHUB_REPO,
                        files_to_commit,
                        f"Add LP package: {final_slug}",
                        GITHUB_BRANCH,
                    )
                    kit_url = (
                        f"https://github.com/{GITHUB_REPO}/tree/{GITHUB_BRANCH}"
                        f"/generated-pages/{final_slug}"
                    )
                    if all_ok:
                        status_msg = f"✅ *LP package ready* — `{final_slug}`\n{kit_url}"
                    else:
                        status_msg = (
                            f"⚠️ *LP generated* — `{final_slug}` — some files failed to commit:\n"
                            + "\n".join(f"• `{p}`" for p in failed_paths)
                        )
                else:
                    kit_url = "(GitHub not configured — set GITHUB_TOKEN and GITHUB_REPO)"
                    status_msg = (
                        f"✅ *LP package generated* — `{final_slug}`\n"
                        f"_(GitHub commit skipped — env vars not set)_"
                    )

                # Confirmation in the original thread
                await post_message(channel_id, status_msg, thread_ts=thread_ts)

                # Announce in #sem-lp-build-kits
                if SEM_LP_BUILD_KITS_CHANNEL:
                    metadata = json.loads(lp_package["metadata_json"])
                    kits_msg = (
                        f"🚀 *New LP package ready*\n"
                        f"*Search term:* {fields['search_term']}\n"
                        f"*Slug:* `{final_slug}`\n"
                        f"*CTA:* {fields.get('primary_cta','Demo')} | "
                        f"*Intent:* {fields.get('intent','Commercial')}\n"
                        f"*Files:* {kit_url}"
                    )
                    await post_message(SEM_LP_BUILD_KITS_CHANNEL, kits_msg)

                job["awaiting"] = "done"
                JOBS[thread_ts] = job

            except Exception as e:
                logger.exception("Pipeline continuation failed: %s", e)
                try:
                    await post_message(
                        channel_id, f"❌ Pipeline failed: `{e}`", thread_ts=thread_ts
                    )
                except Exception:
                    pass
                job["awaiting"] = "error"
                JOBS[thread_ts] = job

        asyncio.create_task(continue_pipeline())

    return JSONResponse({"ok": True})
