"""
Bart validation pipeline orchestrator (event-driven, mirrors /technical-lp v3).

Phase 1 (run_bart_validate_generation) — called from main.py's modal submission handler:
  Fetch source (Sheet, Doc, or hosted HTML page) → post Bart prompt to
  SEM_LP_REQUESTS_CHANNEL → register JOB awaiting BART_DONE → return.

Phase 2 (run_bart_validate_from_response) — called from main.py's /slack/events
  handler when Bart posts BART_DONE in the registered thread:
  Accumulate Bart's reply → extract the markdown summary table → post completion
  message to SEM_LP_BUILD_KITS_CHANNEL (full Bart response in threaded replies if
  it exceeds Slack's 40k limit). No Google Doc is created.
"""
import logging
from typing import Any, Callable, Dict, List

from pipelines.bart_validate.bart_prompt import (
    build_bart_validate_prompt,
    count_verdicts,
    extract_summary_table,
    format_content_block,
)
from pipelines.bart_validate.gdoc_read import read_doc, read_html_url, read_sheet

logger = logging.getLogger("uvicorn.error")

# Slack hard-limits a message at 40,000 chars. Leave headroom for our own wrapping.
_SLACK_CHUNK_BUDGET = 35_000


def _slack_archive_link(channel_id: str, thread_ts: str) -> str:
    ts_compact = (thread_ts or "").replace(".", "")
    if not channel_id or not ts_compact:
        return ""
    return f"https://slack.com/archives/{channel_id}/p{ts_compact}"


def _chunk_for_slack(text: str, budget: int = _SLACK_CHUNK_BUDGET) -> List[str]:
    """Split a long string into <=budget-char chunks, preferring line boundaries."""
    if len(text) <= budget:
        return [text]
    chunks: List[str] = []
    remaining = text
    while len(remaining) > budget:
        cut = remaining.rfind("\n", 0, budget)
        if cut <= 0:
            cut = budget
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks


# ── Phase 1 ───────────────────────────────────────────────────────────────────

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
    source_type = (inputs.get("source_type") or "").strip()
    source_url  = (inputs.get("source_url") or "").strip()
    sheet_tab   = (inputs.get("sheet_tab") or "").strip()
    context     = (inputs.get("context") or "").strip()

    try:
        await post_message(
            requester_channel,
            f"🔎 Bart validation request received _(Request ID: {request_id})_.\n"
            f"*Context:* {context}\n"
            f"*Source:* {source_url}\n"
            f"Step 1/3 — Fetching source content…",
        )

        sheet_rows = None
        doc_text = None
        html_text = None
        try:
            if source_type == "keywords":
                resolved_tab, sheet_rows = await read_sheet(source_url, sheet_tab)
                await post_message(
                    requester_channel,
                    f"📥 Read tab *{resolved_tab}* — {max(0, len(sheet_rows) - 1)} rows of keywords.",
                )
            elif source_type == "html_url":
                html_text = await read_html_url(source_url)
                await post_message(
                    requester_channel,
                    f"📥 Read hosted page — {len(html_text)} chars after tag-stripping.",
                )
            else:
                doc_text = await read_doc(source_url)
                await post_message(
                    requester_channel,
                    f"📥 Read Google Doc — {len(doc_text)} chars.",
                )
        except Exception as e:
            logger.exception("Failed to read source for %s: %s", request_id, e)
            hint = (
                "Make sure the URL is correct. "
                "Google files must be shared with `bart-validate@robust-limiter-488800-g5.iam.gserviceaccount.com` "
                "(Viewer is enough). HTML URLs must be publicly accessible."
            )
            await post_message(
                requester_channel,
                f"❌ Could not read the source URL _(Request ID: {request_id})_: `{e}`\n_{hint}_",
            )
            return

        content_block = format_content_block(source_type, sheet_rows, doc_text, html_text)

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
            "📨 Step 2/3 — Sent to Bart. I'll post the results in #sem-lp-build-kits when Bart finishes.",
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


# ── Phase 2 ───────────────────────────────────────────────────────────────────

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
    requester_channel  = job["requester_channel"]
    bart_channel       = job["bart_channel"]
    build_kits_channel = job.get("build_kits_channel") or requester_channel
    request_id         = job["request_id"]
    user_id            = job["user_id"]
    inputs             = job["inputs"]
    context            = (inputs.get("context") or "").strip()
    source_url         = (inputs.get("source_url") or "").strip()

    try:
        await post_message(bart_channel, "📖 Collecting Bart's response…", thread_ts=thread_ts)
        messages = await fetch_thread_messages(bart_channel, thread_ts)
        bart_response = (accumulate_bart_brief(messages, bart_user_id) or "").strip()

        thread_link = _slack_archive_link(bart_channel, thread_ts)
        summary_table = extract_summary_table(bart_response)
        counts = count_verdicts(summary_table)
        counts_line = (
            f"{counts['confirmed']} confirmed · "
            f"{counts['conditional']} conditional · "
            f"{counts['exclude']} excluded"
        )

        header = (
            f"✅ *Bart validation complete*\n"
            f"*Request ID:* {request_id}\n"
            f"*Context:* {context}\n"
            f"*Source:* {source_url}\n"
            f"*Requester:* <@{user_id}>\n"
            f"*Result:* {counts_line}\n"
        )
        if thread_link:
            header += f"*Full thread:* {thread_link}\n"

        if summary_table:
            header += f"\n*Summary table:*\n```\n{summary_table}\n```\n"
        else:
            header += "\n_(Bart did not include a parseable summary table — see full response in the thread below.)_\n"

        # Post the digest as the main message; chunk Bart's full prose into threaded replies.
        digest_ts = await post_message(build_kits_channel, header)
        if bart_response:
            full = f"*Bart's full response*\n```\n{bart_response}\n```"
            for chunk in _chunk_for_slack(full):
                await post_message(build_kits_channel, chunk, thread_ts=digest_ts)

        if requester_channel and requester_channel != build_kits_channel:
            await post_message(
                requester_channel,
                f"✅ Validation complete — {counts_line}. Results posted to <#{build_kits_channel}>.",
            )
        await post_message(
            bart_channel,
            f"✅ Validation results posted to <#{build_kits_channel}>.",
            thread_ts=thread_ts,
        )

        jobs.pop(thread_ts, None)
        save_jobs()

    except Exception as e:
        logger.exception("run_bart_validate_from_response (phase 2) failed: %s", e)
        try:
            await post_message(
                requester_channel,
                f"❌ Validation completion failed _(Request ID: {request_id})_: `{e}`",
            )
            await post_message(
                bart_channel,
                f"❌ Posting results failed: `{e}`",
                thread_ts=thread_ts,
            )
        except Exception:
            pass
        jobs.pop(thread_ts, None)
        save_jobs()
