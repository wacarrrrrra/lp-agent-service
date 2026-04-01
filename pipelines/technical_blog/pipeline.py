"""
Technical blog pipeline orchestrator.

Entry points called from main.py:
  - start_tech_blog_job(...) — handles /technical-blog slash command
  - run_tech_blog_generation(...) — called when BART_DONE detected for a tech_blog job
"""
import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from pipelines.technical_blog.bart_brief import build_bart_message
from pipelines.technical_blog.stages import run_outline, run_full_draft, run_qa_pass, parse_yaml_front_matter
from pipelines.technical_blog.image_cycling import get_and_advance_image_index, get_image_filenames
from pipelines.technical_blog.gdoc_create import create_blog_draft_doc
from pipelines.technical_blog.wp_publish import publish_draft
from pipelines.technical_blog.qa_report import format_qa_report

logger = logging.getLogger("uvicorn.error")

BART_USER_ID = os.getenv("BART_USER_ID", "")
SEM_LP_REQUESTS_CHANNEL = os.getenv("SEM_LP_REQUESTS_CHANNEL", "")
BLOG_PUBLISHER_CHANNEL = os.getenv("BLOG_PUBLISHER_CHANNEL", "")


def _generate_job_id() -> str:
    return datetime.now().strftime("BLOG-%Y%m%d-%H%M")


async def start_tech_blog_job(
    topic: str,
    requester_channel: str,
    user_id: str,
    post_message: Callable,
    jobs: Dict[str, Any],
    save_jobs: Callable,
) -> None:
    """
    Acknowledge the /technical-blog command, post the BartBot brief prompt,
    and register the job so the event handler can pick it up on BART_DONE.
    """
    bart_channel = SEM_LP_REQUESTS_CHANNEL
    blog_channel = BLOG_PUBLISHER_CHANNEL or requester_channel
    job_id = _generate_job_id()

    try:
        await post_message(
            blog_channel,
            f"📝 Got it <@{user_id}> — drafting a brief for *{topic}*. "
            f"I'll post the WordPress draft here when ready. _(Job ID: {job_id})_",
        )

        # Open a thread in the private Bart channel
        starter = (
            f"🚀 *Engineering blog request started*\n"
            f"*Job ID:* {job_id}\n"
            f"*Topic:* {topic}\n"
            f"*Requested by:* <@{user_id}>"
        )
        bart_thread_ts = await post_message(bart_channel, starter)

        # Register job before posting the prompt so the event handler can find it
        jobs[bart_thread_ts] = {
            "pipeline": "tech_blog",
            "job_id": job_id,
            "topic": topic,
            "bart_channel": bart_channel,
            "requester_channel": blog_channel,
            "user_id": user_id,
            "awaiting": "bart",
        }
        save_jobs()

        # Post BartBot brief prompt in the thread
        await post_message(bart_channel, build_bart_message(topic), thread_ts=bart_thread_ts)
        await post_message(
            bart_channel,
            "⏳ Waiting for Bart… pipeline continues automatically after `BART_DONE`.",
            thread_ts=bart_thread_ts,
        )

    except Exception as e:
        logger.exception("start_tech_blog_job failed: %s", e)
        try:
            await post_message(blog_channel, f"❌ Failed to start engineering blog pipeline: `{e}`")
        except Exception:
            pass


