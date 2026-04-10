#!/usr/bin/env python3
"""
Test that the LP agent will generate heroes matching the finalized design.

Validates:
1. The prompt contains correct hero instructions (form ring, button-text, no deprecated patterns)
2. The template HTML uses .hs-form-ring (not framed-image in hero)
3. Brand guidelines reference correct fonts (Plantin/Lab Grotesque, not Castoro/Geist)
4. SKILL.md documents the hero form ring pattern

Run: python3 test_hero_design.py
No API key needed — this tests the prompt/template, not the generation output.
"""

import sys
import os

# Add repo root to path so we can import main
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  PASS  {name}")
        passed += 1
    else:
        print(f"  FAIL  {name}")
        if detail:
            print(f"        {detail}")
        failed += 1


def load(path):
    with open(path, "r") as f:
        return f.read()


# ── Load all source files ────────────────────────────────────

root = os.path.dirname(os.path.abspath(__file__))
main_py = load(os.path.join(root, "main.py"))
template = load(os.path.join(root, "templates/datahub-governance-lp1.html"))
skill_md = load(os.path.join(root, ".claude/skills/front-end-design/SKILL.md"))
sem_structure = load(os.path.join(root, "SEM-LP-Structure.md"))
brand_guide = load(os.path.join(root, "brand-guidelines.md"))


# ── 1. PROMPT (main.py) ─────────────────────────────────────

print("\n1. main.py — Prompt rules")
print("=" * 50)

check(
    "Prompt references .hs-form-ring",
    "hs-form-ring" in main_py,
    "The prompt should tell Claude to use .hs-form-ring for the hero form"
)

check(
    "Prompt references .button-text for secondary CTA",
    "button-text" in main_py,
    "The prompt should tell Claude to use .button-text, not .button-ghost"
)

check(
    "Prompt deprecates .button-ghost in hero",
    "button-ghost is deprecated" in main_py.lower() or "do not use button-ghost" in main_py.lower(),
    "The prompt should explicitly say not to use button-ghost in hero"
)

check(
    "Prompt says no inline styles on hero",
    "do NOT add inline styles" in main_py or "do not add inline style" in main_py.lower(),
    "The prompt should prevent inline styles on hero elements"
)

check(
    "build_page_head does NOT use Castoro/Geist fonts",
    "Castoro" not in main_py.split("def build_page_head")[1].split("\ndef ")[0]
    if "def build_page_head" in main_py else False,
    "build_page_head should use the shared stylesheet, not Google Fonts Castoro/Geist"
)

check(
    "Prompt does NOT reference framed-image in hero",
    "framed-image" not in main_py.split("Hero image")[0] if "Hero image" in main_py else True,
    "The prompt should not tell Claude to use framed-image in the hero"
)

check(
    "Prompt includes css:'' in HubSpot form config",
    'css: ""' in main_py or "css: ''" in main_py or '"css"' in main_py,
    "HubSpot form must include css:'' to disable default HubSpot styles"
)


# ── 2. TEMPLATE HTML ────────────────────────────────────────

print("\n2. Template HTML — Hero structure")
print("=" * 50)

# Find the hero section in the template
hero_start = template.find('<section class="hero"')
hero_end = template.find('</section>', hero_start) + len('</section>') if hero_start >= 0 else -1
hero_html = template[hero_start:hero_end] if hero_start >= 0 else ""

check(
    "Template has a hero section",
    hero_start >= 0,
    "Template should contain <section class=\"hero\">"
)

check(
    "Hero uses .hs-form-ring",
    "hs-form-ring" in hero_html,
    "Hero right column should use .hs-form-ring component"
)

check(
    "Hero has .hs-form-ring__header",
    "hs-form-ring__header" in hero_html,
    "Form ring should have a header tile"
)

check(
    "Hero has .hs-form-ring__body",
    "hs-form-ring__body" in hero_html,
    "Form ring should have a body for the HubSpot form"
)

check(
    "Hero does NOT use .framed-image",
    "framed-image" not in hero_html,
    "Hero should NOT contain framed-image — that's for feature sections"
)

check(
    "Hero does NOT use .button-ghost",
    "button-ghost" not in hero_html,
    "Hero should use .button-text for secondary CTA, not .button-ghost"
)

check(
    "Hero has id='hero-form' on hero-visual",
    'id="hero-form"' in hero_html,
    "hero-visual div should have id='hero-form' for anchor links"
)

