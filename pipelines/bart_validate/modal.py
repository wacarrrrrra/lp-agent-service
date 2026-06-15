"""
Slack modal view for /bart-validate. Captures a source URL (Google Doc or Sheet)
and a one-sentence context, then the pipeline fetches the content, sends it to
Bart for fact-checking, and writes the result to a new Google Doc.
"""
from typing import Any, Dict, Optional


def extract_bart_validate_fields(view_state: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Pull only the /bart-validate fields out of a Slack view.state payload."""
    values = view_state.get("values", {})

    def get(block_id: str, action_id: str) -> Optional[str]:
        block = values.get(block_id, {})
        action = block.get(action_id, {})
        if "value" in action:
            return action.get("value")
        selected = action.get("selected_option")
        if selected:
            return selected.get("value")
        return None

    return {
        "source_type": get("source_type_block", "source_type"),
        "source_url":  get("source_url_block", "source_url"),
        "sheet_tab":   get("sheet_tab_block", "sheet_tab"),
        "context":     get("context_block", "context"),
    }


def build_bart_validate_modal_view(channel_id: str = "") -> Dict[str, Any]:
    return {
        "type": "modal",
        "callback_id": "bart_validate_modal",
        "private_metadata": channel_id or "",
        "title": {"type": "plain_text", "text": "Bart validation"},
        "submit": {"type": "plain_text", "text": "Send to Bart"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "source_type_block",
                "label": {"type": "plain_text", "text": "What are you validating?"},
                "element": {
                    "type": "static_select",
                    "action_id": "source_type",
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "Keyword list to validate"},
                            "value": "keywords",
                        },
                        {
                            "text": {"type": "plain_text", "text": "Landing page draft to validate"},
                            "value": "lp_content",
                        },
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "source_url_block",
                "label": {"type": "plain_text", "text": "Source URL (Google Sheet or Google Doc)"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "source_url",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "https://docs.google.com/...",
                    },
                },
                "hint": {
                    "type": "plain_text",
                    "text": "Share the Sheet/Doc with blog-agent@robust-limiter-488800-g5.iam.gserviceaccount.com (Viewer is enough).",
                },
            },
            {
                "type": "input",
                "optional": True,
                "block_id": "sheet_tab_block",
                "label": {"type": "plain_text", "text": "Sheet tab name (keywords only, optional)"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "sheet_tab",
                    "placeholder": {"type": "plain_text", "text": "e.g., New keywords"},
                },
                "hint": {
                    "type": "plain_text",
                    "text": "If blank, the first tab is used.",
                },
            },
            {
                "type": "input",
                "block_id": "context_block",
                "label": {"type": "plain_text", "text": "Context (one sentence)"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "context",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "e.g., GRC keyword cluster — evaluating whether DataHub can target governance risk and compliance terms",
                    },
                },
            },
        ],
    }
