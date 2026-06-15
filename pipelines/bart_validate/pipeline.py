"""
Bart validation pipeline orchestrator (event-driven, mirrors /technical-lp v3).

Phase 1 (run_bart_validate_generation) — called from main.py's modal submission handler:
  Fetch source (Sheet or Doc) → post Bart prompt to SEM_LP_REQUESTS_CHANNEL →
  register JOB awaiting BART_DONE → return. No further work until Bart responds.

Phase 2 (run_bart_validate_from_response) — called from main.py's /slack/events
  handler when Bart posts BART_DONE in the registered thread:
  Accumulate Bart's reply → assemble result Google Doc → post link to
  SEM_LP_BUILD_KITS_CHANNEL and to the requester channel.
"""
import logging
from typing import Any, Callable, Dict

from pipelines.bart_validate.bart_prompt import (
    build_bart_validate_prompt,
    format_content_block,
)
from pipelines.bart_validate.gdoc_read import read_sheet, read_doc
from pipelines.technical_lp.gdoc_create import create_technical_lp_doc

logger = logging.getLogger("uvicorn.error")


def _slack_archive_link(channel_id: str, thread_ts: str) -> str:
    """Best-effort archive link. Channel ID, not name — Slack resolves it."""
    ts_compact = (thread_ts or "").replace(".", "")
    if not channel_id or not ts_compact:
        return ""
    return f"https://slack.com/archives/{channel_id}/p{ts_compact}"


async def run_bart_validate_generation(
    inputs: Dict[str, Any],
    request_id: str,
    requester_channel: str,
    user_id: str,
    post_message: Callable,
    bart_channel: str,
    build_kits_channel: str,
    jobs: Dict[str, Any],
    save_jobs: Callable,
) -> None:
    """Phase 1: fetch source, post prompt to Bart, register the job awaiting BART_DONE."""
    source_type = (inputs.get("source_type") or "").strip()
    source_url  = (inputs.get("source_url") or "").strip()
    sheet_tab   = (inputs.get("sheet_tab") or "").strip()
    context     = (inputs.get("context") or "").strip()

    try:
        await post_message(
            requester_channel,
            f"🔎 Bart validation request received _(Request ID: {request_id})_.\n"
            f"*Context:* {context}\n"
            f"Step 1/3 — Fetching source content…",
        )

        # Fetch source content
        sheet_rows = None
        doc_text = None
        try:
            if source_type == "keywords":
                resolved_tab, sheet_rows = await read_sheet(source_url, sheet_tab)
                await post_message(
                    requester_channel,
                    f"📥 Read tab *{resolved_tab}* — {max(0, len(sheet_rows) - 1)} rows of keywords.",
                )
            else:
                doc_text = await read_doc(source_url)
                await post_message(
                    requester_channel,
                    f"📥 Read Google Doc — {len(doc_text)} chars.",
                )
        except Exception as e:
            logger.exception("Failed to read source for %s: %s", request_id, e)
            await post_message(
                requester_channel,
                f"❌ Could not read the source URL _(Request ID: {request_id})_: `{e}`\n"
                f"_Make sure the file is shared with the service account "
                f"`blog-agent@robust-limiter-488800-g5.iam.gserviceaccount.com` (Viewer is enough)._",
            )
            return

        content_block = format_content_block(source_type, sheet_rows, doc_text)

        # Post starter + prompt in Bart's channel; register the job
        starter = (
            f"🔎 *Bart validation request*\n"
            f"*Request ID:* {request_id}\n"
            f"*Context:* {context}\n"
            f"*Source:* {source_url}\n"
            f"*Requester:* <@{user_id}>"
        )
        bart_thread_ts = await post_message(bart_channel, starter)

        jobs[bart_thread_ts] = {
            "pipeline": "bart_validate",
            "request_id": request_id,
            "user_id": user_id,
            "requester_channel": requester_channel,
            "bart_channel": bart_channel,
            "build_kits_channel": build_kits_channel,
            "inputs": dict(inputs),
            "content_block": content_block,
            "awaiting": "bart_grounding_bart_validate",
        }
        save_jobs()

        prompt = build_bart_validate_prompt(
            request_id=request_id,
            source_type=source_type,
            source_url=source_url,
            context=context,
            content_block=content_block,
        )
        await post_message(bart_channel, prompt, thread_ts=bart_thread_ts)
        await post_message(
            bart_channel,
            "⏳ Waiting for Bart… pipeline continues automatically after `BART_DONE`.",
            thread_ts=bart_thread_ts,
        )
        await post_message(
            requester_channel,
            f"📨 Step 2/3 — Sent to Bart. I'll post the validation doc here when Bart finishes.",
        )

    except Exception as e:
        logger.exception("run_bart_validate_generation (phase 1) failed: %s", e)
        try:
            await post_message(
                requester_channel,
                f"❌ Bart validation pipeline failed _(Request ID: {request_id})_: `{e}`",
            )
        except Exception:
            pass


