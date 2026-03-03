"""
LP Agent Service - Slack slash command endpoint

Routes:
- GET  /health
- POST /slack/commands  (Slash command)
- POST /slack/events    (Event API URL verification)

Env vars (Render -> Environment):
- SLACK_SIGNING_SECRET   (required)
- SLACK_BOT_TOKEN        (required)  Bot User OAuth Token (xoxb-...)
- SLACK_COMMAND_NAME     (optional)  e.g. "/sem-lp-request" (default)
- SLACK_DEFAULT_CHANNEL  (optional)  fallback channel_id if Slack doesn’t send one
"""

import os
import time
import hmac
import hashlib
import logging
import re
from datetime import datetime
from typing import Dict, Optional

import httpx
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

# ----------------------------
# App + Logging
# ----------------------------
app = FastAPI()

logger = logging.getLogger("uvicorn.error")

SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_DEFAULT_CHANNEL = os.getenv("SLACK_DEFAULT_CHANNEL", "")
SLACK_COMMAND_NAME = os.getenv("SLACK_COMMAND_NAME", "/sem-lp-request")  # change if needed


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

    basestring = b"v0:" + timestamp.encode("utf-8") + b":" + raw_body
    expected = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode("utf-8"),
        basestring,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature or ""):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")


# ----------------------------
# Helpers
# ----------------------------
def generate_request_id() -> str:
    # LP-YYYYMMDD-HHMM (server local time)
    return datetime.now().strftime("LP-%Y%m%d-%H%M")


def parse_command_text(text: str) -> Dict[str, str]:
    """
    Supports:
      /sem-lp-request search_term="datahub architecture" cta="Demo" intent=commercial
      /sem-lp-request search_term=datahub-architecture cta=Demo
      /sem-lp-request datahub architecture   (fallback => search_term)
    """
    text = (text or "").strip()
    if not text:
        return {}

    pattern = r'(\w+)=(".*?"|\'.*?\'|[^\s]+)'
    matches = re.findall(pattern, text)
    if matches:
        out: Dict[str, str] = {}
        for k, v in matches:
            v = v.strip().strip('"').strip("'")
            out[k.lower()] = v
        return out

    return {"search_term": text}


async def slack_post_message(channel: str, text: str, thread_ts: Optional[str] = None) -> None:
    if not SLACK_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Missing SLACK_BOT_TOKEN")

    payload = {"channel": channel, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
            json=payload,
        )

    data = resp.json()
    if not data.get("ok"):
        logger.error("Slack chat.postMessage failed: %s", data)
        raise HTTPException(status_code=500, detail=f"Slack chat.postMessage failed: {data}")


# ----------------------------
# Routes
# ----------------------------
@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/slack/events")
async def slack_events(request: Request):
    body = await request.json()

    # Slack URL verification challenge
    if body.get("type") == "url_verification":
        return JSONResponse({"challenge": body.get("challenge")})

    # For later: handle events
    return JSONResponse({"ok": True})


@app.post("/slack/commands")
async def slack_commands(request: Request, background_tasks: BackgroundTasks):
    raw_body = await request.body()

    # Helpful logs while debugging
    logger.info("🔥 SLACK HIT /slack/commands")
    logger.info("Headers (subset): ts=%s sig=%s content-type=%s",
                request.headers.get("X-Slack-Request-Timestamp"),
                request.headers.get("X-Slack-Signature"),
                request.headers.get("content-type"))

    # Verify Slack signature
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    verify_slack_signature(raw_body, timestamp, signature)

    # Parse form data
    form = await request.form()
    command = form.get("command")           # e.g. "/sem-lp-request"
    text = form.get("text") or ""
    channel_id = form.get("channel_id")
    user_id = form.get("user_id")

    logger.info("Command=%s Text=%s Channel=%s User=%s", command, text, channel_id, user_id)

    # Accept either configured command OR legacy "/lp-request"
    if command not in {SLACK_COMMAND_NAME, "/lp-request"}:
        return JSONResponse({
            "response_type": "ephemeral",
            "text": f"Unsupported command: {command}. Expected {SLACK_COMMAND_NAME}."
        })

    fields = parse_command_text(text)
    search_term = fields.get("search_term")
    primary_cta = fields.get("cta") or fields.get("primary_cta")
    intent = fields.get("intent")

    request_id = generate_request_id()

    # ACK immediately (Slack requires <3 seconds)
    ack_text = (
        f"✅ *LP request received*\n"
        f"*Request ID:* {request_id}\n"
        f"*Search term:* {search_term or 'TBD'}\n"
        f"*Primary CTA:* {primary_cta or 'TBD'}\n"
        f"{('*Intent:* ' + intent) if intent else ''}\n\n"
        f"I’ll post updates here shortly."
    )

    # Post a visible message asynchronously
    channel_to_use = channel_id or SLACK_DEFAULT_CHANNEL
    if channel_to_use:
        visible_msg = (
            f"🚀 *LP request started*\n"
            f"*Request ID:* {request_id}\n"
            f"*Search term:* {search_term or 'TBD'}\n"
            f"*Primary CTA:* {primary_cta or 'TBD'}\n"
            f"*Intent:* {intent or 'TBD'}\n"
            f"*Requester:* <@{user_id}>\n\n"
            f"Next: I’ll confirm any missing fields, then generate the Build Kit."
        )
        background_tasks.add_task(slack_post_message, channel_to_use, visible_msg)

    return JSONResponse({"response_type": "ephemeral", "text": ack_text})
