"""
Claude API stages for the /technical-lp pipeline.

Three stages:
  1. run_outline    — produces a structured outline of the 10-section LP arc,
                      letting Claude drop/reshape sections based on the brief.
  2. run_full_copy  — writes the full 2,500–3,500 word LP copy as clean markdown.
  3. run_qa_pass    — checks LP-specific rules and auto-applies fixes.

Style rules ported from ~/lp-agent/.claude/commands/technical-lp.md, which is the
human-readable source of truth (used by the local CLI dev/testing flow).
"""
import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Tuple

from anthropic import Anthropic

logger = logging.getLogger("uvicorn.error")

_ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

_SYSTEM_PROMPT = (
    "You are a senior technical writer at DataHub. You write deep technical landing pages "
    "for data engineers, platform engineers, and technical buyers. Your writing is concrete, "
    "specific, and opinionated — never generic. You name actual integrations, APIs, SQL constructs, "
    "and architecture components. You quantify claims or omit them. You write in sentence case for "
    "all headings except the page title. You never use exclamation marks. You write in active voice."
)

_LP_STYLE_RULES = """
## Technical landing page rules — follow strictly

### Structure (10-section starting template)
Default to this section arc, in order. Allow the brief to drop or reshape sections when
the campaign clearly doesn't need one (e.g. drop Deployment & Architecture for a non-infra
topic; expand Solution into more sub-features when the brief is feature-heavy). Do not invent
sections the brief doesn't support.

1. Hero — H1 + a 2–3 sentence subhead naming concrete capabilities, not generic value props.
2. Social proof — one short paragraph naming 5–10 customer brands from the brief (skip if none provided).
3. Problem section — 3–4 named failure modes as H3 + 1 paragraph each. Concrete failure scenarios with named tools, not abstract pain.
4. Solution — 3–5 H3 sub-features. Each names the APIs, SDKs, SQL constructs, file formats, or protocols involved.
5. Implementation process — typically 3 steps, each naming specific tools and protocols.
6. Deployment & architecture — name internal components, deployment options (Kubernetes/Helm, Docker, managed cloud), security/compliance (SSO, SOC 2, VPC, SLA). Drop if brief is strictly feature-focused.
7. Customer testimonial — one Gartner Peer Insights-style quote (named role + industry + segment), only if brief supplies one.
8. FAQ — 4–6 engineering-grade questions, ~120–180 words per answer. Include architecture specifics, integration mechanisms, and honest gap-acknowledgment.
9. CTA — restate the value, promise a consultation scoped to the prospect's stack.
10. Footer note — single short paragraph: copyright + final CTA reference.

### Depth markers (required wherever the brief supports them)
- Named integrations by product (Snowflake, BigQuery, dbt, Airflow, Looker, Tableau, etc.)
- Named APIs / SDKs (GraphQL, REST, Python SDK, OpenLineage) as first-class integration mechanisms
- Specific technical constructs handled (SQL dialects, query patterns, file formats, protocols)
- Quantified benchmarks (cite source — IDC, customer case study, etc.)
- Open-source positioning when relevant (license, community size, downloads)
- Compliance / operational specifics (SOC 2 Type II, SSO standards, SLA percentages, VPC posture)
- Honest acknowledgment of day-one gaps and how they're filled

### Copy rules
- Word count: 2,500–3,500 words total (body only, excludes the H1 title)
- Primary search term appears verbatim in: H1, first 100 words, at least one H2, and the FAQ section
- Sentence case for all H2 and H3 headings (H1 may be Title Case)
- No exclamation marks anywhere
- No em dashes (—) or en dashes (–). Use commas, parentheses, or " - " for clarity.
- Active voice throughout
- Numbers one through nine spelled out in body text; numerals for 10+
- Use "and" not "&"
- No weasel words — quantify or omit ("many organizations", "significantly", "increasingly", "growing number of", "in today's", "as organizations scale", "it's no secret", "as teams grow")
- No invented metrics, customer logos, certifications, or technical claims not in the brief
- Honor the "Must include" inputs verbatim where they fit naturally
- Avoid anything in the "Must not say" inputs
""".strip()


_QA_SYSTEM_PROMPT = (
    "You are a copy editor reviewing technical landing page copy against a strict style rulebook. "
    "Be precise. List only real violations — do not flag things that are correct."
)

_QA_RULES = """Check the technical landing page copy below against these rules. Return a JSON array of issues:

[
  {"rule": "rule name", "location": "quote the offending text", "fix": "suggested correction"}
]

Rules:
1. No exclamation marks anywhere
2. No em dashes (—) or en dashes (–)
3. All H2 and H3 are sentence case (first word capitalized, rest lowercase unless proper noun)
4. Proper nouns exempt: AI, DataHub, API, SQL, AWS, GCP, Azure, Slack, GitHub, Snowflake, BigQuery, dbt, Databricks, Kubernetes, Helm, Docker, OpenLineage, Looker, Tableau, Airflow, Power BI, Spark, Redshift, Kafka, SOC, SSO, OIDC, SAML, VPC, JSON
5. No weasel words: "many organizations", "significantly", "increasingly", "growing number of", "in today's", "as organizations scale", "it's no secret", "as teams grow", "in the world of"
6. Active voice — flag passive constructions ("is configured by", "was built by", "are managed by") that should be active
7. Numbers one through nine spelled out in body text (not in headings, lists, or code-like contexts)
8. Use "and" not "&" in body text
9. Primary search term must appear verbatim in: the H1, the first 100 words, at least one H2, and the FAQ section
10. No invented technical claims — flag any specific product names, customer brands, SOC certifications, or quantified benchmarks that look made up (the brief is the source of truth)
11. Word count target: 2,500–3,500 words in the body. Flag if obviously outside this range.

Return only the JSON array. If there are no issues, return []."""


