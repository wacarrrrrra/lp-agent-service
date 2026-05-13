"""
Technical LP pipeline orchestrator (two-phase, with Bart validation).

Phase 1 (run_technical_lp_generation) — called from main.py's modal submission handler:
  Modal inputs → outline → full copy → QA → post to Bart in SEM_LP_REQUESTS_CHANNEL,
  register JOB awaiting BART_DONE, return.

Phase 2 (run_technical_lp_post_bart) — called from main.py's /slack/events handler
  when Bart posts BART_DONE in the registered thread:
  Accumulate Bart's feedback → run_bart_fix_pass → create Google Doc → post URL to
  the original requester_channel.
"""
import logging
from typing import Any, Callable, Dict

from pipelines.technical_lp.stages import (
    run_outline,
    run_full_copy,
    run_qa_pass,
    run_bart_fix_pass,
)
from pipelines.technical_lp.gdoc_create import create_technical_lp_doc
from pipelines.technical_lp.bart_validation import build_technical_lp_validation_prompt

logger = logging.getLogger("uvicorn.error")


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

    Generates the LP copy (outline → full copy → QA), then hands off to Bart for technical
    validation by posting to a new thread in bart_channel. Registers a JOB so the event
    handler can pick up Bart's BART_DONE and continue to phase 2.
    """
    search_term = (inputs.get("search_term") or "").strip()

    try:
        await post_message(
            requester_channel,
            f"🚀 Technical LP generation started for *{search_term}* "
            f"_(Request ID: {request_id})_. I'll post the Google Doc link here when it's ready.",
        )

        await post_message(requester_channel, "📐 Step 1/5 — Building outline…")
        outline = await run_outline(inputs)

        await post_message(requester_channel, "✍️ Step 2/5 — Writing full copy…")
        copy = await run_full_copy(outline, inputs)

        await post_message(requester_channel, "🔍 Step 3/5 — Running QA pass…")
        copy, qa_issues = await run_qa_pass(copy, inputs)

        await post_message(
            requester_channel,
            f"🤖 Step 4/5 — Sending to Bart for technical validation… "
            f"(Bart will review against the DataHub codebase. This step is async.)"
            + (f"\n_QA auto-fixes applied:_ {len(qa_issues)}" if qa_issues else ""),
        )

        # Post the validation thread starter in Bart's channel
        starter = (
            f"🚀 *Technical LP validation request*\n"
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
            "copy": copy,
            "qa_issues_count": len(qa_issues),
            "awaiting": "bart_validation_technical_lp",
        }
        save_jobs()

        # Now @-mention Bart with the validation request
        validation_prompt = build_technical_lp_validation_prompt(
            copy=copy, inputs=inputs, request_id=request_id
        )
        await post_message(bart_channel, validation_prompt, thread_ts=bart_thread_ts)
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


async def run_technical_lp_post_bart(
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
    Phase 2 of the technical LP pipeline. Triggered by the /slack/events handler when
    Bart posts BART_DONE in a thread with awaiting=bart_validation_technical_lp.

    Accumulates Bart's feedback, applies fixes via Claude, creates the Google Doc,
    posts the URL to the original requester_channel.
    """
    requester_channel = job["requester_channel"]
    bart_channel = job["bart_channel"]
    request_id = job["request_id"]
    user_id = job["user_id"]
    inputs = job["inputs"]
    copy = job["copy"]
    qa_issues_count = job.get("qa_issues_count", 0)
    search_term = (inputs.get("search_term") or "").strip()

    try:
        # Step 1 — Accumulate Bart's feedback from the thread
        await post_message(
            bart_channel, "📖 Collecting Bart's feedback…", thread_ts=thread_ts
        )
        messages = await fetch_thread_messages(bart_channel, thread_ts)
        bart_feedback = accumulate_bart_brief(messages, bart_user_id) or ""

        # Step 2 — Apply Bart's fixes
        await post_message(
            requester_channel,
            f"🛠️ Step 5/5 — Applying Bart's technical fixes _(Request ID: {request_id})_…",
        )
        fixed_copy = await run_bart_fix_pass(copy, bart_feedback, inputs)

        # Step 3 — Create the Google Doc
        await post_message(requester_channel, "📄 Creating Google Doc…")
        title = f"{request_id} — {search_term} — Technical LP"
        gdoc_url = await create_technical_lp_doc(title=title, markdown_body=fixed_copy)

        # Step 4 — Final report
        validated_msg = (
            "All claims validated"
            if "all claims validated" in bart_feedback.lower()
            else f"{bart_feedback.count('ISSUE:')} issue(s) flagged + fixed"
        )
        report = (
            f"✅ Technical LP ready: {gdoc_url}\n"
            f"_Request ID:_ `{request_id}` · _Requester:_ <@{user_id}>\n"
            f"_QA auto-fixes:_ {qa_issues_count} · _Bart validation:_ {validated_msg}"
        )
        await post_message(requester_channel, report)
        await post_message(
            bart_channel,
            f"✅ Doc created: {gdoc_url}",
            thread_ts=thread_ts,
        )

        # Clean up
        jobs.pop(thread_ts, None)
        save_jobs()

    except Exception as e:
        logger.exception("run_technical_lp_post_bart (phase 2) failed: %s", e)
        try:
            await post_message(
                requester_channel,
                f"❌ Technical LP post-Bart pipeline failed _(Request ID: {request_id})_: `{e}`",
            )
            await post_message(
                bart_channel,
                f"❌ Post-Bart pipeline failed: `{e}`",
                thread_ts=thread_ts,
            )
        except Exception:
            pass
        jobs.pop(thread_ts, None)
        save_jobs()