check(
    "Hero uses button-primary with span",
    "button-primary" in hero_html and "<span>" in hero_html,
    "Primary CTA should use button-primary with inner <span>"
)

check(
    "Hero has no inline style on hero-visual",
    'hero-visual animate-in" style=' not in hero_html
    and 'hero-visual animate-in" id="hero-form">' in hero_html,
    "hero-visual should not have inline styles"
)

check(
    "HubSpot script uses hsforms.net",
    "js.hsforms.net" in hero_html,
    "Form script should load from js.hsforms.net"
)


# ── 3. SKILL.md — Design system rules ──────────────────────

print("\n3. SKILL.md — Design rules")
print("=" * 50)

check(
    "Documents .hs-form-ring component",
    "hs-form-ring" in skill_md,
    "SKILL.md should document the hero form ring component"
)

check(
    "Documents .button-text pattern",
    "button-text" in skill_md,
    "SKILL.md should document the text-only button for hero secondary CTA"
)

check(
    "Says NOT to use framed-image in hero",
    "framed-image" in skill_md and "hero" in skill_md.lower(),
    "SKILL.md should explicitly say framed-image is not for the hero"
)


# ── 4. CHALLENGE SECTION ──────────────────────────────────

print("\n4. Challenge section — Prompt + Template + SKILL.md")
print("=" * 50)

check(
    "Prompt specifies hover-tile-grid with no inline styles",
    "hover-tile-grid" in main_py and "no inline styles" in main_py.lower().split("challenge")[1].split("solution")[0]
    if "challenge" in main_py.lower() else False,
    "Prompt should say challenge hover-tile-grid must have no inline styles"
)

check(
    "Prompt specifies exactly 4 challenge tiles",
    "exactly 4 tiles" in main_py.lower(),
    "Prompt should specify exactly 4 tiles in the challenge section"
)

check(
    "Prompt says no --light modifier on challenge grid",
    "--light" in main_py.split("Challenge")[1].split("Solution")[0]
    if "Challenge" in main_py else False,
    "Prompt should warn not to use --light on the challenge grid"
)

check(
    "Prompt says no h4/h5 in challenge tiles",
    "h4" in main_py.split("Challenge")[1].split("Solution")[0]
    or "h5" in main_py.split("Challenge")[1].split("Solution")[0]
    if "Challenge" in main_py else False,
    "Prompt should say use h3 for titles, not h4/h5"
)

check(
    "Prompt says no checklists in challenge tiles",
    "checklist" in main_py.lower().split("challenge")[1].split("solution")[0]
    or "<ul>" in main_py.split("Challenge")[1].split("Solution")[0]
    if "Challenge" in main_py else False,
    "Prompt should say no <ul> checklists in challenge tiles"
)

# Template challenge section
challenge_start = template.find('hover-tile-grid', template.find('hover-tile-grid-section'))
challenge_grid_line = template[challenge_start:challenge_start+200] if challenge_start >= 0 else ""

check(
    "Template challenge grid has no inline style",
    'hover-tile-grid" role=' in template or 'hover-tile-grid">' in template,
    "Template challenge grid should not have inline style attributes"
)

check(
    "SKILL.md documents challenge tile dark theme",
    "challenge" in skill_md.lower() and "dark" in skill_md.lower(),
    "SKILL.md should document the challenge tiles dark theme pattern"
)

check(
    "SKILL.md says no --light on challenge grid",
    "--light" in skill_md and "challenge" in skill_md.lower(),
    "SKILL.md should warn against --light modifier on challenge grid"
)


# ── 5. SOLUTION SECTION ───────────────────────────────────

print("\n5. Solution section — Prompt + SKILL.md")
print("=" * 50)

# Extract the solution section text from main.py
solution_block = ""
if "Solution section" in main_py:
    solution_block = main_py.split("Solution section")[1].split("Non-negotiable")[0]

check(
    "Prompt specifies hover-tile-grid--light for solution",
    "hover-tile-grid--light" in solution_block,
    "Prompt should tell agent to use --light variant for solution tiles"
)

check(
    "Prompt specifies icon stroke #006DCD",
    "#006DCD" in solution_block,
    "Prompt should specify blue-03 (#006DCD) for light-bg icon strokes"
)

check(
    "Prompt specifies hover-tile-checklist",
    "hover-tile-checklist" in solution_block,
    "Prompt should specify the checklist class for solution tile bullets"
)