def _claude_sync(system: str, user: str, max_tokens: int = 8000) -> str:
    client = Anthropic(api_key=_ANTHROPIC_KEY)
    msg = client.messages.create(
        model=_CLAUDE_MODEL,
        max_tokens=max_tokens,
        temperature=0.2,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(
        block.text for block in msg.content if getattr(block, "type", None) == "text"
    ).strip()


async def _claude(system: str, user: str, max_tokens: int = 8000) -> str:
    return await asyncio.to_thread(_claude_sync, system, user, max_tokens)


def _strip_fences(raw: str) -> str:
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    return re.sub(r"\s*```$", "", raw.strip())


def _strip_markdown_fence(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:markdown|md)?\s*\n", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\n```\s*$", "", raw)
    return raw.strip()


def _normalize_dashes(text: str) -> str:
    """Strip em/en dashes Claude may slip past the rule."""
    return text.replace("—", " ").replace("–", "-")


def _format_inputs(inputs: Dict[str, Any]) -> str:
    """Render the modal inputs as a structured brief for the prompts."""
    parts = [
        f"Primary search term: {inputs.get('search_term', '')}",
        f"Primary CTA: {inputs.get('primary_cta', '')}",
        f"Intent: {inputs.get('intent', '')}",
        f"Primary audience: {inputs.get('primary_audience', '')}",
    ]
    secondary = inputs.get("secondary_keywords") or []
    if isinstance(secondary, list):
        secondary_str = ", ".join(secondary) if secondary else "(none)"
    else:
        secondary_str = str(secondary) or "(none)"
    parts.append(f"Secondary keywords: {secondary_str}")
    for key, label in [
        ("offer", "Offer"),
        ("must_include", "Must include"),
        ("must_not_say", "Must not say"),
    ]:
        val = (inputs.get(key) or "").strip()
        if val:
            parts.append(f"{label}:\n{val}")
    return "\n".join(parts)


async def run_outline(inputs: Dict[str, Any]) -> str:
    """Stage 1: produce a detailed outline of the technical LP."""
    user_prompt = f"""Produce a detailed outline for a technical landing page.

{_LP_STYLE_RULES}

## Your task
Build the outline as a markdown document. For each section in the 10-section template:
- The H2 heading (sentence case — primary search term should appear in at least one H2)
- 3–6 bullet points outlining what the section will say
- Any H3 sub-headings within the section (e.g. named failure modes under Problem, sub-features under Solution, FAQ questions under FAQ)
- Notes on which specific integrations, APIs, technical constructs, or benchmarks to name (drawing only from the brief)

If a section doesn't fit the brief, drop it and note why.
If a section needs to be expanded, add the additional H3s.

## Brief
{_format_inputs(inputs)}

Return the outline only — no preamble, no explanation."""

    return await _claude(_SYSTEM_PROMPT, user_prompt, max_tokens=4000)


async def run_full_copy(outline: str, inputs: Dict[str, Any]) -> str:
    """Stage 2: write the full LP copy from the outline. Returns markdown."""
    user_prompt = f"""Write the full technical landing page copy from the outline below. Follow ALL style rules carefully.

{_LP_STYLE_RULES}

## Output format
Clean markdown:
- Single `# ` H1 at the top (the page title) — Title Case allowed
- `## ` H2 for each top-level section
- `### ` H3 for sub-sections
- Body paragraphs as plain text
- Bullet lists as `- ` lines
- No shortcodes, no YAML front matter, no code blocks
- Aim for 2,500–3,500 words in the body

## Outline
{outline}

## Brief
{_format_inputs(inputs)}

Return only the markdown — no preamble, no explanation."""

    draft = await _claude(_SYSTEM_PROMPT, user_prompt, max_tokens=12000)
    draft = _strip_markdown_fence(draft)
    draft = _normalize_dashes(draft)
    return draft


async def run_qa_pass(copy: str, inputs: Dict[str, Any]) -> Tuple[str, List[Dict[str, str]]]:
    """Stage 3: QA pass. Auto-applies fixes. Returns (corrected_copy, issues_list)."""
    primary_search_term = inputs.get("search_term", "")
    user_prompt = f"""{_QA_RULES}

Primary search term (for rule 9): {primary_search_term}

COPY:
{copy}"""

    raw = await _claude(_QA_SYSTEM_PROMPT, user_prompt, max_tokens=3000)
    raw = _strip_fences(raw)

    issues: List[Dict[str, str]] = []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            issues = parsed
    except Exception:
        logger.warning("QA pass returned non-JSON: %s", raw[:200])

    if not issues:
        return copy, []

    fix_prompt = f"""Apply all the fixes below to the technical landing page copy. Return the COMPLETE corrected copy in markdown. Return only the corrected copy — no preamble.

ISSUES:
{json.dumps(issues, indent=2)}

COPY:
{copy}"""
    corrected = await _claude(_SYSTEM_PROMPT, fix_prompt, max_tokens=12000)
    corrected = _strip_markdown_fence(corrected)
    corrected = _normalize_dashes(corrected)
    return corrected, issues
