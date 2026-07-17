"""
Signal Radar pipeline — weekly job.

Pulls rising queries from Google Search Console for the DataHub property, runs each
through the Claude-based classifier to triage as Confirmed / Conditional / Exclude,
and posts TWO Slack digests:
  - Internal channel: full scored list (all buckets)
  - Agency channel:  only 🔥 Strategic (Confirmed + rising fast)

This is a triage pipeline. High-priority findings should be re-submitted to
/bart-validate for authoritative fit-checks (Bart has codebase access that Claude lacks).
"""
import logging
import os
from datetime import date
from typing import Callable, Dict, List, Optional

from pipelines.signal_radar.classifier import classify_queries
from pipelines.signal_radar.gsc_client import fetch_query_deltas

logger = logging.getLogger("uvicorn.error")

# Tuning knobs — set via env vars if needed.
MIN_IMPRESSIONS_RECENT = int(os.getenv("SIGNAL_RADAR_MIN_IMPRESSIONS", "5"))
TOP_N = int(os.getenv("SIGNAL_RADAR_TOP_N", "15"))


def _score(verdict: str, delta: int, velocity: Optional[float]) -> str:
    """Turn a Claude verdict + growth metrics into a Signal Radar tier label."""
    is_hot = delta >= 20 or (velocity is not None and velocity >= 1.0)
    if verdict == "confirmed" and is_hot:
        return "🔥 Strategic"
    if verdict == "confirmed":
        return "✅ Ready"
    if verdict == "conditional":
        return "⚠️ Watch"
    return "⬜ Pass"


def _fmt_velocity(delta: int, velocity: Optional[float]) -> str:
    if velocity is None:
        return f"+{delta} (new)"
    return f"+{delta} ({velocity * 100:+.0f}%)"


def _format_internal_digest(scored: List[Dict], recent_window: str, prior_window: str) -> str:
    lines = [
        f"🛰️ *Signal Radar — weekly digest*",
        f"_Recent: {recent_window} · Prior: {prior_window}_",
        "",
        f"Top {len(scored)} rising queries on datahub.com. Triage below — for authoritative fit-check on the interesting ones, use `/bart-validate`.",
        "",
        "```",
        f"{'Tier':<15} {'Δ impressions':<18} {'Query'}",
    ]
    lines.append("-" * 80)
    for s in scored:
        tier = s["tier"]
        vel = _fmt_velocity(s["delta"], s["velocity"])
        q = s["query"][:60]
        lines.append(f"{tier:<15} {vel:<18} {q}")
    lines.append("```")
    lines.append("")
    lines.append("*Reasoning per query:*")
    for s in scored:
        lines.append(f"• {s['tier']} — `{s['query']}` — {s['reason']}")
    return "\n".join(lines)


def _format_agency_digest(strategic: List[Dict], recent_window: str) -> str:
    lines = [
        f"🎯 *Weekly rising queries — DataHub is a strong fit*",
        f"_Signal window: {recent_window}. Suggestions for LP + SEM prioritization._",
        "",
    ]
    for s in strategic:
        lines.append(f"• *{s['query']}* — {_fmt_velocity(s['delta'], s['velocity'])} impressions")
        lines.append(f"    _{s['reason']}_")
    lines.append("")
    lines.append(f"_These are triaged as 🔥 Strategic (DataHub-confirmed coverage + rising traffic). {len(strategic)} of this week's rising queries fit the criteria._")
    lines.append("_Deeper fit-check on any of these? Use `/bart-validate` with the query as context._")
    return "\n".join(lines)


async def run_signal_radar(
    post_message: Callable,
    internal_channel: str,
    agency_channel: str,
) -> Dict:
    """Fetch → classify → score → post. Returns a summary dict for the caller."""
    logger.info("Signal Radar run starting")
    try:
        deltas = await fetch_query_deltas()
    except Exception as e:
        logger.exception("GSC fetch failed: %s", e)
        if internal_channel:
            try:
                await post_message(
                    internal_channel,
                    f"❌ Signal Radar run failed at GSC fetch: `{e}`",
                )
            except Exception:
                pass
        return {"ok": False, "error": f"gsc_fetch: {e}"}

    rising = [
        d for d in deltas
        if d["delta"] > 0 and d["impressions_recent"] >= MIN_IMPRESSIONS_RECENT
    ]
    top = rising[:TOP_N]

    if not top:
        msg = (
            f"🛰️ *Signal Radar — weekly digest*\n"
            f"_No rising queries this week (min {MIN_IMPRESSIONS_RECENT} impressions filter). "
            f"Nothing to triage._"
        )
        if internal_channel:
            await post_message(internal_channel, msg)
        logger.info("Signal Radar: no rising queries this week")
        return {"ok": True, "rising_count": 0}

    classifications = await classify_queries([d["query"] for d in top])

    scored: List[Dict] = []
    for d, c in zip(top, classifications):
        verdict = c["verdict"]
        tier = _score(verdict, d["delta"], d["velocity"])
        scored.append({
            **d,
            "verdict": verdict,
            "reason": c["reason"],
            "tier": tier,
        })

    # Window strings for the digest header
    today = date.today()
    recent_window = f"last 7 days ending {today.isoformat()}"
    prior_window  = "prior 7 days"

    if internal_channel:
        await post_message(internal_channel, _format_internal_digest(scored, recent_window, prior_window))

    strategic = [s for s in scored if s["tier"] == "🔥 Strategic"]
    if strategic and agency_channel:
        await post_message(agency_channel, _format_agency_digest(strategic, recent_window))

    counts = {
        "strategic": sum(1 for s in scored if s["tier"] == "🔥 Strategic"),
        "ready":     sum(1 for s in scored if s["tier"] == "✅ Ready"),
        "watch":     sum(1 for s in scored if s["tier"] == "⚠️ Watch"),
        "pass":      sum(1 for s in scored if s["tier"] == "⬜ Pass"),
    }
    logger.info("Signal Radar run complete: %s", counts)
    return {"ok": True, "rising_count": len(scored), "counts": counts}
