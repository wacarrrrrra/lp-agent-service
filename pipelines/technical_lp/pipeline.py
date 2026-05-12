"""
Technical LP pipeline orchestrator.

Entry point called from main.py's _handle_interactivity when the technical_lp_modal
is submitted: run_technical_lp_generation(...).

Modal-driven (synchronous from kickoff — no Bart wait, no JOBS persistence).
"""
import logging
from typing import Any, Callable, Dict

from pipelines.technical_lp.stages import run_outline, run_full_copy, run_qa_pass
from pipelines.technical_lp.gdoc_create import create_technical_lp_doc

logger = logging.getLogger("uvicorn.error")


async def run_technical_lp_generation(
    inputs: Dict[str, Any],
    request_id: str,
    requester_channel: str,
    user_id: str,
    post_message: Callable,
) -> None:
    """
    Full /technical-lp generation pipeline. Triggered from the modal submission.

    Posts progress to the requester_channel, runs the three Claude stages,
    creates the Google Doc in the Technical LP Shared Drive folder, and posts
    the URL back to the channel.
    """
    search_term = (inputs.get("search_term") or "").strip()
    title = f"{request_id} — {search_term} — Technical LP"

    try:
        await post_message(
            requester_channel,
            f"🚀 Technical LP generation started for *{search_term}* "
            f"_(Request ID: {request_id})_. I'll post the Google Doc link here when it's ready.",
        )

        await post_message(requester_channel, "📐 Step 1/3 — Building outline…")
        outline = await run_outline(inputs)

        await post_message(requester_channel, "✍️ Step 2/3 — Writing full copy…")
        copy = await run_full_copy(outline, inputs)

        await post_message(requester_channel, "🔍 Step 3/3 — Running QA pass…")
        copy, qa_issues = await run_qa_pass(copy, inputs)

        await post_message(requester_channel, "📄 Creating Google Doc…")
        gdoc_url = await create_technical_lp_doc(title=title, markdown_body=copy)

        report = (
            f"✅ Technical LP ready: {gdoc_url}\n"
            f"_Request ID:_ `{request_id}` · _Requester:_ <@{user_id}>\n"
            f"_QA issues auto-fixed:_ {len(qa_issues)}"
        )
        await post_message(requester_channel, report)

    except Exception as e:
        logger.exception("run_technical_lp_generation failed: %s", e)
        try:
            await post_message(
                requester_channel,
                f"❌ Technical LP pipeline failed _(Request ID: {request_id})_: `{e}`",
            )
        except Exception:
            pass
