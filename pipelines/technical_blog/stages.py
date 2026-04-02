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

# Key rules distilled from blog-template-guide.md and writing-best-practices.md
_BLOG_STYLE_RULES = """
## Content & SEO rules (follow strictly)

### SEO fields
- Title tag: ≤60 characters EXCLUDING " | DataHub". Include the focus keyword verbatim. Title Case.
- Meta description: ≤140 characters. Sentence case. Include focus keyword and a reason to click.
- URL slug: no filler words (a, the, of, and). Use hyphens. Under 5 words. Must contain the focus keyword words (e.g. focus keyword "data lineage" → slug includes "data-lineage").
- Focus keyword: the primary search term, 2–4 words. Must appear verbatim in both the title tag and the URL slug.

### Structure
- Open with a clean, citable definition of the primary entity — minimize preamble.
- First hyperlink must point to https://datahub.com/products/ anchored on a relevant keyphrase.
- H2s: phrase 30–50% as questions when it feels natural. All sentence case.
- Target 2,500–3,500 words total.
- 4-line max per body paragraph.
- Numbers one through nine spelled out in body text (not in code, headings, or lists).
- Use "and" not "&". No em dashes. No exclamation marks in headings. No italic text.
- No weasel words — quantify claims or omit them.

### Shortcodes (use these in the markdown output — the publisher handles rendering)
Use the following shortcodes on their own line:

[DEFINITION: Title | Body text]
  → Styled definition box with H2 heading. Use near the top for the primary entity definition.
  Example: [DEFINITION: Quick definition: data lineage | Data lineage tracks the origin, movement, and transformation of data across your stack.]

[CALLOUT: Title | Body text]
  → Styled callout box with H3. Does not appear in TOC. Use for tips, context, secondary concepts.

[DIAGRAM: one-sentence description of what the diagram should show]
  → Flags a diagram placeholder. Will be visible in the Google Doc for the designer, and rendered as an empty image block in WordPress.

[NOTE: editorial note text]
  → Stripped from both Google Doc and WordPress. Use for internal review notes only.

### FAQ section
- End the article with an H2 "FAQs" section.
- Put [FAQ] on its own line immediately after the H2 heading.
- Write each question as an H3, followed by the answer as a paragraph.
- 5–8 FAQs: mix informational (broader topic) and product-specific (how DataHub handles this).
- Each answer: 1–2 sentence direct answer first, then elaboration. 40–70 words total.

Example FAQ format:
## FAQs

[FAQ]

### What is the difference between data lineage and data provenance?
Data lineage tracks how data moves and transforms across systems. Data provenance focuses on the origin and ownership of data at the point of creation. In practice, most data catalogs (including DataHub) combine both.

### How does DataHub capture lineage automatically?
DataHub uses metadata ingestion connectors for tools like dbt, Airflow, and Spark to capture lineage without manual tagging. [See how DataHub's lineage works](https://datahub.com/products/).
""".strip()

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
8. Meta description (from YAML front matter) must be ≤140 characters — count carefully
9. Title (from YAML front matter) must be ≤60 characters EXCLUDING the " | DataHub" suffix — count carefully
10. No filler openers (flags: "in today's", "as organizations", "it's no secret", "in the world of")
11. No generic link anchor text ("click here", "here", "learn more" alone)
12. FAQ section must have a [FAQ] shortcode on its own line immediately after the ## FAQs heading
13. Any diagram notes must use [DIAGRAM: description] shortcode format, not inline comments
14. Focus keyword (from YAML front matter) must appear verbatim in the title (case-insensitive)
15. Focus keyword words must all appear in the URL slug (e.g. keyword "data lineage" → slug must contain "data" and "lineage")

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
    """Stage 1: produce a detailed outline + shortcode scaffold + SEO JSON."""
    user_prompt = f"""Using the brief below, produce a detailed blog post outline.

## Section outline
For each H2 section include:
- The section heading (sentence case — phrase 30–50% as questions where natural)
- 3–5 bullet points covering what the section will say
- Note any code snippets, tables, or diagrams needed

## Shortcode plan (required — include this section verbatim in your outline)
After the section outline, add a section headed "## SHORTCODE PLAN" containing:

**[DEFINITION:]** — Write the exact shortcode to place near the top of the article, defining the primary entity in one clean, citable sentence:
[DEFINITION: Quick definition: {{primary entity}} | {{one-sentence definition}}]

**[CALLOUT:] boxes** — List 1–3 callout boxes (secondary concepts, tips, "how DataHub handles X"):
[CALLOUT: {{title}} | {{1–2 sentence body}}]

**[DIAGRAM:]** — If a diagram would help, write the exact shortcode:
[DIAGRAM: {{one sentence describing what the diagram shows}}]
(Write "No diagram" if not needed.)

**[FAQ] questions** — List the exact 6–8 FAQ question titles (mix of informational and product-specific):
1. {{question}}
2. {{question}}
...

## SEO JSON
At the end output a ```json block:
{{
  "title": "...",            ← Title Case, ≤60 chars EXCLUDING " | DataHub"
  "slug": "...",             ← no filler words, 3–5 hyphened words
  "meta_description": "...", ← ≤140 chars, sentence case, includes focus keyword
  "focus_keyword": "...",    ← 2–4 word primary search term
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
    user_prompt = f"""Write the full blog post from the outline below. Follow ALL style rules carefully.

