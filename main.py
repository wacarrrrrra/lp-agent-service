import os
import time
import hmac
import hashlib
import json
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any

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

# Optional: lock Bart identification down to a known Slack user ID (recommended)
# Find it by right-clicking Bart in Slack -> View profile -> Copy member ID
BART_USER_ID = os.getenv("BART_USER_ID", "")  # e.g. U123ABC...

SLACK_API_BASE = "https://slack.com/api"

# ----------------------------
# In-memory state (v1)
# For production: swap to Redis / DB
# ----------------------------
# Keyed by thread_ts
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
    # Intent + Primary Audience REQUIRED per your update
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
            # REQUIRED: Intent
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
            # REQUIRED: Primary Audience
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
            # Optional fields
            {
                "type": "input",
                "optional": True,
                "block_id": "offer_block",
                "label": {"type": "plain_text", "text": "Offer (optional)"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "offer",
                    "multiline": True,
                },
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

def bart_prompt(search_term: str) -> str:
    return (
        f'@bartbot Draft a technically accurate landing page outline for the exact search term: "{search_term}".\n\n'
        "Output format:\n"
        "1) Recommended angle (2 sentences)\n"
        "2) H1 that includes the search term verbatim\n"
        "3) Section outline (H2s + bullets)\n"
        "4) Claims we can safely make + supporting product facts (no speculation)\n"
        "5) FAQs\n"
        "6) Visual plan (what visual, what it explains, placement)\n"
    )

# ----------------------------
# Claude stubs (wire later)
# ----------------------------
async def claude_writer(fields: Dict[str, Any], bart_output: str) -> Dict[str, str]:
    """
    Replace this with:
    - Claude Desktop automation
    - Claude MCP tool call
    - or API call later
    Return: {"outline_md": "...", "copy_md": "..."}
    """
    # For now, keep it deterministic and transparent:
    outline_md = f"# Outline\n\n(Based on Bart)\n\n{bart_output}\n"
    copy_md = (
        f"# Copy Draft\n\n"
        f"## Hero\n"
        f"**H1:** {fields['search_term']}\n\n"
        f"Primary CTA: {fields['primary_cta']}\n\n"
        f"(Replace with Claude Writer output)\n"
    )
    return {"outline_md": outline_md, "copy_md": copy_md}

async def claude_html_builder(fields: Dict[str, Any], outline_md: str, copy_md: str) -> str:
    """
    Replace this with Claude HTML Builder using:
    - your uploaded sample HTML template
    - your brand guide constraints
    HTML should be LAST.
    """
    title = fields["search_term"]
    meta = f"Learn how DataHub supports {fields['search_term']}."
    cta = fields["primary_cta"]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{title}</title>
  <meta name="description" content="{meta}" />
</head>
<body>
  <!-- Request -->
  <main>
    <section id="hero">
      <h1>{fields["search_term"]}</h1>
      <p><strong>Intent:</strong> {fields["intent"]} | <strong>Primary Audience:</strong> {fields["primary_audience"]}</p>
      <a href="#cta">{cta}</a>
    </section>

    <section id="outline">
      <h2>Outline (from Bart/Writer)</h2>
      <pre>{outline_md[:1500]}</pre>
    </section>

    <section id="copy">
      <h2>Copy (from Writer)</h2>
      <pre>{copy_md[:1500]}</pre>
    </section>

    <section id="cta">
      <h2>Next step</h2>
      <p>Repeat CTA and clarify what happens after click.</p>
      <a href="#">{cta}</a>
    </section>
  </main>
</body>
</html>"""

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

    # URL verification
    if body.get("type") == "url_verification":
        return JSONResponse({"challenge": body.get("challenge")})

    event = body.get("event", {})
    event_type = event.get("type")

    # Handle Bart replies in-thread (message events)
    if event_type == "message":
        thread_ts = event.get("thread_ts") or event.get("ts")
        user_id = event.get("user")  # for bot messages may differ
        bot_id = event.get("bot_id")  # present when it's a bot message
        text = event.get("text") or ""

        # Only proceed if we have a job for this thread
        job = JOBS.get(thread_ts)
        if not job:
            return JSONResponse({"ok": True})

        # Identify Bart response:
        # Best: compare user_id to BART_USER_ID
        # Fallback: if message includes typical Bart structure or is bot message and we asked Bart.
        is_bart = False
        if BART_USER_ID and user_id == BART_USER_ID:
            is_bart = True
        elif job.get("awaiting") == "bart" and (bot_id or "Recommended angle" in text):
            is_bart = True

        if is_bart and job.get("awaiting") == "bart":
            job["bart_output"] = text
            job["awaiting"] = "writer"
            JOBS[thread_ts] = job

            channel_id = job["channel_id"]
            request_id = job["request_id"]
            fields = job["fields"]

            async def continue_pipeline():
                try:
                    await post_message(channel_id, "✍️ Running Writer step (Claude) using Bart output…", thread_ts=thread_ts)
                    writer_out = await claude_writer(fields, text)

                    await post_message(channel_id, "🧱 Running HTML Builder step (Claude) LAST…", thread_ts=thread_ts)
                    html = await claude_html_builder(fields, writer_out["outline_md"], writer_out["copy_md"])

                    # Post HTML last
                    max_len = 3500
                    chunk = html if len(html) <= max_len else html[:max_len] + "\n...(truncated)"
                    await post_message(channel_id, f"✅ *Final HTML for {request_id}*\n```{chunk}```", thread_ts=thread_ts)

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

    if not trigger_id:
        return PlainTextResponse("Missing trigger_id.", status_code=200)

    view = build_modal_view(initial_search_term=text, channel_id=channel_id)

    # Open modal
    await slack_api("views.open", {"trigger_id": trigger_id, "view": view})
    return PlainTextResponse("", status_code=200)

# IMPORTANT: match Slack's Interactivity URL.
# Your logs showed Slack calling /slack/interactivity
@app.post("/slack/interactions")
async def slack_interactivity(request: Request):
    raw_body = await request.body()
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
    payload_type = payload.get("type")

    if payload_type == "view_submission":
        view = payload.get("view", {})
        if view.get("callback_id") != "lp_request_modal":
            return JSONResponse({"response_action": "clear"})

        fields = extract_modal_values(view.get("state", {}))

        # Required fields
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
        _slug = slugify(fields["search_term"])

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

                # Store job state
                JOBS[thread_ts] = {
                    "request_id": request_id,
                    "channel_id": channel_id,
                    "user_id": user_id,
                    "fields": fields,
                    "awaiting": "bart",
                    "bart_output": None,
                }

                await post_message(channel_id, "🧠 Step 1/3: asking Bart for technical outline + claims + visuals…", thread_ts=thread_ts)
                await post_message(channel_id, bart_prompt(fields["search_term"]), thread_ts=thread_ts)

                await post_message(
                    channel_id,
                    "⏳ Waiting for Bart reply… then I’ll run Writer (Claude) → HTML Builder (Claude) with HTML as the LAST step.",
                    thread_ts=thread_ts,
                )
            except Exception as e:
                logger.exception("run_pipeline failed: %s", e)
                # Try to notify in the channel if possible
                try:
                    await post_message(channel_id, f"❌ Pipeline failed to start: `{e}`")
                except Exception:
                    pass

        asyncio.create_task(run_pipeline())

        # Close modal immediately (<3s)
        return JSONResponse({"response_action": "clear"})

    return JSONResponse({"ok": True})
