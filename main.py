import os
import time
import hmac
import hashlib
import json
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from anthropic import Anthropic

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

# ----------------------------
# App + Logging
# ----------------------------
app = FastAPI()
logger = logging.getLogger("uvicorn.error")

# ----------------------------
# Env Vars
# ----------------------------
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_DEFAULT_CHANNEL = os.getenv("SLACK_DEFAULT_CHANNEL", "")  # e.g., C0AHY0FAN4C
BART_USER_ID = os.getenv("BART_USER_ID", "")  # e.g. U09RYUJDUQL

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-latest")

anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

SLACK_API_BASE = "https://slack.com/api"

# ----------------------------
# In-memory job state
# Keyed by thread_ts
# ----------------------------
JOBS: Dict[str, Dict[str, Any]] = {}

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
# Helpers
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
        "primary_cta": get_value("primary_cta_block", "primary_cta"),
        "intent": get_value("intent_block", "intent"),
        "primary_audience": get_value("primary_audience_block", "primary_audience"),
        "offer": get_value("offer_block", "offer"),
        "must_include": get_value("must_include_block", "must_include"),
        "must_not_say": get_value("must_not_say_block", "must_not_say"),
    }

def claude_text(prompt: str, max_tokens: int = 3500) -> str:
    if not anthropic_client:
        raise RuntimeError("Missing ANTHROPIC_API_KEY")

    msg = anthropic_client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}],
    )

    # Anthropic returns a list of content blocks; concatenate text blocks
    out = []
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            out.append(block.text)
    return "\n".join(out).strip()

def build_writer_prompt(fields: dict, bart_output: str) -> str:
    return f"""
You are the SEM Landing Page Writer.

Inputs:
- search_term: "{fields["search_term"]}"
- primary_cta: "{fields["primary_cta"]}"
- intent: "{fields["intent"]}"
- primary_audience: "{fields["primary_audience"]}"
- offer: "{fields.get("offer","")}"
- must_include: "{fields.get("must_include","")}"
- must_not_say: "{fields.get("must_not_say","")}"

BART_VALIDATED_OUTPUT:
{bart_output}

Rules:
- Only use claims that are validated in BART_VALIDATED_OUTPUT.
- search_term must appear in Title tag, H1, first 100 words, and at least one H2.
- CTA above the fold and repeated.
- Keep formatting scannable.

Return ONLY valid JSON with keys:
- "seo_json" (object: title_tag, meta_description, slug, h1)
- "outline_md" (string)
- "copy_md" (string)
- "image_briefs_md" (string)
- "qa_checklist_md" (string)
""".strip()

def bart_prompt(search_term: str, primary_cta: str, intent: str) -> str:
    return f"""<@{BART_USER_ID}> You are validating + drafting a technically accurate SEM landing page outline.

Context:
- Audience: Platform Engineer
- Search term (exact): "{search_term}"
- Primary CTA: {primary_cta}
- Intent: {intent}

TASK A — Codebase validation (required):
Validate any capabilities/claims you mention by checking the codebase.
Specifically:
1) List 8–12 “safe claims” we can make for this landing page topic.
2) For each claim, include:
   - Validation result: ✅ supported / ⚠️ unclear / ❌ not supported
   - Evidence: file path(s) + function/setting names, OR a short explanation if not found
3) If something is unclear, propose a safer alternative claim.

TASK B — Landing page outline (required):
Provide:
1) Recommended angle (2 sentences) tailored to a Platform Engineer.
2) H1 that includes the search term verbatim.
3) Section outline (H2s + bullets) including at least one H2 with the exact search term.
4) FAQs (3–6) tailored to Platform Engineers.

TASK C — Image generation (required):
Generate 1–2 visuals to explain the concepts for this landing page.
- Visual 1: a simple architecture diagram (preferred) that explains "{search_term}" in DataHub.
- Visual 2 (optional): a landing page layout wireframe showing section placement.
Upload the generated image(s) to this Slack thread and include a 1–2 sentence caption + suggested alt text for each.

Output order:
A) Validated claims table
B) Outline
C) FAQs
D) Visual captions + alt text

When you're fully done (claims validated + images uploaded), reply with exactly: BART_DONE
"""


