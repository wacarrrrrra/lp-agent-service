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
SLACK_DEFAULT_CHANNEL = os.getenv("SLACK_DEFAULT_CHANNEL", "")  # channel ID like C123..., optional

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-latest")

SLACK_API_BASE = "https://slack.com/api"


# ----------------------------
# Slack signature verification
# ----------------------------
def verify_slack_signature(raw_body: bytes, timestamp: str, signature: str) -> None:
    if not SLACK_SIGNING_SECRET:
        raise HTTPException(status_code=500, detail="Missing SLACK_SIGNING_SECRET")

    if not timestamp or not signature:
        raise HTTPException(status_code=400, detail="Missing Slack signature headers")

    # Prevent replay attacks (5-minute window)
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
    t = "-".join(t.split())  # spaces -> hyphens
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
    async with httpx.AsyncClient(timeout=15) as client:
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
    # store channel_id in private_metadata so modal submit knows where to post
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
                    "placeholder": {"type": "plain_text", "text": "e.g., datahub architecture"},
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
                "optional": True,
                "block_id": "intent_block",
                "label": {"type": "plain_text", "text": "Intent (optional)"},
                "element": {
                    "type": "static_select",
                    "action_id": "intent",
                    "options": [
                        {"text": {"type": "plain_text", "text": "Commercial"}, "value": "Commercial"},
                        {"text": {"type": "plain_text", "text": "OSS / Developer"}, "value": "OSS"},
                        {"text": {"type": "plain_text", "text": "Enterprise"}, "value": "Enterprise"},
                    ],
                },
            },
            {
                "type": "input",
                "optional": True,
                "block_id": "persona_block",
                "label": {"type": "plain_text", "text": "Audience persona (optional)"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "audience_persona",
                    "placeholder": {"type": "plain_text", "text": "e.g., Platform Engineer"},
                },
            },
            {
                "type": "input",
                "optional": True,
                "block_id": "offer_block",
                "label": {"type": "plain_text", "text": "Offer (optional)"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "offer",
                    "multiline": True,
                    "placeholder": {"type": "plain_text", "text": "e.g., Interactive Product Tour..."},
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
        "audience_persona": get_value("persona_block", "audience_persona"),
        "offer": get_value("offer_block", "offer"),
        "must_include": get_value("must_include_block", "must_include"),
        "must_not_say": get_value("must_not_say_block", "must_not_say"),
    }


async def call_claude(prompt: str) -> str:
    if not ANTHROPIC_API_KEY:
        return "⚠️ Claude integration not configured (missing ANTHROPIC_API_KEY)."

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": CLAUDE_MODEL,
        "max_tokens": 900,
        "messages": [{"role": "user", "content": prompt}],
    }

    async with httpx.AsyncClient(timeout=45) as client:
        resp = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    parts = data.get("content", [])
    out = ""
    for p in parts:
        if p.get("type") == "text":
            out += p.get("text", "")
    return out.strip() or "(No text returned from Claude.)"


def build_claude_prompt(fields: Dict[str, Any], request_id: str) -> str:
    return f"""
You are the SEM Landing Page Agent.

Create a technically credible landing page outline + first-draft copy for:
Search term: "{fields.get("search_term")}"
Primary CTA: "{fields.get("primary_cta")}"
Intent: "{fields.get("intent")}"
Audience persona: "{fields.get("audience_persona")}"
Offer: "{fields.get("offer")}"
Must include: "{fields.get("must_include")}"
Must not say: "{fields.get("must_not_say")}"

Requirements:
- Title tag includes the search term verbatim.
- H1 includes the search term verbatim.
- Search term appears within the first 100 words and at least one H2.
- CTA above the fold and repeated.
- Scannable formatting.
- 3–6 FAQs.
- Provide a visual plan (diagram/screenshot/table) with placement notes.

Output sections:
1) Recommended angle (2 sentences)
2) SEO: title tag, meta description, slug
3) Page outline (H1 + H2s with bullets)
4) Draft copy for hero + 3 key sections
5) FAQs
6) Visual plan

Request ID: {request_id}
""".strip()


# ----------------------------
# Routes
# ----------------------------
@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/slack/events")
async def slack_events(request: Request):
    # Only needed if you enable Event Subscriptions
    raw_body = await request.body()
    # Slack events are signed too
    verify_slack_signature(
        raw_body,
        request.headers.get("X-Slack-Request-Timestamp", ""),
        request.headers.get("X-Slack-Signature", ""),
    )
    body = json.loads(raw_body.decode("utf-8") or "{}")

    if body.get("type") == "url_verification":
        return JSONResponse({"challenge": body.get("challenge")})

    return JSONResponse({"ok": True})


