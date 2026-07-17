"""
Signal Radar classifier — triage step.

For each rising query, ask Claude to classify as Confirmed / Conditional / Exclude
based on DataHub's shipped capabilities. This is a triage step, NOT authoritative
validation — use /bart-validate for authoritative fit-checks (Bart has codebase access
that Claude lacks).

Output is a list of {query, verdict, reason} — kept short so the Slack digest stays
scannable.
"""
import asyncio
import json
import logging
import os
import re
from typing import List

from anthropic import Anthropic

logger = logging.getLogger("uvicorn.error")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
_client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None


_SYSTEM_PROMPT = """You are triaging search queries for DataHub's SEM marketing team.

DataHub is an open-source data catalog and metadata management platform. Shipped capabilities include:
- Data lineage (column-level and table-level, OpenLineage support, native integrations with Snowflake, BigQuery, dbt, Airflow, Looker, Tableau, and 100+ others)
- Business glossary (with governance workflows)
- Access policies / RBAC
- Data assertions and observability (freshness, volume, schema, custom)
- Compliance forms and structured property review workflows
- APIs: GraphQL, REST, Python SDK
- Deployment: Helm/Kubernetes, Docker, Managed Cloud (DataHub Cloud)
- Security: SOC 2 Type II, SSO (SAML/OIDC), VPC deployment
- Metadata graph backed by GMS, Elasticsearch/OpenSearch, Neo4j (optional), Kafka event stream
- Open source (Apache 2.0)

For each query, classify:
- ✅ Confirmed — DataHub has documented, shipped capabilities that clearly match this query.
- ⚠️ Conditional — DataHub has adjacent or partial coverage; would need SME/PM confirmation before targeting.
- ❌ Exclude — DataHub has no legitimate coverage. Anything tied to specific analyst content (Gartner, McKinsey, Forrester reports we're not featured in) defaults here.

Reply with a JSON object only (no prose before or after):
{"classifications": [
  {"query": "...", "verdict": "confirmed" | "conditional" | "exclude", "reason": "one short sentence"}
]}

The `reason` field should be under 20 words and cite a specific capability or docs area when confirming."""


def _extract_json_object(text: str) -> dict:
    """Robust-ish JSON extraction: tolerate leading/trailing prose or ```json fences."""
    if not text:
        return {}
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Strip markdown code fence
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Grab the first {...} span
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {}


async def classify_queries(queries: List[str]) -> List[dict]:
    """Return a list of {query, verdict, reason} dicts in the same order as input.

    Falls back to marking every query as 'conditional' with reason 'triage unavailable' if
    the API call or parse fails — Signal Radar should still post *something* even when
    the classifier is degraded.
    """
    if not queries:
        return []
    if not _client:
        logger.warning("Signal Radar classifier called with no ANTHROPIC_API_KEY set")
        return [{"query": q, "verdict": "conditional", "reason": "classifier unavailable"} for q in queries]

    numbered = "\n".join(f"{i+1}. {q}" for i, q in enumerate(queries))
    user_msg = f"Classify these {len(queries)} search queries:\n\n{numbered}"

    try:
        resp = await asyncio.to_thread(
            _client.messages.create,
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        text_parts = [b.text for b in resp.content if hasattr(b, "text")]
        raw = "\n".join(text_parts)
    except Exception as e:
        logger.exception("Claude classification call failed: %s", e)
        return [{"query": q, "verdict": "conditional", "reason": "classifier error"} for q in queries]

    parsed = _extract_json_object(raw)
    entries = parsed.get("classifications") or []
    by_query = {e.get("query", ""): e for e in entries if isinstance(e, dict)}

    out: List[dict] = []
    for q in queries:
        entry = by_query.get(q)
        if not entry:
            out.append({"query": q, "verdict": "conditional", "reason": "not classified — SME check"})
            continue
        verdict = (entry.get("verdict") or "conditional").strip().lower()
        if verdict not in ("confirmed", "conditional", "exclude"):
            verdict = "conditional"
        out.append({
            "query": q,
            "verdict": verdict,
            "reason": (entry.get("reason") or "").strip() or "no reason given",
        })
    return out
