"""
Slack modal view for /technical-lp. Mirrors the SEM-LP request modal's field set
so main.py's extract_modal_values can be reused without modification.
"""
from typing import Any, Dict


def build_technical_lp_modal_view(channel_id: str = "") -> Dict[str, Any]:
    return {
        "type": "modal",
        "callback_id": "technical_lp_modal",
        "private_metadata": channel_id or "",
        "title": {"type": "plain_text", "text": "Technical LP"},
        "submit": {"type": "plain_text", "text": "Generate"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "search_term_block",
                "label": {"type": "plain_text", "text": "Search term (exact)"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "search_term",
                    "placeholder": {"type": "plain_text", "text": "e.g., kubernetes cost optimization"},
                },
            },
            {
                "type": "input",
                "optional": True,
                "block_id": "secondary_keywords_block",
                "label": {"type": "plain_text", "text": "Secondary keywords (optional)"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "secondary_keywords",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "One per line (or comma-separated)\nExample:\nkubernetes monitoring\ncloud cost management\nfinops for kubernetes",
                    },
                },
            },
            {
                "type": "input",
                "block_id": "primary_cta_block",
                "label": {"type": "plain_text", "text": "Primary CTA"},
                "element": {
                    "type": "static_select",
                    "action_id": "primary_cta",
                    "options": [
                        {"text": {"type": "plain_text", "text": "Demo"}, "value": "Demo"},
                        {"text": {"type": "plain_text", "text": "Free Trial"}, "value": "Free Trial"},
                        {"text": {"type": "plain_text", "text": "Product Tour"}, "value": "Product Tour"},
                        {"text": {"type": "plain_text", "text": "Bi-weekly Demo"}, "value": "Bi-weekly Demo"},
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "intent_block",
                "label": {"type": "plain_text", "text": "Intent (required)"},
                "element": {
                    "type": "static_select",
                    "action_id": "intent",
                    "options": [
                        {"text": {"type": "plain_text", "text": "Commercial"}, "value": "Commercial"},
                        {"text": {"type": "plain_text", "text": "Educational"}, "value": "Educational"},
                        {"text": {"type": "plain_text", "text": "Transactional"}, "value": "Transactional"},
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "primary_audience_block",
                "label": {"type": "plain_text", "text": "Primary Audience (required)"},
                "element": {
                    "type": "static_select",
                    "action_id": "primary_audience",
                    "options": [
                        {"text": {"type": "plain_text", "text": "Economic Buyer"}, "value": "Economic Buyer"},
                        {"text": {"type": "plain_text", "text": "Platform Engineer"}, "value": "Platform Engineer"},
                    ],
                },
            },
            {
                "type": "input",
                "optional": True,
                "block_id": "offer_block",
                "label": {"type": "plain_text", "text": "Offer (optional)"},
                "element": {"type": "plain_text_input", "action_id": "offer", "multiline": True},
            },
            {
                "type": "input",
                "optional": True,
                "block_id": "must_include_block",
                "label": {"type": "plain_text", "text": "Must include (optional)"},
                "element": {"type": "plain_text_input", "action_id": "must_include", "multiline": True},
            },
            {
                "type": "input",
                "optional": True,
                "block_id": "must_not_say_block",
                "label": {"type": "plain_text", "text": "Must not say (optional)"},
                "element": {"type": "plain_text_input", "action_id": "must_not_say", "multiline": True},
            },
        ],
    }
