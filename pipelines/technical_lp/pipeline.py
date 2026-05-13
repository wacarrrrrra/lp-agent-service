"""
Technical LP pipeline orchestrator (v3 — grounding-first).

Phase 1 (run_technical_lp_generation) — called from main.py's modal submission handler:
  Modal inputs → post Bart grounding request to SEM_LP_REQUESTS_CHANNEL,
  register JOB awaiting BART_DONE, return.

Phase 2 (run_technical_lp_from_grounding) — called from main.py's /slack/events
  handler when Bart posts BART_DONE in the registered thread:
  Accumulate Bart's grounding → parse TOPIC_FIT verdict.
  • If NOT_A_FIT → surface Bart's reasoning + suggested alternatives, abort doc creation.
  • Else → run outline (with grounding) → full copy → QA → create Google Doc → post URL.
"""
import logging
import re
from typing import Any, Callable, Dict, Optional

from pipelines.technical_lp.stages import (
    run_outline,
    run_full_copy,
    run_qa_pass,
)
from pipelines.technical_lp.gdoc_create import create_technical_lp_doc
from pipelines.technical_lp.bart_brief import build_technical_lp_grounding_prompt

logger = logging.getLogger("uvicorn.error")

_TOPIC_FIT_RE = re.compile(r"TOPIC_FIT\s*[:\-]\s*(STRONG|PARTIAL|NOT_A_FIT)", re.IGNORECASE)


def _parse_topic_fit(grounding: str) -> str:
    """Return 'STRONG', 'PARTIAL', 'NOT_A_FIT', or 'UNKNOWN' from Bart's grounding text."""
    m = _TOPIC_FIT_RE.search(grounding or "")
    if not m:
        return "UNKNOWN"
    return m.group(1).upper()


def _extract_topic_fit_explanation(grounding: str) -> str:
    """Pull the first ~600 chars after the TOPIC_FIT verdict line for context."""
    m = _TOPIC_FIT_RE.search(grounding or "")
    if not m:
        return ""
    start = m.start()
    snippet = (grounding or "")[start : start + 800]
    return snippet.strip()


async def run_technical_lp_generation(
    inputs: Dict[str, Any],
    request_id: str,
    requester_channel: str,
    user_id: str,
    post_message: Callable,
    bart_channel: str,
    jobs: Dict[str, Any],
    save_jobs: Callable,
) -> None:
    """
    Phase 1 of the technical LP pipeline.

    Posts the Bart grounding request to bart_channel and registers a JOB so the event handler
    can pick up Bart's BART_DONE and continue to phase 2. No Claude calls in phase 1.
    """
    search_term = (inputs.get("search_term") or "").strip()

    try:
        await post_message(
            requester_channel,
            f"🚀 Technical LP request received for *{search_term}* "
            f"_(Request ID: {request_id})_.\n"
            f"Step 1/4 — Asking Bart Bot to research the topic and ground the page in real "
            f"DataHub capabilities. This is async; I'll post progress here as it advances.",
        )

        # Post the validation thread starter in Bart's channel
        starter = (
            f"🚀 *Technical LP grounding request*\n"
            f"*Request ID:* {request_id}\n"
            f"*Search term:* {search_term}\n"
            f"*Requester:* <@{user_id}>"
        )
        bart_thread_ts = await post_message(bart_channel, starter)

        # Register the job BEFORE posting the prompt so the event handler can find it
        jobs[bart_thread_ts] = {
            "pipeline": "technical_lp",
            "request_id": request_id,
            "user_id": user_id,
            "requester_channel": requester_channel,
            "bart_channel": bart_channel,
            "inputs": inputs,
            "awaiting": "bart_grounding_technical_lp",
        }
        save_jobs()

        grounding_prompt = build_technical_lp_grounding_prompt(inputs=inputs, request_id=request_id)
        await post_message(bart_channel, grounding_prompt, thread_ts=bart_thread_ts)
        await post_message(
            bart_channel,
            "⏳ Waiting for Bart… pipeline continues automatically after `BART_DONE`.",
            thread_ts=bart_thread_ts,
        )

    except Exception as e:
        logger.exception("run_technical_lp_generation (phase 1) failed: %s", e)
        try:
            await post_message(
                requester_channel,
                f"❌ Technical LP pipeline failed _(Request ID: {request_id})_: `{e}`",
            )
        except Exception:
            pass


