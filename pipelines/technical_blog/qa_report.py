from typing import List, Optional


def format_qa_report(
    title: str,
    gdoc_url: str,
    edit_url: str,
    qa_issues: List[dict],
    hero_filename: str,
    featured_filename: str,
    socialcard_filename: str,
    idx_str: str,
    diagram_prompt: Optional[str] = None,
) -> str:
    """Build the Slack QA report posted to #blog-publisher."""
    issue_count = len(qa_issues)

    if qa_issues:
        issue_lines = "\n".join(
            f"• *{i['rule']}*: _{i.get('location', '')}_ → {i.get('fix', '')}"
            for i in qa_issues
        )
    else:
        issue_lines = "No issues found."

    diagram_section = ""
    if diagram_prompt:
        diagram_section = (
            f"\n\n📊 *Diagram needed* — copy prompt below and run through SVG generation:\n"
            f"```\n{diagram_prompt}\n```"
        )
    else:
        diagram_section = "\n\n📊 *Diagram needed:* No"

    return (
        f"✅ *Draft ready — ready for review*\n\n"
        f"*{title}*\n\n"
        f"📝 *Edit here (Google Doc):*\n"
        f"{gdoc_url}\n\n"
        f"🌐 *WordPress draft (staging reference):*\n"
        f"{edit_url}\n\n"
        f"📋 *QA ({issue_count} issue(s) to check):*\n"
        f"{issue_lines}\n\n"
        f"🖼 *Images assigned (index {idx_str}):*\n"
        f"  • Hero: `{hero_filename.split('/')[-1]}`\n"
        f"  • Featured: `{featured_filename.split('/')[-1]}`\n"
        f"  • Social card: `{socialcard_filename.split('/')[-1]}`"
        f"{diagram_section}\n\n"
        f"When edits are done, sync back to WordPress with:\n"
        f"`/sync-to-wordpress {gdoc_url}`"
    )
