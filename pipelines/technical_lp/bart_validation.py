"""
Bart Bot validation prompt for the /technical-lp pipeline.

After Claude generates the QA'd LP copy, the pipeline posts the copy to
SEM_LP_REQUESTS_CHANNEL with this prompt @-mentioning Bart. Bart (which has
DataHub codebase access) reviews technical claims and replies with issues +
BART_DONE. The event handler picks up BART_DONE and triggers the fix pass.
"""
import os

BART_USER_ID = os.getenv("BART_USER_ID", "")

_MAX_INLINE_COPY_CHARS = 38000  # Slack message limit is 40k; leave headroom for the prompt scaffold


def build_technical_lp_validation_prompt(copy: str, inputs: dict, request_id: str) -> str:
    """Compose the @Bart message asking for technical validation of the LP copy."""
    search_term = (inputs.get("search_term") or "").strip()
    audience = (inputs.get("primary_audience") or "").strip()

    copy_excerpt = copy
    if len(copy_excerpt) > _MAX_INLINE_COPY_CHARS:
        copy_excerpt = copy_excerpt[:_MAX_INLINE_COPY_CHARS] + "\n\n[copy truncated for Slack length limit]"

    return (
        f"<@{BART_USER_ID}> Please technically validate this DataHub landing page copy.\n\n"
        f"*Request ID:* {request_id}\n"
        f"*Topic:* {search_term}\n"
        f"*Audience:* {audience}\n\n"
        "Review the copy below using your access to the DataHub codebase, and flag any of:\n"
        "1. Claims about DataHub features or integrations that aren't accurate (don't exist, "
        "don't work the way described, or are out of date)\n"
        "2. Customer brands, testimonials, or quotes that shouldn't be cited\n"
        "3. Certifications, SLAs, or compliance claims that are wrong or unverifiable\n"
        "4. Architecture or technical details that misrepresent how DataHub actually works\n"
        "5. Quantified benchmarks or stats that look invented\n\n"
        "For each issue, respond in this format:\n"
        "- ISSUE: [what's wrong]\n"
        "- LOCATION: [quote the offending text verbatim]\n"
        "- FIX: [suggested correction or removal]\n\n"
        "If everything checks out, reply: All claims validated.\n\n"
        "When fully done reviewing, reply `BART_DONE` on its own line.\n\n"
        "---\n"
        "COPY:\n\n"
        f"{copy_excerpt}"
    )
