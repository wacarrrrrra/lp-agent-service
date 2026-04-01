import asyncio
import json
import os
import re
import logging
from typing import Dict, Optional, Tuple

from anthropic import Anthropic

from pipelines.technical_blog.bart_brief import get_diagram_prompt_instructions

logger = logging.getLogger("uvicorn.error")

_ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

_SYSTEM_PROMPT = (
    "You are a senior technical writer at DataHub. You write technical blog posts for data engineers, "
    "platform teams, and technical practitioners. Your writing is clear, specific, and opinionated — "
    "not generic. You never use filler phrases like \"in today's data landscape\" or \"as organizations scale\". "
    "You write in sentence case. No em dashes."
)

_QA_SYSTEM_PROMPT = (
    "You are a copy editor. You check markdown blog posts against a strict style rulebook. "
    "Be precise and list only real violations — do not flag things that are correct."
)

_QA_RULES = """Check the blog post below against these rules and return a JSON array of issues:

[
  {"rule": "rule name", "location": "quote the offending text", "fix": "suggested correction"}
]

Rules to check:
1. No em dashes (—) anywhere
2. No italic text (no *word* or _word_ unless it is a code block)
3. All H2 and H3 must be sentence case (first word capitalized, rest lowercase unless proper noun)
4. Proper nouns exempt from sentence case: AI, DataHub, API, SQL, AWS, GCP, Azure, Slack, GitHub, Snowflake, BigQuery, dbt, Databricks, MCP, BartBot
5. Numbers one through nine spelled out in body text (not in code, headings, or lists)
6. No ampersands (&) in body text — use "and"
7. No exclamation marks in headings
8. Meta description ≤140 characters
9. No filler openers (flags: "in today's", "as organizations", "it's no secret", "in the world of")
10. No generic link anchor text ("click here", "here", "learn more" alone)

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


async def run_outline(bart_brief: str) -> Tuple[str, Dict]:
    """Stage 1: produce a detailed outline + extract SEO JSON and diagram_prompt."""
    user_prompt = f"""Using the brief below, produce a detailed blog post outline.

For each H2 section include:
- The section heading (sentence case)
- 3–5 bullet points covering what the section will say
- Whether a diagram, code snippet, or table is needed in this section

At the end, output a JSON block (fenced with ```json) with:
{{
  "title": "...",
  "slug": "...",
  "meta_description": "...",
  "focus_keyword": "...",
  "diagram_prompt": "..." or null
}}

{get_diagram_prompt_instructions()}

BRIEF:
{bart_brief}"""

    outline_raw = await _claude(_SYSTEM_PROMPT, user_prompt, max_tokens=6000)

    # Extract the trailing JSON block
    json_match = re.search(r"```json\s*([\s\S]+?)\s*```", outline_raw, re.IGNORECASE)
    seo_json: Dict = {}
    if json_match:
        try:
            seo_json = json.loads(json_match.group(1))
        except Exception:
            logger.warning("Outline stage: could not parse SEO JSON block")

    # Return outline text (without the json block) + seo fields
    outline_text = re.sub(r"```json[\s\S]+?```", "", outline_raw, flags=re.IGNORECASE).strip()
    return outline_text, seo_json


async def run_full_draft(outline: str, bart_brief: str) -> str:
    """Stage 2: write the full blog post from the outline. Returns markdown with YAML front matter."""
    user_prompt = f"""Write the full blog post from the outline below.

Rules:
- Sentence case for all headings (H1, H2, H3)
- No em dashes — use commas, colons, or restructure the sentence
- No italic text
- No filler openers ("In today's...", "As data teams grow...", "It's no secret...")
- Spell out numbers one through nine in body text
- Use "and" not "&"
- No exclamation marks in headings
- Hyperlink format: [anchor text](URL) — anchor text should be descriptive, never "click here" or "here"
- FAQ section at the end: H3 for each question, paragraph for each answer
- End with a natural transition to related resources (do not hard-sell)

Output format: clean markdown. Include YAML front matter at the top:

---
title: "..."
slug: "..."
author: "John Joyce, Co-Founder, DataHub"
category: "Engineering"
meta_description: "..."
focus_keyword: "..."
---

OUTLINE:
{outline}

BRIEF:
{bart_brief}"""

    draft = await _claude(_SYSTEM_PROMPT, user_prompt, max_tokens=12000)
    # Strip em-dashes even if Claude missed the rule
    draft = draft.replace("\u2014", " ").replace("\u2013", "-")
    draft = draft.replace("&mdash;", " ").replace("&ndash;", "-")
    return draft


async def run_qa_pass(draft: str) -> Tuple[str, list]:
    """Stage 3: QA pass. Auto-applies fixes. Returns (corrected_draft, issues_list)."""
    user_prompt = f"""{_QA_RULES}

POST:
{draft}"""

    raw = await _claude(_QA_SYSTEM_PROMPT, user_prompt, max_tokens=4000)
    raw = _strip_fences(raw)

    issues = []
    try:
        issues = json.loads(raw)
        if not isinstance(issues, list):
            issues = []
    except Exception:
        logger.warning("QA pass returned non-JSON: %s", raw[:200])

    if not issues:
        return draft, []

    # Ask Claude to apply the fixes
    fix_prompt = f"""Apply all the fixes below to the blog post and return the corrected full post in markdown (with YAML front matter). Return only the corrected post — no preamble.

ISSUES:
{json.dumps(issues, indent=2)}

POST:
{draft}"""
    corrected = await _claude(_SYSTEM_PROMPT, fix_prompt, max_tokens=12000)
    corrected = corrected.replace("\u2014", " ").replace("\u2013", "-")
    return corrected, issues


def parse_yaml_front_matter(draft: str) -> Tuple[Dict, str]:
    """Extract YAML front matter dict and return (meta, body_markdown)."""
    m = re.match(r"^---\s*\n([\s\S]+?)\n---\s*\n", draft)
    if not m:
        return {}, draft

    meta: Dict = {}
    for line in m.group(1).splitlines():
        kv = re.match(r'^(\w[\w_]*):\s*"?(.+?)"?\s*$', line)
        if kv:
            meta[kv.group(1)] = kv.group(2).strip().strip('"')

    body = draft[m.end():].strip()
    return meta, body
