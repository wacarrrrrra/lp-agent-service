import os
import time
import hmac
import hashlib
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

import httpx
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, PlainTextResponse

app = FastAPI()
logger = logging.getLogger("uvicorn.error")

SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_DEFAULT_CHANNEL = os.getenv("SLACK_DEFAULT_CHANNEL", "")  # channel ID (C123...), optional

# Claude (Anthropic) - optional for step 2
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-latest")


# ----------------------------
# Slack signature verification
# ----------------------------
def verify_slack_signature(raw_body: bytes, timestamp: str, signature: str) -> None:
    if not SLACK_SIGNING_SECRET:
        raise HTTPException(status_code=500, detail="Missing SLACK_SIGNING_SECRET")

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

    if not hmac.compare_digest(expected, signature or ""):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")


def generate_request_id() -> str:
    # LP-YYYYMMDD-HHMM
    return datetime.now().strftime("LP-%Y%m%d-%H%M")


def slugify(text: str, max_len: int = 50) -> str:
    t = (text or "").strip().lower()
    # replace spaces with hyphens
    t = "-".join(t.split())
    # remove non-alnum / hyphen
    cleaned = []
    for ch in t:
        if ch.isalnum() or ch == "-":
            cleaned.append(ch)
    out = "".join(cleaned)
    return out[:max_len] if len(out) > max_len else out


async def slack_api(method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not SLACK_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Missing SLACK_BOT_TOKEN")

    url = f"https://slack.com/api/{method}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}, json=payload)
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


def build_modal_view(initial_search_term: str = "") -> Dict[str, Any]:
    # Slack Block Kit modal
    return {
        "type": "modal",
        "callback_id": "lp_request_modal",
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

    def get_input(block_id: str, action_id: str) -> Optional[str]:
        block = values.get(block_id, {})
        action = block.get(action_id, {})
        # text input uses "value", selects use "selected_option"
        if "value" in action:
            return action.get("value")
        selected = action.get("selected_option")
        if selected:
            return selected.get("value")
        return None

    return {
        "search_term": get_input("search_term_block", "search_term"),
        "primary_cta": get_input("primary_cta_block", "primary_cta"),
        "intent": get_input("intent_block", "intent"),
        "audience_persona": get_input("persona_block", "audience_persona"),
        "offer": get_input("offer_block", "offer"),
        "must_include": get_input("must_include_block", "must_include"),
        "must_not_say": get_input("must_not_say_block", "must_not_say"),
    }


async def call_claude(prompt: str) -> str:
    """
    Minimal Anthropic Messages API call via HTTP.
    If you want, we can swap to the official SDK later.
    """
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

    # content is list of blocks; extract text
    parts = data.get("content", [])
    text_out = ""
    for p in parts:
        if p.get("type") == "text":
            text_out += p.get("text", "")
    return text_out.strip() or "(No text returned from Claude.)"


def build_claude_prompt(fields: Dict[str, Any], request_id: str) -> str:
    # You can evolve this into your full Build Kit spec.
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


@app.post("/slack/commands")
async def slack_commands(request: Request):
    """
    Slash command endpoint: opens a modal.
    """
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

    if command != "/sem-lp-request":
        # Return 200 so Slack doesn't show an error
        return PlainTextResponse("Unsupported command.", status_code=200)

    # Open modal
    channel_id = form.get("channel_id") or ""
    view = build_modal_view(initial_search_term=text)
    view["private_metadata"] = channel_id
    await slack_api("views.open", {"trigger_id": trigger_id, "view": view})

    # Must respond quickly to Slack
    return PlainTextResponse("", status_code=200)


@app.post("/slack/interactions")
async def slack_interactions(request: Request, background_tasks: BackgroundTasks):
    """
    Handles modal submissions.
    Slack sends payload as application/x-www-form-urlencoded with a 'payload' field (JSON string).
    """
    raw_body = await request.body()
    verify_slack_signature(
        raw_body,
        request.headers.get("X-Slack-Request-Timestamp", ""),
        request.headers.get("X-Slack-Signature", ""),
    )

    form = await request.form()
    payload = json.loads(form.get("payload", "{}"))

    payload_type = payload.get("type")

    # Modal submit
    if payload_type == "view_submission":
        view = payload.get("view", {})
        callback_id = view.get("callback_id")

        if callback_id != "lp_request_modal":
            return JSONResponse({"response_action": "clear"})

        fields = extract_modal_values(view.get("state", {}))

        # Validate required fields
        if not fields.get("search_term") or not fields.get("primary_cta"):
            # Tell Slack to show inline errors
            errors = {}
            if not fields.get("search_term"):
                errors["search_term_block"] = "Search term is required."
            if not fields.get("primary_cta"):
                errors["primary_cta_block"] = "Primary CTA is required."
            return JSONResponse({"response_action": "errors", "errors": errors})

        request_id = generate_request_id()
        slug = slugify(fields["search_term"])

        user = payload.get("user", {})
        user_id = user.get("id")

        # Where to post
        # Prefer the channel the user ran the command from (stored in private_metadata if you want),
        # but for v1: use the conversation from the "view" if available, else fallback.
        channel_id = payload.get("view", {}).get("private_metadata") or SLACK_DEFAULT_CHANNEL
        
        # NOTE: If you want the exact channel the slash command ran in, you can:
        # - In /slack/commands, set view["private_metadata"] = channel_id
        # We'll add that enhancement next if you want. For now fallback is OK.

        if not channel_id:
            # If no channel, we can DM the user instead (not implemented here)
            return JSONResponse({"response_action": "clear"})

        # Post starter message in channel and capture thread_ts
        starter = (
            f"🚀 *LP request started*\n"
            f"*Request ID:* {request_id}\n"
            f"*Search term:* {fields['search_term']}\n"
            f"*Primary CTA:* {fields['primary_cta']}\n"
            f"*Intent:* {fields.get('intent') or '—'}\n"
            f"*Persona:* {fields.get('audience_persona') or '—'}\n"
            f"*Requester:* <@{user_id}>\n"
        )

        # Post and then do Claude in-thread
        async def run_workflow():
            thread_ts = await post_message(channel_id, starter)

            await post_message(
                channel_id,
                f"🧠 Drafting outline + copy with Claude… (request: {request_id})",
                thread_ts=thread_ts,
            )

            prompt = build_claude_prompt(fields, request_id)
            claude_text = await call_claude(prompt)

            # Keep Slack message size reasonable; if long, truncate
            max_len = 3500
            if len(claude_text) > max_len:
                claude_text = claude_text[:max_len] + "\n\n…(truncated)"

            await post_message(
                channel_id,
                f"✅ *Claude draft ready* for *{request_id}*\n```{claude_text}```",
                thread_ts=thread_ts,
            )

        background_tasks.add_task(run_workflow)

        # Clear the modal
        return JSONResponse({"response_action": "clear"})

    return JSONResponse({"ok": True})
