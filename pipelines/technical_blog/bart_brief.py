import os

BART_USER_ID = os.getenv("BART_USER_ID", "")

_DIAGRAM_PROMPT_INSTRUCTIONS = """
If the brief flags a diagram as needed, write a diagram_prompt for a technical SVG illustration following these exact constraints:

DataHub brand colors only:
- Background: #F2F1EE (off-white) or #002131 (dark blue)
- Primary stroke/fill: #006DCD (blue midtone) or #3CBBEB (bright blue)
- Text: #161616 (off-black) on light backgrounds
- Accent: #0FC691 (green) for success/flow states

Style rules:
- Flat, enterprise-grade, no gradients, no shadows
- Rounded rectangle tiles (border-radius equivalent)
- Directional flow shown with solid arrows in #3CBBEB
- Monospace labels for technical terms (table names, column names, tool names)
- Geist or system sans-serif for section labels
- No stock icons — use simple geometric shapes only
- One outer frame containing all content

The diagram_prompt should describe: layout direction, what each tile/node represents, what the arrows show, and what text labels appear. Be specific enough that a separate Claude call can generate the SVG without ambiguity.
""".strip()


def build_bart_message(topic: str) -> str:
    return (
        f"<@{BART_USER_ID}> Engineering blog request.\n\n"
        f"TOPIC: {topic}\n\n"
        "Please research this topic and produce a structured blog brief with:\n\n"
        "1. WORKING TITLE — a clear, specific H1 candidate (sentence case, not title case)\n"
        "2. AUDIENCE — who this post is for (e.g., data engineers, platform teams)\n"
        "3. ANGLE — the specific point of view or argument this post makes\n"
        "4. OUTLINE — H2 sections with 1–2 sentence descriptions of each\n"
        "5. KEY CLAIMS — 3–5 technical claims that must be accurate; flag any you are uncertain about\n"
        "6. DIAGRAM NEEDED — yes/no, and if yes: describe in one sentence what the diagram should show\n"
        "7. SUGGESTED SLUG — URL-friendly, no filler words\n\n"
        "When complete, reply BART_DONE on its own line."
    )


def get_diagram_prompt_instructions() -> str:
    return _DIAGRAM_PROMPT_INSTRUCTIONS
