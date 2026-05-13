"""
Claude API stages for the /technical-lp pipeline (v3 — grounding-first).

Three stages:
  1. run_outline    — produces a structured outline of the 10-section LP arc,
                      grounded in the Bart technical research brief.
  2. run_full_copy  — writes the full 2,500–3,500 word LP copy from outline +
                      Bart's grounding. Claude is told to use ONLY the technical
                      claims, integrations, capabilities, and customer references
                      that Bart provided. No invention.
  3. run_qa_pass    — checks LP-specific style/structure rules and auto-applies fixes.

Reference docs (SEM-LP-Structure.md, datahub-editorial-style.md, brand-guidelines.md,
SEO-Best-Practices.md) are loaded at module init and injected into the outline + full-copy
prompts with Anthropic prompt caching, so repeat runs amortize the ~15K-token cost. The
reference docs cover style/voice/structure; Bart's grounding is the source of truth for
product facts.

The technical-LP-specific structural rules below (_LP_STYLE_RULES) supplement the reference
docs with rules unique to this pipeline: the 10-section arc, depth markers, output format,
and brief-specific constraints.
"""
import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from anthropic import Anthropic

logger = logging.getLogger("uvicorn.error")

_ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# Resolve to lp-agent-service/ from stages.py → technical_lp → pipelines → lp-agent-service
_SERVICE_DIR = Path(__file__).resolve().parent.parent.parent

_REFERENCE_DOC_FILES = [
    (
        "SEM-LP-Structure.md",
        "DataHub SEM Landing Page Structure Template "
        "(NOTE: this doc is written for HTML SEM landing pages. Apply ONLY the copy constraints, "
        "primary-search-term placement rules, intent/CTA mapping, and section structure principles. "
        "IGNORE HubSpot form embedding, CSS class names, and HTML markup — this pipeline outputs a "
        "Google Doc, not HTML.)",
    ),
    ("datahub-editorial-style.md", "DataHub Editorial Style Guide (voice, tone, grammar, capitalization)"),
    ("brand-guidelines.md", "DataHub Brand Guidelines (voice + SEO/AEO writing rules)"),
    ("SEO-Best-Practices.md", "Writing in 2026: SEO/AEO Best Practices"),
]


def _load_reference_docs() -> str:
    """Concatenate the 4 reference docs into one prompt block. Done once at module init."""
    parts: List[str] = []
    for filename, header in _REFERENCE_DOC_FILES:
        path = _SERVICE_DIR / filename
        if not path.exists():
            logger.warning("technical_lp reference doc not found: %s", path)
            continue
        try:
            content = path.read_text()
        except Exception as e:
            logger.warning("Failed reading reference doc %s: %s", path, e)
            continue
        parts.append(f"# === {header} ===\n\n{content}\n")
    return "\n".join(parts)


_REFERENCE_DOCS = _load_reference_docs()


_SYSTEM_PROMPT = (
    "You are a senior technical writer at DataHub. You write deep technical landing pages "
    "for data engineers, platform engineers, and technical buyers.\n\n"
    "CRITICAL RULE — TECHNICAL ACCURACY:\n"
    "You write ONLY from the Bart Bot technical grounding brief supplied in each user message. "
    "Bart has direct access to the DataHub codebase and is the authoritative source for product "
    "facts. You may rephrase Bart's grounding into compelling copy, but you may NOT introduce "
    "integrations, capabilities, customer brands, certifications, benchmarks, architecture "
    "components, or features that Bart did not explicitly verify. If Bart did not mention "
    "something, you do not write about it. If Bart flagged a limitation, you acknowledge it "
    "honestly.\n\n"
    "STYLE:\n"
    "Your writing is concrete, specific, and opinionated — never generic. You quantify claims "
    "or omit them. You follow DataHub's editorial style guide and brand guidelines (provided "
    "in the cached reference block). You write in active voice. You never use exclamation marks."
)