check(
    "Prompt specifies stroke=currentColor for checklist SVGs",
    "currentColor" in solution_block,
    "Prompt should specify currentColor for checklist SVG strokes"
)

check(
    "Prompt says no inline styles on solution tiles",
    "inline style" in solution_block.lower(),
    "Prompt should warn against inline styles on solution tiles"
)

check(
    "SKILL.md documents solution tile light theme",
    "solution" in skill_md.lower() and "light" in skill_md.lower() and "hover-tile-grid--light" in skill_md,
    "SKILL.md should document the solution tiles light theme pattern"
)

check(
    "SKILL.md specifies #006DCD for solution icons",
    "#006DCD" in skill_md,
    "SKILL.md should specify blue-03 stroke for solution tile icons"
)


# ── 6. HOW IT WORKS SECTION ────────────────────────────────

print("\n6. How It Works — Prompt + SKILL.md")
print("=" * 50)

hiw_block = ""
if "How It Works section" in main_py:
    hiw_block = main_py[main_py.find("How It Works section"):main_py.find("Non-negotiable output rules")]

check(
    "Prompt specifies --light --3col for How It Works",
    "hover-tile-grid--light" in hiw_block and "hover-tile-grid--3col" in hiw_block,
    "Prompt should specify both --light and --3col modifiers"
)

check(
    "Prompt specifies exactly 3 cards",
    "exactly 3 cards" in hiw_block.lower() or "exactly 3" in hiw_block.lower(),
    "Prompt should specify exactly 3 cards for How It Works"
)

check(
    "Prompt deprecates list-title-section",
    "list-title-section" in hiw_block and "deprecated" in hiw_block.lower(),
    "Prompt should say list-title-section is deprecated"
)

check(
    "SKILL.md documents How It Works 3-column pattern",
    "3-column" in skill_md and "hover-tile-grid--3col" in skill_md,
    "SKILL.md should document the How It Works 3-column tile pattern"
)


# ── 6b. ENTERPRISE SECTION ────────────────────────────────

print("\n6b. Enterprise section — Prompt + SKILL.md")
print("=" * 50)

ent_block = ""
if "Enterprise section" in main_py:
    ent_block = main_py[main_py.find("Enterprise section"):main_py.find("Non-negotiable output rules")]

check(
    "Prompt specifies hover-tile-grid--light for enterprise",
    "hover-tile-grid--light" in ent_block,
    "Prompt should tell agent to use --light variant for enterprise tiles"
)

check(
    "Prompt specifies --3col for 3 groups",
    "hover-tile-grid--3col" in ent_block and "3 groups" in ent_block.lower(),
    "Prompt should specify --3col when enterprise has 3 groups"
)

check(
    "Prompt specifies 2-col for 2 groups",
    "2-col" in ent_block.lower() or "2 groups" in ent_block.lower(),
    "Prompt should specify default 2-col when enterprise has only 2 groups"
)

check(
    "Prompt deprecates ring-split",
    "ring-split" in ent_block and "deprecated" in ent_block.lower(),
    "Prompt should say ring-split is deprecated"
)

check(
    "Prompt deprecates list-item-group",
    "list-item-group" in ent_block and "deprecated" in ent_block.lower(),
    "Prompt should say list-item-group is deprecated"
)

check(
    "Prompt says no inline styles on enterprise tiles",
    "inline style" in ent_block.lower(),
    "Prompt should warn against inline styles on enterprise tiles"
)

check(
    "SKILL.md documents enterprise tile pattern",
    "enterprise" in skill_md.lower() and "hover-tile-grid--light" in skill_md,
    "SKILL.md should document the enterprise tile pattern"
)

check(
    "SKILL.md says ring-split is deprecated",
    "ring-split" in skill_md and "deprecated" in skill_md.lower(),
    "SKILL.md should say ring-split is deprecated for enterprise"
)

check(
    "SKILL.md documents 2-col vs 3-col choice",
    "2-col" in skill_md.lower() or "2 groups" in skill_md.lower(),
    "SKILL.md should document when to use 2-col vs 3-col"
)


# ── 6c. SOCIAL PROOF / QUOTE SECTION ─────────────────────

print("\n6c. Quote section — Prompt + SKILL.md")
print("=" * 50)