{_BLOG_STYLE_RULES}

Output format: clean markdown. Include YAML front matter at the top:

---
title: "..."           ← Title Case, ≤60 chars EXCLUDING " | DataHub"
slug: "..."
author: "DataHub"
category: "Engineering"
meta_description: "..."   ← ≤140 chars
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


async def run_best_practices_pass(draft: str) -> str:
    """Stage 2.5: revise the draft against writing best practices. Returns improved draft."""
    user_prompt = f"""Review this blog post draft and revise it against the DataHub writing best practices below.
Return the COMPLETE revised post in markdown with YAML front matter. Return ONLY the markdown — no preamble or explanation.

## Checks to make and fix

1. PRIMARY ENTITY DEFINITION
   Within the first 100 words (before the first H2), there must be a [DEFINITION: Title | Body] shortcode giving a clean, citable one-sentence definition of the primary topic. If it is missing or buried in a paragraph, add it immediately after the intro sentence.
   Format: [DEFINITION: Quick definition: {{topic}} | {{one clean sentence}}]

2. FIRST HYPERLINK
   The very first hyperlink in the article body must go to https://datahub.com/products/ anchored on a relevant keyphrase (e.g. "DataHub's data catalog"). If the first link goes elsewhere, insert a datahub.com/products/ link before it in a natural sentence.

3. H2 QUESTION FORMAT
   Rephrase 30–50% of H2 headings as questions where it reads naturally. Do not force it. Example: "Why data lineage matters" → "Why does data lineage matter?"

4. EXTERNAL CITATIONS
   Include at least 3 links to authoritative third-party sources (research reports, standards bodies, analyst firms). Anchor from the source name: "According to [Gartner's 2025 report](url)" not "According to [this study](url)". If citations are missing, add them where they strengthen a claim.

5. WEASEL WORDS
   Replace or remove: "many organizations", "significant savings", "increasingly", "growing number of", "it's no secret", "in the world of", "as teams scale", "more and more". Substitute a specific number, example, or delete the sentence.

6. SHORTCODE COMPLETENESS — the post MUST contain all of these:
   - At least one [DEFINITION: Title | Body] box (near the top)
   - At least one [CALLOUT: Title | Body] box mid-article for a secondary concept or "How DataHub handles X"
   - The [FAQ] shortcode on its own line immediately after ## FAQs
   - [DIAGRAM: description] if the outline called for one
   Add any that are missing. Do not remove ones that are already there.

7. DATAHUB WOVEN IN THROUGHOUT
   DataHub should appear naturally in at least 3 H2 sections, not only in the final section. If it is only in the conclusion, add a [CALLOUT: How DataHub handles {{topic}} | ...] in an earlier section.

8. PARAGRAPH LENGTH
   No body paragraph should exceed 4 lines. Break any that are longer.

9. FAQ ANSWERS
   Each FAQ answer must lead with a 1–2 sentence direct answer, then elaborate. Total 40–70 words for informational questions, 60–120 for product questions.

POST TO REVISE:
{draft}"""

    revised = await _claude(_SYSTEM_PROMPT, user_prompt, max_tokens=14000)
    revised = revised.replace("\u2014", " ").replace("\u2013", "-")
    return revised


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
