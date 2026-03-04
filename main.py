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
# IMPORTANT: channel ID like C0AHY0FAN4C (not "#sem-lp-requests")
SLACK_DEFAULT_CHANNEL = os.getenv("SLACK_DEFAULT_CHANNEL", "").strip()

SLACK_API_BASE = "https://slack.com/api"


# ----------------------------
# Slack signature verification
# ----------------------------
def verify_slack_signature(raw_body: bytes, timestamp: str, signature: str) -> None:
    """
    https://api.slack.com/authentication/verifying-requests-from-slack
    """
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

    # Use compare_digest to avoid timing attacks
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")


# ----------------------------
# Helpers
# ----------------------------
def generate_request_id() -> str:
    # LP-YYYYMMDD-HHMM
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
    """
    Required:
      - Search term
      - Primary CTA
      - Intent (Commercial | Educational | Transactional)
      - Primary Audience (Economic Buyer | Platform Engineer)
    """
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
                    "placeholder": {"type": "plain_text", "text": "Select a CTA"},
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
                "label": {"type": "plain_text", "text": "Intent"},
                "element": {
                    "type": "static_select",
                    "action_id": "intent",
                    "placeholder": {"type": "plain_text", "text": "Select intent"},
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
                "label": {"type": "plain_text", "text": "Primary Audience"},
                "element": {
                    "type": "static_select",
                    "action_id": "primary_audience",
                    "placeholder": {"type": "plain_text", "text": "Select audience"},
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
        "primary_audience": get_value("primary_audience_block", "primary_audience"),
        "offer": get_value("offer_block", "offer"),
        "must_include": get_value("must_include_block", "must_include"),
        "must_not_say": get_value("must_not_say_block", "must_not_say"),
    }


def render_basic_html(fields: Dict[str, Any], request_id: str) -> str:
    """
    Placeholder HTML generator (no Claude/API needed).
    Replace later with a full template renderer or Claude output.
    """
    term = fields["search_term"]
    cta = fields["primary_cta"]
    intent = fields["intent"]
    audience = fields["primary_audience"]
    slug = slugify(term)

    title_tag = f"{term} | DataHub"
    meta_desc = f"Learn how DataHub supports {term}. Explore key capabilities, outcomes, and next steps. {cta} available."

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{title_tag}</title>
  <meta name="description" content="{meta_desc}" />
</head>
<body>
  <!-- Request: {request_id} -->
  <header>
    <p><strong>Keyword:</strong> {term}</p>
    <p><strong>Intent:</strong> {intent} | <strong>Primary Audience:</strong> {audience}</p>
    <a href="#cta">{cta}</a>
  </header>

  <main>
    <section id="hero">
      <h1>{term}</h1>
      <p>
        {term} — built for {audience}. (This is a starter skeleton; swap in brand + final copy.)
      </p>
      <a id="cta" href="#cta">{cta}</a>
    </section>

    <section>
      <h2>Why {term} matters</h2>
      <ul>
        <li>Add 3–5 benefit bullets</li>
        <li>Keep claims conservative until validated</li>
      </ul>
    </section>

    <section>
      <h2>{term} capabilities</h2>
      <ul>
        <li>Capability 1</li>
        <li>Capability 2</li>
        <li>Capability 3</li>
      </ul>
    </section>

    <section>
      <h2>FAQs about {term}</h2>
      <details><summary>FAQ 1</summary><p>Answer…</p></details>
      <details><summary>FAQ 2</summary><p>Answer…</p></details>
      <details><summary>FAQ 3</summary><p>Answer…</p></details>
    </section>

    <section>
      <h2>Next step</h2>
      <p>Repeat CTA and reinforce what happens after click.</p>
      <a href="#cta">{cta}</a>
    </section>
  </main>

  <footer>
    <p>Slug suggestion: <code>{slug}</code></p>
  </footer>
</body>
</html>"""
    return html


async def generate_build_kit_and_post(channel_id: str, starter_text: str, fields: Dict[str, Any], request_id: str) -> None:
    """
    Background workflow: post starter message, then post HTML skeleton in-thread.
    """
    thread_ts = await post_message(channel_id, starter_text)

    await post_message(
        channel_id,
        f"🛠️ Building initial HTML skeleton (no Claude API key yet). Next we can swap this for Claude-rendered HTML.",
        thread_ts=thread_ts,
    )

    html = render_basic_html(fields, request_id)

    # Keep message size safe
    max_len = 3500
    if len(html) > max_len:
        html = html[:max_len] + "\n...(truncated)"

    await post_message(
        channel_id,
        f"✅ *Starter HTML* for *{request_id}*:\n```{html}```",
        thread_ts=thread_ts,
    )

    await post_message(
        channel_id,
        "Next step options:\n"
        "1) Add your brand guide + sample HTML and we’ll upgrade this into the real template.\n"
        "2) When you have Claude API access, we’ll have Claude render the full HTML into the thread (or Drive).",
        thread_ts=thread_ts,
    )


# ----------------------------
# Routes
# ----------------------------
@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/slack/commands")
async def slack_commands(request: Request):
    """
    Slash command endpoint: opens modal.
    Slash Command Request URL must point here.
    """
    raw_body = await request.body()
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
    channel_id = (form.get("channel_id") or "").strip()

    if command != "/sem-lp-request":
        return PlainTextResponse("Unsupported command.", status_code=200)

    if not trigger_id:
        return PlainTextResponse("Missing trigger_id.", status_code=200)

    view = build_modal_view(initial_search_term=text, channel_id=channel_id)
    await slack_api("views.open", {"trigger_id": trigger_id, "view": view})

    return PlainTextResponse("", status_code=200)


@app.post("/slack/interactions")
async def slack_interactions(request: Request, background_tasks: BackgroundTasks):
    """
    Modal submissions & interactive events.
    Interactivity Request URL must point here.

    IMPORTANT: Must return within ~3 seconds. Do not do network calls before responding.
    """
    raw_body = await request.body()
    logger.info("INTERACTIONS /slack/interactions hit. bytes=%s", len(raw_body))

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
            if not fields.get("intent"):
                errors["intent_block"] = "Intent is required."
            if not fields.get("primary_audience"):
                errors["primary_audience_block"] = "Primary Audience is required."

            if errors:
                return JSONResponse({"response_action": "errors", "errors": errors})

            request_id = generate_request_id()
            user_id = (payload.get("user") or {}).get("id") or "unknown"

            # Post to the channel where the command ran (stored in private_metadata),
            # fallback to SLACK_DEFAULT_CHANNEL
            channel_id = (view.get("private_metadata") or "").strip() or SLACK_DEFAULT_CHANNEL
            if not channel_id:
                # no channel available; close modal gracefully
                logger.warning("No channel_id available (private_metadata empty and no SLACK_DEFAULT_CHANNEL).")
                return JSONResponse({"response_action": "clear"})

            starter = (
                f"🚀 *LP request started*\n"
                f"*Request ID:* {request_id}\n"
                f"*Search term:* {fields['search_term']}\n"
                f"*Primary CTA:* {fields['primary_cta']}\n"
                f"*Intent:* {fields['intent']}\n"
                f"*Primary Audience:* {fields['primary_audience']}\n"
                f"*Requester:* <@{user_id}>"
            )

            # Background workflow: do Slack API calls after we respond to Slack
            background_tasks.add_task(generate_build_kit_and_post, channel_id, starter, fields, request_id)

            # Immediately clear modal
            return JSONResponse({"response_action": "clear"})

        return JSONResponse({"ok": True})

    except Exception as e:
        # KEY: still return 200 so Slack doesn't show "trouble connecting"
        logger.exception("Error handling /slack/interactions: %s", e)
        return JSONResponse({"response_action": "clear"})