async def run_technical_lp_from_grounding(
    job: Dict[str, Any],
    thread_ts: str,
    post_message: Callable,
    fetch_thread_messages: Callable,
    accumulate_bart_brief: Callable,
    bart_user_id: str,
    jobs: Dict[str, Any],
    save_jobs: Callable,
) -> None:
    """
    Phase 2 of the technical LP pipeline. Triggered when Bart posts BART_DONE in a thread
    with awaiting=bart_grounding_technical_lp.

    Accumulates Bart's grounding, checks TOPIC_FIT verdict, then either aborts (NOT_A_FIT) or
    runs the Claude generation stages.
    """
    requester_channel = job["requester_channel"]
    bart_channel = job["bart_channel"]
    request_id = job["request_id"]
    user_id = job["user_id"]
    inputs = job["inputs"]
    search_term = (inputs.get("search_term") or "").strip()

    try:
        # Step 1 — Accumulate Bart's grounding from the thread
        await post_message(
            bart_channel, "📖 Collecting Bart's grounding research…", thread_ts=thread_ts
        )
        messages = await fetch_thread_messages(bart_channel, thread_ts)
        grounding = accumulate_bart_brief(messages, bart_user_id) or ""

        # Step 2 — Check TOPIC_FIT verdict
        verdict = _parse_topic_fit(grounding)
        if verdict == "NOT_A_FIT":
            excerpt = _extract_topic_fit_explanation(grounding)
            await post_message(
                requester_channel,
                f"⚠️ Bart flagged *{search_term}* as not currently a fit for a DataHub LP "
                f"_(Request ID: {request_id})_. Doc creation aborted.\n\n"
                f"*Bart's verdict:*\n```\n{excerpt}\n```\n"
                f"_Reposition the topic or adjust the angle and re-run `/technical-lp`._",
            )
            await post_message(
                bart_channel,
                f"🛑 Pipeline aborted: TOPIC_FIT verdict was NOT_A_FIT.",
                thread_ts=thread_ts,
            )
            jobs.pop(thread_ts, None)
            save_jobs()
            return

        verdict_msg = (
            f"Bart says topic fit is *{verdict}*"
            if verdict in ("STRONG", "PARTIAL")
            else f"Bart did not provide an explicit TOPIC_FIT verdict; proceeding cautiously"
        )

        await post_message(
            requester_channel,
            f"✅ Step 2/4 — Bart's grounding received. {verdict_msg}.",
        )

        # Step 3 — Generate from grounding
        await post_message(requester_channel, "📐 Step 3/4 — Building outline from Bart's grounding…")
        outline = await run_outline(inputs, grounding=grounding)

        await post_message(requester_channel, "✍️ Step 3/4 — Writing full copy…")
        copy = await run_full_copy(outline, inputs, grounding=grounding)

        await post_message(requester_channel, "🔍 Step 3/4 — Running style QA pass…")
        copy, qa_issues = await run_qa_pass(copy, inputs)

        # Step 4 — Create the Google Doc
        await post_message(requester_channel, "📄 Step 4/4 — Creating Google Doc…")
        title = f"{request_id} — {search_term} — Technical LP"
        gdoc_url = await create_technical_lp_doc(title=title, markdown_body=copy)

        report = (
            f"✅ Technical LP ready: {gdoc_url}\n"
            f"_Request ID:_ `{request_id}` · _Requester:_ <@{user_id}>\n"
            f"_Topic fit:_ {verdict} · _QA auto-fixes:_ {len(qa_issues)}"
        )
        await post_message(requester_channel, report)
        await post_message(
            bart_channel,
            f"✅ Doc created from Bart's grounding: {gdoc_url}",
            thread_ts=thread_ts,
        )

        jobs.pop(thread_ts, None)
        save_jobs()

    except Exception as e:
        logger.exception("run_technical_lp_from_grounding (phase 2) failed: %s", e)
        try:
            await post_message(
                requester_channel,
                f"❌ Technical LP generation failed _(Request ID: {request_id})_: `{e}`",
            )
            await post_message(
                bart_channel,
                f"❌ Generation from grounding failed: `{e}`",
                thread_ts=thread_ts,
            )
        except Exception:
            pass
        jobs.pop(thread_ts, None)
        save_jobs()