quote_block = ""
if "Social proof / quote section" in main_py:
    quote_block = main_py[main_py.find("Social proof / quote section"):main_py.find("Non-negotiable output rules")]

check(
    "Prompt specifies .quote-ring component",
    "quote-ring" in quote_block and "quote-ring__source" in quote_block,
    "Prompt should specify the quote-ring component structure"
)

check(
    "Prompt specifies separate quote-ring per quote",
    "separate" in quote_block.lower() and "multiple" in quote_block.lower(),
    "Prompt should say each quote gets its own quote-ring"
)

check(
    "Prompt specifies social-h2 heading ID",
    "social-h2" in quote_block and "not proof-h2" in quote_block.lower(),
    "Prompt should specify social-h2 as heading ID"
)

check(
    "Prompt specifies BEM class names for result",
    "quote-ring__source-result-lbl" in quote_block,
    "Prompt should specify full BEM names for result label/value"
)

check(
    "Prompt says no inline styles on quote-ring",
    "inline style" in quote_block.lower(),
    "Prompt should warn against inline styles on quote-ring elements"
)

check(
    "Prompt deprecates quote-inner",
    "quote-inner" in quote_block and "deprecated" in quote_block.lower(),
    "Prompt should say quote-inner is deprecated"
)

check(
    "SKILL.md documents quote-ring component",
    "quote-ring" in skill_md and "quote-ring__source" in skill_md,
    "SKILL.md should document the quote-ring component"
)

check(
    "SKILL.md says separate quote-ring per quote",
    "separate" in skill_md.lower() and "quote-ring" in skill_md,
    "SKILL.md should document multiple quotes get separate rings"
)

check(
    "SKILL.md deprecates quote-inner",
    "quote-inner" in skill_md and "deprecated" in skill_md.lower(),
    "SKILL.md should say quote-inner is deprecated"
)


# ── 7. SEC-HEADER RULES ───────────────────────────────────

print("\n7. Section headers — Prompt + SKILL.md")
print("=" * 50)

sec_header_rule = main_py[main_py.find("Section headers (.sec-header)"):main_py.find("Section headers (.sec-header)") + 500] if "Section headers (.sec-header)" in main_py else ""

check(
    "Prompt specifies sec-header uses h2 + p",
    "<h2" in sec_header_rule and "<p>" in sec_header_rule,
    "Prompt should specify h2 for heading and p for intro in sec-headers"
)

check(
    "Prompt says no h3/h4 in sec-headers",
    "Do NOT use h3 or h4" in sec_header_rule,
    "Prompt should warn against h3/h4 for sec-header heading or intro"
)

check(
    "Prompt says no inline styles on sec-headers",
    "inline" in sec_header_rule.lower(),
    "Prompt should warn against inline styles on sec-header elements"
)

check(
    "SKILL.md documents sec-header structure",
    "sec-header" in skill_md and "<h2" in skill_md and "never h3" in skill_md.lower(),
    "SKILL.md should document the sec-header h2 + p pattern"
)


# ── 7b. FAQ SECTION ──────────────────────────────────────────

print("\n7b. FAQ section — Prompt + Template + SKILL.md + Structure")
print("=" * 50)

# Template FAQ structure — find the full FAQ section
faq_section_start = template.find('<section class="faq-section"')
faq_section_end = template.find('</section>', faq_section_start) + len('</section>') if faq_section_start >= 0 else -1
faq_html = template[faq_section_start:faq_section_end] if faq_section_start >= 0 else ""

check(
    "Template uses .faq-ring grid (not .faq-tile-list)",
    "faq-ring" in faq_html and "faq-tile-list" not in faq_html,
    "Template FAQ should use .faq-ring two-column grid, not old .faq-tile-list"
)

check(
    "Template has .faq-ring__heading",
    "faq-ring__heading" in faq_html,
    "Template should have .faq-ring__heading for the left-column heading tile"
)

check(
    "Template has .faq-ring__list",
    "faq-ring__list" in faq_html,
    "Template should have .faq-ring__list for the right-column accordion tiles"
)

check(
    "Template FAQ does NOT use .sec-header",
    "sec-header" not in faq_html,
    "FAQ heading lives in .faq-ring__heading, not a .sec-header"
)

check(
    "Template FAQ tiles have aria-controls/aria-labelledby pairs",
    "aria-controls" in faq_html and "aria-labelledby" in faq_html,
    "FAQ tiles need aria-controls on button and aria-labelledby on answer"
)