# ----------------------------
# Claude stubs (wire later)
# ----------------------------
def build_html_prompt(fields: dict, writer_json: dict) -> str:
    return f"""
You are the HTML Builder. HTML is the LAST step.

Use this content exactly (do not invent claims):
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
- H1 must include the search_term verbatim: "{fields["search_term"]}"
- CTA appears above the fold and at the bottom.
- Add alt text based on IMAGE_BRIEFS_MD.

Return ONLY the HTML.
""".strip()

def build_html_prompt(fields: dict, writer_json: dict) -> str:
    return f"""
You are the HTML Builder. HTML is the LAST step.

Use this content exactly (do not invent claims):
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
- H1 must include the search_term verbatim: "{fields["search_term"]}"
- CTA appears above the fold and at the bottom.
- Add alt text based on IMAGE_BRIEFS_MD.

Return ONLY the HTML.
""".strip()

# ----------------------------
# Routes
# ----------------------------
@app.get("/health")
async def health():
    return {"ok": True}

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

    # ignore edits/bot subtypes
    if event.get("subtype"):
        return JSONResponse({"ok": True})

    thread_ts = event.get("thread_ts") or event.get("ts")
    user_id = event.get("user") or ""
    text = (event.get("text") or "").strip()

    job = JOBS.get(thread_ts)
    if not job:
        return JSONResponse({"ok": True})

    # Only treat as Bart response if from Bart AND includes completion token
    if job.get("awaiting") == "bart" and user_id == BART_USER_ID and "BART_DONE" in text:
        job["bart_output"] = text
        job["awaiting"] = "writer"
        JOBS[thread_ts] = job

        channel_id = job["channel_id"]
        request_id = job["request_id"]
        fields = job["fields"]

        async def continue_pipeline():
            try:
                writer_prompt = build_writer_prompt(fields, bart_output)
                writer_raw = claude_text(writer_prompt, max_tokens=3500)
                writer_json = json.loads(writer_raw)

                html_prompt = build_html_prompt(fields, writer_json)
                page_html = claude_text(html_prompt, max_tokens=3500)

                job["awaiting"] = "done"
                JOBS[thread_ts] = job
            except Exception as e:
                logger.exception("Pipeline continuation failed: %s", e)
                await post_message(channel_id, f"❌ Pipeline failed: `{e}`", thread_ts=thread_ts)

        asyncio.create_task(continue_pipeline())

    return JSONResponse({"ok": True})

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

# IMPORTANT: support both paths to avoid config mismatch
@app.post("/slack/interactions")
async def slack_interactions(request: Request):
    return await _handle_interactivity(request)

@app.post("/slack/interactivity")
async def slack_interactivity(request: Request):
    return await _handle_interactivity(request)

async def _handle_interactivity(request: Request):
    raw_body = await request.body()
    logger.info("INTERACTIVITY hit bytes=%s path=%s", len(raw_body), request.url.path)

    # Always respond quickly to Slack
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
        user_id = (payload.get("user") or {}).get("id") or "unknown"
        channel_id = (view.get("private_metadata") or "").strip() or SLACK_DEFAULT_CHANNEL or ""
        if not channel_id:
            return JSONResponse({"response_action": "clear"})

        async def run_pipeline():
            try:
                starter = (
                    f"🚀 *LP request started*\n"
                    f"*Request ID:* {request_id}\n"
                    f"*Search term:* {fields['search_term']}\n"
                    f"*Primary CTA:* {fields['primary_cta']}\n"
                    f"*Intent:* {fields['intent']}\n"
                    f"*Primary Audience:* {fields['primary_audience']}\n"
                    f"*Requester:* <@{user_id}>"
                )

                thread_ts = await post_message(channel_id, starter)

                JOBS[thread_ts] = {
                    "request_id": request_id,
                    "channel_id": channel_id,
                    "user_id": user_id,
                    "fields": fields,
                    "awaiting": "bart",
                    "bart_output": None,
                }

                await post_message(channel_id, "🧠 Step 1/3: asking Bart…", thread_ts=thread_ts)
                await post_message(
                    channel_id,
                    bart_prompt(fields["search_term"], fields["primary_cta"], fields["intent"]),
                    thread_ts=thread_ts,
                )
                await post_message(
                    channel_id,
                    "⏳ Waiting for Bart reply… I’ll continue automatically after Bart posts `BART_DONE`.",
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
