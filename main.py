import os
import time
import hmac
import hashlib
import json
import re
from datetime import datetime
from typing import Dict, Optional

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse

app = FastAPI()

SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_DEFAULT_CHANNEL = os.getenv("SLACK_DEFAULT_CHANNEL", "")  # optional


def verify_slack_signature(raw_body: bytes, timestamp: str, signature: str) -> None:
    """
    Verifies Slack request signature.
    Slack docs: signing secret verification with v0 format.
    """
    if not SLACK_SIGNING_SECRET:
        raise HTTPException(status_code=500, detail="Missing SLACK_SIGNING_SECRET")

    # Prevent replay attacks (5 min window)
    now = int(time.time())
    try:
        ts = int(timestamp)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Slack timestamp")

    if abs(now - ts) > 60 * 5:
        raise HTTPException(status_code=400, detail="Stale Slack request (possible replay)")

    basestring = b"v0:" + timestamp.encode("utf-8") + b":" + raw_body
    my_sig = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode("utf-8"),
        basestring,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(my_sig, signature or ""):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")


def generate_request_id() -> str:
    # LP-YYYYMMDD-HHMM (local server time; good enough for v1)
    return datetime.now().strftime("LP-%Y%m%d-%H%M")


def parse_command_text(text: str) -> Dict[str, str]:
    """
    Very simple parser for slash command text.

    Supports:
      search_term="datahub architecture" cta="Demo" intent=commercial
    or:
      datahub architecture

    Returns dict with keys like search_term, primary_cta, intent, etc.
    """
    text = (text or "").strip()
    if not text:
        return {}

    # key="value" OR key=value tokens
    pattern = r'(\w+)=(".*?"|\'.*?\'|[^\s]+)'
    matches = re.findall(pattern, text)
    if matches:
        out = {}
        for k, v in matches:
            v = v.strip().strip('"').strip("'")
            out[k.lower()] = v
        return out

    # fallback: treat entire text as search term
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
        raise HTTPException(status_code=500, detail=f"Slack postMessage failed: {data}")


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/slack/commands")
async def slack_commands(request: Request):
    raw_body = await request.body()

    # Slack signature headers
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    verify_slack_signature(raw_body, timestamp, signature)

    # Slack slash commands are sent as application/x-www-form-urlencoded
    form = await request.form()
    command = form.get("command")           # e.g. /lp-request
    text = form.get("text")                # whatever user typed after command
    channel_id = form.get("channel_id")    # where command was used
    user_id = form.get("user_id")
    response_url = form.get("response_url")  # can be used later, but not needed for v1

    if command != "/lp-request":
        return PlainTextResponse("Unsupported command", status_code=200)

    fields = parse_command_text(text)
    search_term = fields.get("search_term")
    primary_cta = fields.get("cta") or fields.get("primary_cta")

    request_id = generate_request_id()

    # Immediate ephemeral-ish response (visible to user who ran the command)
    # Note: Slack slash commands expect a response within 3 seconds.
    ack_text = (
        f"✅ Got it! Request received.\n"
        f"- Request ID: {request_id}\n"
        f"- Search term: {search_term or '(not provided)'}\n"
        f"- Primary CTA: {primary_cta or '(not provided)'}\n\n"
        f"I’ll post progress updates in this channel."
    )

    # Post a visible message to the channel (so the whole team sees it)
    channel_to_use = channel_id if channel_id else SLACK_DEFAULT_CHANNEL
    if channel_to_use:
        # Post as a new message (top-level). Later we can thread everything off this ts.
        post_text = (
            f"🚀 LP request started\n"
            f"*Request ID:* {request_id}\n"
            f"*Search term:* {search_term or 'TBD'}\n"
            f"*Primary CTA:* {primary_cta or 'TBD'}\n"
            f"*Requester:* <@{user_id}>\n\n"
            f"Next: I’ll confirm missing fields (if any), then generate the Build Kit."
        )
        # Fire-and-forget in v1 (still awaited, but fast)
        await slack_post_message(channel_to_use, post_text)

    return JSONResponse(
        {
            "response_type": "ephemeral",
            "text": ack_text,
        }
    )