check(
    "Template FAQ uses 16x16 SVG chevron (not 24x24)",
    'width="16" height="16"' in faq_html,
    "FAQ chevron SVG should be 16x16, not the old 24x24"
)

# CSS checks
check(
    "CSS has .faq-ring grid styles",
    ".faq-ring{" in template and "grid-template-columns" in template,
    "Stylesheet should define .faq-ring as a CSS grid"
)

check(
    "CSS has .faq-ring__heading--long modifier",
    ".faq-ring__heading--long" in template,
    "Stylesheet should have --long modifier for headings over 40 chars"
)

check(
    "CSS --long sets font-size:42px",
    "faq-ring__heading--long" in template and "42px" in template,
    "--long modifier should reduce heading font from 60px to 42px"
)

# Prompt checks
check(
    "Prompt references .faq-ring structure",
    "faq-ring" in main_py and "faq-ring__heading" in main_py,
    "HTML builder prompt should describe the faq-ring structure"
)

check(
    "Prompt explains --long class threshold (40 chars)",
    "40 characters" in main_py and "faq-ring__heading--long" in main_py,
    "Prompt should explain when to add --long modifier"
)

check(
    "Prompt says no .sec-header in FAQ",
    "Do NOT use .sec-header" in main_py or "NOT use .sec-header" in main_py or "not a sec-header" in main_py.lower(),
    "Prompt should warn against using sec-header in FAQ section"
)

# SEM-LP-Structure.md checks
check(
    "Structure doc describes faq-ring layout",
    "faq-ring" in sem_structure,
    "SEM-LP-Structure.md should reference the faq-ring layout"
)

check(
    "Structure doc mentions --long modifier",
    "faq-ring__heading--long" in sem_structure,
    "SEM-LP-Structure.md should document the --long modifier for long headings"
)

check(
    "Structure doc mentions 40-character threshold",
    "40 character" in sem_structure,
    "SEM-LP-Structure.md should specify the 40-char threshold"
)

# SKILL.md checks
check(
    "SKILL.md documents faq-ring (not just FAQ Accordion)",
    "faq-ring" in skill_md or "FAQ Ring" in skill_md,
    "SKILL.md should document the faq-ring two-column grid pattern"
)

check(
    "SKILL.md documents --long modifier",
    "faq-ring__heading--long" in skill_md,
    "SKILL.md should document the --long modifier"
)


# ── 7c. CTA RING SECTION ────────────────────────────────────

print("\n7c. CTA Ring section — Prompt + Template + SKILL.md + Structure")
print("=" * 50)

# Template CTA structure
cta_section_start = template.find('cta-ring')
cta_section_end = template.find('</section>', template.find('<section', template.rfind('<section', 0, template.find('</main>')))) + len('</section>') if cta_section_start >= 0 else -1
cta_html = template[template.rfind('<section', 0, template.find('</main>')):template.find('</section>', template.rfind('<section', 0, template.find('</main>'))) + len('</section>')] if cta_section_start >= 0 else ""

check(
    "Template uses .cta-ring (not .frame-cta)",
    "cta-ring" in cta_html and "frame-cta" not in cta_html,
    "Template CTA should use .cta-ring, not old .frame-cta"
)

check(
    "Template has .cta-ring__tile",
    "cta-ring__tile" in cta_html,
    "Template should have .cta-ring__tile wrapper"
)

check(
    "Template has .cta-ring__content and .cta-ring__text",
    "cta-ring__content" in cta_html and "cta-ring__text" in cta_html,
    "Template should have .cta-ring__content and .cta-ring__text"
)

check(
    "Template CTA does NOT use .sec-label",
    "sec-label" not in cta_html,
    "CTA ring should not contain .sec-label"
)

check(
    "Template CTA does NOT use .demo-chip",
    "demo-chip" not in cta_html,
    "CTA ring should not contain .demo-chip"
)

check(
    "Template CTA has no inline styles",
    'style=' not in cta_html,
    "CTA ring should have no inline styles"
)

check(
    "Template CTA primary button links to #hero-form",
    'href="#hero-form"' in cta_html,
    "Primary CTA should anchor to #hero-form"
)

check(
    "Template CTA secondary button uses button-secondary",
    "button-secondary" in cta_html and "button-inverse" not in cta_html,
    "Secondary CTA should use button-secondary, not button-inverse"
)