@app.post("/slack/commands")
async def slack_commands(request: Request):
    """
    Slash command endpoint: opens modal.
    Slash Command Request URL must point here.
    """
    raw_body = await request.body()

    # Log basics for debugging (safe; does not log tokens)
    logger.info("SLASH /slack/commands hit. bytes=%s", len(raw_body))

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

    # IMPORTANT: views.open must succeed quickly. If your Render instance cold-starts,
    # Slack might still be OK, but this is the correct approach.
    await slack_api("views.open", {"trigger_id": trigger_id, "view": view})

    return PlainTextResponse("", status_code=200)


@app.post("/slack/interactions")
async def slack_interactions(request: Request):
    """
    Modal submissions & interactive events.
    Interactivity Request URL must point here.
    """
    raw_body = await request.body()
    logger.info("INTERACTIONS /slack/interactions hit. bytes=%s", len(raw_body))

    try:
        verify_slack_signature(
            raw_body,
            request.headers.get("X-Slack-Request-Timestamp", ""),
            request.headers.get("X-Slack-Signature", ""),
        )
    except Exception as e:
        logger.exception("Signature verification failed: %s", e)
        # Slack will show "can't connect" if this isn't 200.
        # But we *should* return a clear error so you can see it in logs.
        raise

    form = await request.form()
    payload_raw = form.get("payload")
    if not payload_raw:
        # Slack expects 200. Return ok so UI doesn't freak out.
        return JSONResponse({"ok": True})

    payload = json.loads(payload_raw)
    payload_type = payload.get("type")

    if payload_type == "view_submission":
        view = payload.get("view", {})
        if view.get("callback_id") != "lp_request_modal":
            return JSONResponse({"response_action": "clear"})

        fields = extract_modal_values(view.get("state", {}))

        # Required fields validation (inline modal errors)
        errors = {}
        if not fields.get("search_term"):
            errors["search_term_block"] = "Search term is required."
        if not fields.get("primary_cta"):
            errors["primary_cta_block"] = "Primary CTA is required."
        if errors:
            return JSONResponse({"response_action": "errors", "errors": errors})

        request_id = generate_request_id()
        _slug = slugify(fields["search_term"])

        user_id = (payload.get("user") or {}).get("id") or "unknown"

        # Post to the channel where the command ran (stored in private_metadata)
        channel_id = (view.get("private_metadata") or "").strip() or SLACK_DEFAULT_CHANNEL
        if not channel_id:
            # If you want, you could DM the user here instead.
            return JSONResponse({"response_action": "clear"})

        starter = (
            f"🚀 *LP request started*\n"
            f"*Request ID:* {request_id}\n"
            f"*Search term:* {fields['search_term']}\n"
            f"*Primary CTA:* {fields['primary_cta']}\n"
            f"*Intent:* {fields.get('intent') or '—'}\n"
            f"*Persona:* {fields.get('audience_persona') or '—'}\n"
            f"*Requester:* <@{user_id}>"
        )

        async def run_workflow():
            thread_ts = None
            try:
                thread_ts = await post_message(channel_id, starter)

                await post_message(
                    channel_id,
                    f"🧠 Drafting outline + copy with Claude… (request: {request_id})",
                    thread_ts=thread_ts,
                )

                prompt = build_claude_prompt(fields, request_id)
                claude_text = await call_claude(prompt)

                max_len = 3500
                if len(claude_text) > max_len:
                    claude_text = claude_text[:max_len] + "\n\n…(truncated)"

                await post_message(
                    channel_id,
                    f"✅ *Claude draft ready* for *{request_id}*\n```{claude_text}```",
                    thread_ts=thread_ts,
                )
            except Exception as e:
                logger.exception("Workflow failed: %s", e)
                if thread_ts:
                    try:
                        await post_message(channel_id, f"❌ Workflow failed for {request_id}: `{e}`", thread_ts=thread_ts)
                    except Exception:
                        pass

        # IMPORTANT: do not block Slack; run async task
        asyncio.create_task(run_workflow())

        # Immediately close modal (Slack requires <3s response)
        return JSONResponse({"response_action": "clear"})

    return JSONResponse({"ok": True})