async def run_bart_validate_from_response(
    job: Dict[str, Any],
    thread_ts: str,
    post_message: Callable,
    fetch_thread_messages: Callable,
    accumulate_bart_brief: Callable,
    bart_user_id: str,
    jobs: Dict[str, Any],
    save_jobs: Callable,
) -> None:
    """Phase 2: assemble Bart's reply, write to a Google Doc, post link to build-kits."""
    requester_channel  = job["requester_channel"]
    bart_channel       = job["bart_channel"]
    build_kits_channel = job.get("build_kits_channel") or requester_channel
    request_id         = job["request_id"]
    user_id            = job["user_id"]
    inputs             = job["inputs"]
    content_block      = job.get("content_block", "")
    context            = (inputs.get("context") or "").strip()
    source_url         = (inputs.get("source_url") or "").strip()

    try:
        await post_message(bart_channel, "📖 Collecting Bart's response…", thread_ts=thread_ts)
        messages = await fetch_thread_messages(bart_channel, thread_ts)
        bart_response = accumulate_bart_brief(messages, bart_user_id) or ""

        thread_link = _slack_archive_link(bart_channel, thread_ts)

        # Build the result Google Doc body in markdown
        body_md = (
            f"# Bart validation results\n\n"
            f"**Request ID:** {request_id}  \n"
            f"**Context:** {context}  \n"
            f"**Source:** {source_url}  \n"
            f"**Slack thread:** {thread_link or '_(see #sem-lp-requests)_'}\n\n"
            f"## Content submitted for validation\n\n"
            f"{content_block}\n\n"
            f"## Bart's response\n\n"
            f"{bart_response}\n\n"
            f"## Summary — items to act on\n\n"
            f"_Parse Bart's response above. Triage:_\n\n"
            f"- ✅ **Validated** — items Bart confirmed are accurate\n"
            f"- ⚠️ **Needs revision** — items Bart said need adjustment\n"
            f"- ❌ **Exclude** — items Bart flagged as not supported by DataHub\n"
        )

        await post_message(requester_channel, "📄 Step 3/3 — Writing Google Doc…")
        title = f"{request_id} — Bart Validation: {context[:80]}".strip()
        gdoc_url = await create_technical_lp_doc(title=title, markdown_body=body_md)

        # Post to build-kits per spec, and back to the requester
        completion = (
            f"Bart validation complete ✅\n"
            f"*Request ID:* {request_id}\n"
            f"*Context:* {context}\n"
            f"*Source:* {source_url}\n"
            f"*Results:* {gdoc_url}"
        )
        await post_message(build_kits_channel, completion)
        if requester_channel and requester_channel != build_kits_channel:
            await post_message(
                requester_channel,
                f"✅ Validation doc ready: {gdoc_url}\n_Request ID:_ `{request_id}` · _Requester:_ <@{user_id}>",
            )
        await post_message(
            bart_channel,
            f"✅ Validation doc created: {gdoc_url}",
            thread_ts=thread_ts,
        )

        jobs.pop(thread_ts, None)
        save_jobs()

    except Exception as e:
        logger.exception("run_bart_validate_from_response (phase 2) failed: %s", e)
        try:
            await post_message(
                requester_channel,
                f"❌ Validation doc creation failed _(Request ID: {request_id})_: `{e}`",
            )
            await post_message(
                bart_channel,
                f"❌ Doc creation failed: `{e}`",
                thread_ts=thread_ts,
            )
        except Exception:
            pass
        jobs.pop(thread_ts, None)
        save_jobs()
