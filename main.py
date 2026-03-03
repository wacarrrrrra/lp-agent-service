"""
LP Agent Service - Slack /lp-request endpoint (v1)

What this does:
- Exposes POST /slack/commands for Slack slash command /lp-request
- Verifies Slack request signatures (Signing Secret)
- Parses optional key=value arguments from the command text
- Generates request_id (LP-YYYYMMDD-HHMM)
- Immediately ACKs Slack with an ephemeral response (<3s)
- Posts a visible “LP request started” message in the same channel (background task)

Required env vars (Render -> Environment):
- SLACK_SIGNING_SECRET
- SLACK_BOT_TOKEN

Optional env vars:
- SLACK_DEFAULT_CHANNEL   (fallback channel if Slack doesn't send channel_id; usually not needed)
"""

import os
import time
import hmac
import hashlib
import re
from datetime import datetime
from typing import Dict, Optional

import httpx
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse


app = FastAPI()

SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_DEFAULT_CHANNEL = os.getenv("SLACK_DEFAULT_CHANNEL", "")  # optional


# ----------------------------
# Slack signature verification
# ----------------------------
def verify_slack_signature(raw_body: bytes, timestamp: str, signature: str) -> None:
    """
    Verify Slack request signature using signing secret.

    Slack docs:
    https://api.slack.com/authentication/verifying-requests-from-slack
    """
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
    # LP-YYYYMMDD-HHMM (server-local time; fine for v1)
    return datetime.now().strftime("LP-%Y%m%d-%H%M")


def parse_command_text(text: str) -> Dict[str, str]:
    """
    Parses slash command text.

    Supported examples:
      /lp-request search_term="datahub architecture" cta="Demo" intent=commercial
      /lp-request search_term=datahub-architecture cta=Demo
      /lp-request datahub architecture      (fallback => search_term)

    Returns keys in lowercase.
    """
    text = (text or "").strip()
    if not text:
        return {}

    # key="value" OR key=value tokens
    pattern = r'(\w+)=(".*?"|\'.*?\'|[^\s]+)'
    matches = re.findall(pattern, text)
    if matches:
        out: Dict[str, str] = {}
        for k, v in matches:
            v = v.strip().strip('"').strip("'")
            out[k.lower()] = v
        return out

    # fallback: treat whole string as search_term
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
        # Raise a 500 so Render logs show the Slack error payload
        raise HTTPException(status_code=500, detail=f"Slack chat.postMessage failed: {data}")


# ----------------------------
# Routes
# ----------------------------
@app.get("/health")
async def health():
    return {"ok": True}


@app.api_route("/slack/commands", methods=["GET", "POST", "HEAD"])
async def slack_commands(request: Request, background_tasks: BackgroundTasks):

    # Slack validation probe
    if request.method in ["GET", "HEAD"]:
        return {"status": "ok"}

    body = await request.body()
    logger.info("🔥 SLACK HIT /slack/commands")
    logger.info("Method: %s", request.method)

    form = await request.form()
    command = form.get("command")
    text = form.get("text")

    return {
        "response_type": "ephemeral",
        "text": f"Received command: {command} with text: {text}"
    }

    from fastapi import FastAPI, Request
import logging

app = FastAPI()

logger = logging.getLogger("uvicorn.error")


from fastapi import Request
from fastapi.responses import JSONResponse

@app.post("/slack/events")
async def slack_events(request: Request):
    body = await request.json()

    # 🔐 Slack URL verification
    if body.get("type") == "url_verification":
        return JSONResponse({"challenge": body.get("challenge")})

    # Handle real events here later
    return JSONResponse({"ok": True})

@app.post("/slack/commands")
async def slack_commands(request: Request):

    # 👇 ADD THIS BLOCK RIGHT HERE
    body = await request.body()
    logger.info("🔥 SLACK HIT /slack/commands")
    logger.info("Method: %s", request.method)
    logger.info("Headers: %s", dict(request.headers))
    logger.info("Body length: %s", len(body))

    # then your existing logic continues below...
    form = await request.form()
    command = form.get("command")
    text = form.get("text")

    return {
        "response_type": "ephemeral",
        "text": f"Received command: {command} with text: {text}"
    }
    raw_body = await request.body()

    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    verify_slack_signature(raw_body, timestamp, signature)

    # Slack slash commands send x-www-form-urlencoded
    form = await request.form()
    command = form.get("command")               # "/lp-request"
    text = form.get("text")                     # user args after command
    channel_id = form.get("channel_id")         # where command was run
    user_id = form.get("user_id")               # requesting user
    channel_name = form.get("channel_name")     # may be "directmessage" or channel name

    if command != "/lp-request":
        return PlainTextResponse("Unsupported command", status_code=200)

    fields = parse_command_text(text)
    search_term = fields.get("search_term")
    primary_cta = fields.get("cta") or fields.get("primary_cta")
    intent = fields.get("intent")

    request_id = generate_request_id()

    # Ack quickly (Slack expects < 3 seconds)
    ack_text = (
        f"✅ Got it! LP request received.\n"
        f"- Request ID: {request_id}\n"
        f"- Search term: {search_term or '(not provided)'}\n"
        f"- Primary CTA: {primary_cta or '(not provided)'}\n"
        f"{('- Intent: ' + intent) if intent else ''}\n\n"
        f"I’ll post updates in <#{channel_id}>."
        if channel_id
        else "I’ll post updates in the channel."
    )

    # Post a visible message to the channel in the background
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