_LP_STYLE_RULES = """
## Technical landing page rules (supplement the reference docs)

### Section structure (10-section starting template)
Default to this section arc, in order. Allow the brief to drop or reshape sections when
the campaign clearly doesn't need one. Do not invent sections the brief doesn't support.

1. Hero — H1 + a 2–3 sentence subhead naming concrete capabilities.
2. Social proof — one paragraph naming 5–10 customer brands from the brief (skip if none provided).
3. Problem section — 3–4 named failure modes as H3 + 1 paragraph each.
4. Solution — 3–5 H3 sub-features, each naming the APIs, SDKs, SQL constructs, or protocols involved.
5. Implementation process — typically 3 steps, each naming specific tools and protocols.
6. Deployment & architecture — name internal components, deployment options, security/compliance specifics. Drop if brief is strictly feature-focused.
7. Customer testimonial — one Gartner Peer Insights-style quote (only if brief supplies one).
8. FAQ — 4–6 engineering-grade questions, ~120–180 words per answer, honest gap-acknowledgment.
9. CTA — restate the value, promise a consultation scoped to the prospect's stack.
10. Footer note — single short paragraph.

### Depth markers (required wherever the brief supports them)
- Named integrations by product (Snowflake, BigQuery, dbt, Airflow, Looker, Tableau, etc.)
- Named APIs / SDKs (GraphQL, REST, Python SDK, OpenLineage) as first-class integration mechanisms
- Specific technical constructs handled (SQL dialects, query patterns, file formats, protocols)
- Quantified benchmarks (cite source — IDC, customer case study, etc.)
- Open-source positioning when relevant (license, community size, downloads)
- Compliance / operational specifics (SOC 2 Type II, SSO standards, SLA percentages, VPC posture)
- Honest acknowledgment of day-one gaps and how they're filled

### Output format
- Word count: 2,500–3,500 words in the body (excludes the H1 title)
- Single `# ` H1 at the top, `## ` H2 for sections, `### ` H3 for sub-sections
- No HTML, no shortcodes, no YAML front matter, no code blocks — clean markdown only

### Brief-specific rules
- Primary search term appears verbatim in: H1, first 100 words, at least one H2, and the FAQ section
- Honor the "Must include" inputs verbatim where they fit naturally
- Avoid anything in the "Must not say" inputs
- No invented metrics, customer logos, certifications, or technical claims not in the brief
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


def _claude_sync_with_docs(user: str, max_tokens: int = 8000) -> str:
    """Like _claude_sync but injects the reference docs into the system as a cached block.

    Falls back to plain _claude_sync if the reference docs failed to load (so the pipeline
    doesn't break in environments where the reference files aren't present).
    """
    if not _REFERENCE_DOCS:
        return _claude_sync(_SYSTEM_PROMPT, user, max_tokens)

    client = Anthropic(api_key=_ANTHROPIC_KEY)
    msg = client.messages.create(
        model=_CLAUDE_MODEL,
        max_tokens=max_tokens,
        temperature=0.2,
        system=[
            {"type": "text", "text": _SYSTEM_PROMPT},
            {
                "type": "text",
                "text": "## DataHub reference documents (apply when writing)\n\n" + _REFERENCE_DOCS,
                "cache_control": {"type": "ephemeral"},
            },
        ],
        messages=[{"role": "user", "content": user}],
    )
    return "".join(
        block.text for block in msg.content if getattr(block, "type", None) == "text"
    ).strip()


async def _claude_with_docs(user: str, max_tokens: int = 8000) -> str:
    return await asyncio.to_thread(_claude_sync_with_docs, user, max_tokens)


def _strip_fences(raw: str) -> str:
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    return re.sub(r"\s*```$", "", raw.strip())


def _strip_markdown_fence(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:markdown|md)?\s*\n", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\n```\s*$", "", raw)
    return raw.strip()


def _normalize_dashes(text: str) -> str:
    return text.replace("—", " ").replace("–", "-")


def _format_inputs(inputs: Dict[str, Any]) -> str:
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


async def run_outline(inputs: Dict[str, Any], grounding: str) -> str:
    """Stage 1: produce a detailed outline of the technical LP, grounded in Bart's research."""
    user_prompt = f"""Produce a detailed outline for a DataHub technical landing page.

## AUTHORITATIVE TECHNICAL GROUNDING (from Bart Bot — codebase-verified)
You may use ONLY the integrations, capabilities, customer references, certifications, and
technical claims that Bart documented below. Do not introduce anything Bart did not name.
If Bart flagged a gap or limitation, the outline must respect it (do not promise something
Bart said doesn't work).

{grounding}

## TECHNICAL-LP STRUCTURE RULES
{_LP_STYLE_RULES}

## Your task
Build the outline as a markdown document. For each section in the 10-section template:
- The H2 heading (sentence case — primary search term should appear in at least one H2)
- 3–6 bullet points outlining what the section will say (drawn from Bart's grounding)
- H3 sub-headings within the section (named failure modes under Problem, sub-features under Solution, FAQ questions under FAQ)
- Notes on which specific integrations, APIs, technical constructs, or benchmarks to name (only from Bart's grounding)

If a section can't be supported by Bart's grounding, drop it and note why.

## Modal inputs (for tone/audience/CTA)
{_format_inputs(inputs)}

Return the outline only — no preamble, no explanation."""

    return await _claude_with_docs(user_prompt, max_tokens=4000)


async def run_full_copy(outline: str, inputs: Dict[str, Any], grounding: str) -> str:
    """Stage 2: write the full LP copy from the outline + Bart's grounding."""
    user_prompt = f"""Write the full DataHub technical landing page copy from the outline and grounding below.

## AUTHORITATIVE TECHNICAL GROUNDING (from Bart Bot — codebase-verified)
This is your ONLY source for product facts. You may NOT introduce integrations, capabilities,
customer brands, certifications, benchmarks, architecture components, or quantified claims
beyond what Bart documented. If Bart flagged a limitation, write the copy honestly around it.

{grounding}

## TECHNICAL-LP STRUCTURE RULES
{_LP_STYLE_RULES}

## OUTLINE (follow this structure)
{outline}

## Output format
Clean markdown:
- Single `# ` H1 at the top (the page title) — Title Case allowed
- `## ` H2 for each top-level section
- `### ` H3 for sub-sections
- Body paragraphs as plain text
- Bullet lists as `- ` lines
- No shortcodes, no YAML front matter, no code blocks
- Aim for 2,500–3,500 words in the body

## Modal inputs (for tone/audience/CTA)
{_format_inputs(inputs)}

Return only the markdown — no preamble, no explanation."""

    draft = await _claude_with_docs(user_prompt, max_tokens=12000)
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