async def run_tech_blog_generation(
    job: Dict[str, Any],
    thread_ts: str,
    trigger_text: str,
    post_message: Callable,
    fetch_thread_messages: Callable,
    accumulate_bart_brief: Callable,
    jobs: Dict[str, Any],
    save_jobs: Callable,
) -> None:
    """
    Full generation pipeline triggered when BART_DONE is detected.
    Runs outline → draft → QA → WP publish → Slack report.
    """
    bart_channel = job["bart_channel"]
    requester_channel = job["requester_channel"]
    topic = job.get("topic", "")
    job_id = job.get("job_id", "")

    try:
        # Step 1 — Collect full Bart brief from thread
        await post_message(bart_channel, "📖 Collecting brief from thread…", thread_ts=thread_ts)
        messages = await fetch_thread_messages(bart_channel, thread_ts)
        bart_brief = accumulate_bart_brief(messages, BART_USER_ID) or trigger_text

        # Step 2 — Outline
        await post_message(bart_channel, "📐 Step 1/3: Building outline…", thread_ts=thread_ts)
        outline, seo_json = await run_outline(bart_brief)
        diagram_prompt: Optional[str] = seo_json.get("diagram_prompt") or None

        # Step 3 — Full draft
        await post_message(bart_channel, "✍️ Step 2/3: Writing full draft…", thread_ts=thread_ts)
        draft = await run_full_draft(outline, bart_brief)

        # Step 4 — QA pass (up to 2 iterations)
        await post_message(bart_channel, "🔍 Step 3/3: Running QA…", thread_ts=thread_ts)
        draft, qa_issues = await run_qa_pass(draft)
        if qa_issues:
            # One more pass if issues were found
            draft, qa_issues = await run_qa_pass(draft)

        # Step 5 — Parse metadata from YAML front matter
        meta, body_md = parse_yaml_front_matter(draft)
        title = meta.get("title") or seo_json.get("title") or topic
        slug = meta.get("slug") or seo_json.get("slug") or ""
        meta_description = meta.get("meta_description") or seo_json.get("meta_description") or ""
        focus_keyword = meta.get("focus_keyword") or seo_json.get("focus_keyword") or ""
        category = meta.get("category") or "Engineering"

        # Step 6 — Assign cycling images
        idx = get_and_advance_image_index(slug=slug)
        idx_str = str(idx).zfill(2)
        hero_fn, featured_fn, socialcard_fn = get_image_filenames(idx)

        # Step 7 — Create Google Doc in Blog Drafts folder
        await post_message(bart_channel, "📄 Creating Google Doc draft…", thread_ts=thread_ts)
        gdoc_url = await create_blog_draft_doc(
            title=title,
            meta_description=meta_description,
            slug=slug,
            focus_keyword=focus_keyword,
            markdown_body=body_md,
            diagram_prompt=diagram_prompt,
        )

        # Step 8 — Publish WP draft
        await post_message(bart_channel, "📤 Publishing WordPress draft…", thread_ts=thread_ts)
        post_id, edit_url = await publish_draft(
            title=title,
            slug=slug,
            meta_description=meta_description,
            focus_keyword=focus_keyword,
            category=category,
            markdown_body=body_md,
            hero_filename=hero_fn,
            featured_filename=featured_fn,
            socialcard_filename=socialcard_fn,
            diagram_prompt=diagram_prompt,
        )

        # Step 9 — Post QA report to #blog-publisher
        report = format_qa_report(
            title=title,
            gdoc_url=gdoc_url,
            edit_url=edit_url,
            qa_issues=qa_issues,
            hero_filename=hero_fn,
            featured_filename=featured_fn,
            socialcard_filename=socialcard_fn,
            idx_str=idx_str,
            diagram_prompt=diagram_prompt,
        )
        await post_message(requester_channel, report)

        # Internal confirmation in Bart thread
        await post_message(
            bart_channel,
            f"✅ Draft published: {edit_url}",
            thread_ts=thread_ts,
        )

        # Clean up job
        jobs.pop(thread_ts, None)
        save_jobs()

    except Exception as e:
        logger.exception("run_tech_blog_generation failed: %s", e)
        try:
            await post_message(
                requester_channel,
                f"❌ Engineering blog pipeline failed _(Job ID: {job_id})_: `{e}`",
            )
            await post_message(
                bart_channel, f"❌ Generation failed: `{e}`", thread_ts=thread_ts
            )
        except Exception:
            pass
        jobs.pop(thread_ts, None)
        save_jobs()
