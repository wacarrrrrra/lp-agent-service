"""
Bart Bot grounding-request prompt for the /technical-lp pipeline.

In v3 the pipeline is grounding-first: Bart (which has DataHub codebase access)
researches the topic and produces an authoritative technical brief. Claude then
generates the LP copy using ONLY the facts Bart provided — no invention, no
extrapolation beyond Bart's grounding.

Bart's response must include a TOPIC_FIT verdict on the first line. If
NOT_A_FIT, the pipeline aborts doc creation and surfaces Bart's verdict to the
requester so the topic can be repositioned before wasted Claude generation.
"""
import os

BART_USER_ID = os.getenv("BART_USER_ID", "")


def build_technical_lp_grounding_prompt(inputs: dict, request_id: str) -> str:
    """Compose the @Bart message asking for technical grounding research."""
    search_term = (inputs.get("search_term") or "").strip()
    audience = (inputs.get("primary_audience") or "").strip()
    intent = (inputs.get("intent") or "").strip()
    primary_cta = (inputs.get("primary_cta") or "").strip()

    secondary_keywords = inputs.get("secondary_keywords") or []
    if isinstance(secondary_keywords, list):
        secondary_str = ", ".join(secondary_keywords) if secondary_keywords else "—"
    else:
        secondary_str = str(secondary_keywords) or "—"

    optional_blocks = []
    for key, label in [
        ("offer", "Offer"),
        ("must_include", "Must include"),
        ("must_not_say", "Must not say"),
    ]:
        val = (inputs.get(key) or "").strip()
        if val:
            optional_blocks.append(f"*{label}:* {val}")
    optional_section = "\n".join(optional_blocks)

    return (
        f"<@{BART_USER_ID}> Technical grounding research for a DataHub landing page.\n\n"
        f"*Request ID:* {request_id}\n"
        f"*Topic:* {search_term}\n"
        f"*Audience:* {audience}\n"
        f"*Intent:* {intent}\n"
        f"*Primary CTA:* {primary_cta}\n"
        f"*Secondary keywords:* {secondary_str}\n"
        + (f"{optional_section}\n" if optional_section else "")
        + "\n"
        "Using your access to the DataHub codebase, produce a TECHNICAL GROUNDING document "
        "that the writer will use to generate the landing page copy. Be specific. Cite only "
        "features and integrations that exist today. Do not extrapolate beyond what is built "
        "and shipped.\n\n"
        "## REQUIRED OUTPUT FORMAT\n\n"
        "### 1. TOPIC_FIT VERDICT (required, first content line)\n"
        "Use exactly one of these labels:\n"
        "- `TOPIC_FIT: STRONG` — DataHub has direct, shipped capabilities for this topic\n"
        "- `TOPIC_FIT: PARTIAL` — DataHub has adjacent capabilities; the LP needs to reframe the angle\n"
        "- `TOPIC_FIT: NOT_A_FIT` — DataHub does not currently support this topic; writing the LP would misrepresent the product\n"
        "If PARTIAL or NOT_A_FIT, explain why in 1–2 sentences and suggest 1–2 alternative angles "
        "that ARE strong fits.\n\n"
        "### 2. WHAT DATAHUB DOES FOR THIS TOPIC\n"
        "- Specific shipped features by name\n"
        "- Concrete capabilities (what does it literally do? — no vague \"powers\" or \"enables\")\n"
        "- Limit to what exists in the codebase today\n\n"
        "### 3. REAL INTEGRATIONS\n"
        "- Named integrations and connectors that actually exist for this topic\n"
        "- APIs and SDKs that apply (GraphQL, REST, Python SDK, OpenLineage, etc.)\n"
        "- Skip integrations that are roadmap-only or hypothetical\n\n"
        "### 4. ARCHITECTURE / COMPONENTS\n"
        "- Internal services involved (named: GMS, MAE consumer, MCE consumer, etc.)\n"
        "- Deployment paths (Helm chart, Cloud, Docker Compose) — what's actually supported\n"
        "- Data flow specifics\n\n"
        "### 5. LEGITIMATE CLAIMS\n"
        "- Quantified claims with source (IDC studies, customer case studies, etc.)\n"
        "- Customer references that can be cited by name (only if verified)\n"
        "- Compliance / certifications that are accurate (SOC 2 Type II, SSO standards, etc.)\n"
        "- Open-source positioning when applicable (license, community size, downloads)\n\n"
        "### 6. HONEST GAPS / LIMITATIONS\n"
        "- What DOESN'T work for this topic\n"
        "- What requires manual setup, custom code, or roadmap items\n"
        "- Common misconceptions to avoid\n\n"
        "### 7. FAQ-WORTHY ENGINEERING QUESTIONS\n"
        "3–5 questions a technical evaluator would actually ask about this topic, each with a "
        "1–2 sentence factual answer grounded in what DataHub actually does.\n\n"
        "---\n"
        "When fully done, reply `BART_DONE` on its own line — the pipeline will not continue "
        "until it sees this signal."
    )