check(
    "Template CTA has .cta-trust with checkmark SVGs",
    "cta-trust" in cta_html and "cta-trust-item" in cta_html,
    "CTA should have .cta-trust with .cta-trust-item elements"
)

# CSS checks
check(
    "CSS has .cta-ring styles (not .frame-cta)",
    ".cta-ring{" in template and ".frame-cta" not in template,
    "Stylesheet should define .cta-ring, not .frame-cta"
)

check(
    "CSS has .cta-ring__tile",
    ".cta-ring__tile" in template,
    "Stylesheet should define .cta-ring__tile"
)

check(
    "CSS has .cta-ring .button-secondary override",
    ".cta-ring .button-secondary" in template,
    "Stylesheet should have button-secondary color overrides for cta-ring"
)

# Prompt checks
check(
    "Prompt references .cta-ring structure",
    "cta-ring" in main_py and "cta-ring__tile" in main_py,
    "HTML builder prompt should describe the cta-ring structure"
)

check(
    "Prompt says not to use .frame-cta",
    "frame-cta" in main_py.lower() and ("do not" in main_py.lower().split("frame-cta")[0][-50:] or "not" in main_py.lower().split("frame-cta")[0][-30:]),
    "Prompt should deprecate .frame-cta"
)

check(
    "Prompt says primary button links to #hero-form",
    "#hero-form" in main_py.split("Final CTA")[1].split("SEO")[0] if "Final CTA" in main_py else False,
    "Prompt should specify #hero-form as primary CTA href"
)

check(
    "Prompt says button-secondary (not button-inverse)",
    "button-secondary" in main_py.split("Final CTA")[1].split("SEO")[0]
    and "button-inverse" in main_py.split("Final CTA")[1].split("SEO")[0]
    if "Final CTA" in main_py else False,
    "Prompt should specify button-secondary and deprecate button-inverse"
)

# SEM-LP-Structure.md checks
check(
    "Structure doc describes cta-ring layout",
    "cta-ring" in sem_structure,
    "SEM-LP-Structure.md should reference the cta-ring layout"
)

check(
    "Structure doc says no .frame-cta",
    "frame-cta" not in sem_structure or "No `.frame-cta`" in sem_structure or "not .frame-cta" in sem_structure.lower(),
    "SEM-LP-Structure.md should not reference .frame-cta as current (deprecation note is OK)"
)

# SKILL.md checks
check(
    "SKILL.md documents CTA Ring pattern",
    "cta-ring" in skill_md or "CTA Ring" in skill_md,
    "SKILL.md should document the cta-ring component"
)

check(
    "SKILL.md says button-secondary for CTA",
    "button-secondary" in skill_md.split("CTA Ring")[1] if "CTA Ring" in skill_md else False,
    "SKILL.md should specify button-secondary in CTA Ring section"
)


# ── 8. SEM-LP-Structure.md ─────────────────────────────────

print("\n8. SEM-LP-Structure.md — Content rules")
print("=" * 50)

check(
    "References .hs-form-ring for hero form",
    "hs-form-ring" in sem_structure,
    "Structure doc should specify .hs-form-ring for the hero form"
)

check(
    "References .button-text for secondary CTA",
    "button-text" in sem_structure,
    "Structure doc should mention button-text for optional secondary link"
)


# ── 9. Brand guidelines ────────────────────────────────────

print("\n9. brand-guidelines.md — Font references")
print("=" * 50)

check(
    "References Plantin MT Pro",
    "Plantin MT Pro" in brand_guide,
    "Should reference the actual brand font, not the fallback"
)

check(
    "References Lab Grotesque",
    "Lab Grotesque" in brand_guide,
    "Should reference the actual body font"
)

check(
    "Does NOT recommend adding Google Fonts links",
    "Do NOT add Google Fonts" in brand_guide or "do not add google fonts" in brand_guide.lower(),
    "Should explicitly say not to add Google Fonts links"
)


# ── RESULTS ─────────────────────────────────────────────────

print("\n" + "=" * 50)
total = passed + failed
print(f"\nResults: {passed}/{total} passed, {failed} failed")

if failed == 0:
    print("\nAll checks passed — the agent will generate heroes, challenge, and solution sections matching the finalized design.")
else:
    print(f"\n{failed} check(s) failed — review the items above before merging.")

sys.exit(1 if failed else 0)
