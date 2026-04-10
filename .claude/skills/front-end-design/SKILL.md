---
name: frontend-design-datahub
description: Create distinctive, production-grade frontend interfaces for DataHub that strictly follow the DataHub Brand Guidelines v1.2 (2026). Use this skill when building DataHub web components, landing pages, diagrams, or UI artifacts. Generates polished, brand-compliant code that avoids generic AI aesthetics while staying within DataHub's visual system.
license: Complete terms in LICENSE.txt
---

This skill guides creation of production-grade DataHub frontend interfaces. All aesthetic decisions — color, typography, layout, illustration — are constrained by the DataHub Brand Guidelines v1.2 (2026). The goal is pages and components that feel designed, not generated: precise, confident, and unmistakably DataHub.

The user provides frontend requirements: a component, page, application, or interface to build. They may include context about the purpose, audience, or technical constraints.

---

## Design Thinking

Before coding, understand the context and commit to a brand-aligned aesthetic direction:

- **Purpose**: What problem does this interface solve? Who uses it? (Platform Engineer or Economic Buyer?)
- **Palette mode**: Which of the three DataHub color weighting approaches fits? Neutral, Neutral + Highlights, or Tonal?
- **Tonal group**: Which brand color group anchors this page? Blue (default for most LP work), Green, Magenta, or Orange?
- **Illustration type**: Is a visual needed? If so — 3D Render (high-impact/abstract), Explainer (concept diagram), or Stylized UI (product showcase)?
- **Constraints**: Technical requirements (HTML/CSS, React, accessibility, HubSpot embed).
- **Differentiation**: What makes this page feel *considered* rather than templated? What is the one compositional or typographic choice that elevates it?

**CRITICAL**: The DataHub brand has a clear visual system with real flexibility inside it. The job is not to impose an external aesthetic — it is to make *excellent choices within the system* and execute them with precision. Brand compliance and visual distinction are not in conflict.

---

## LAYOUT INTEGRITY RULES

These rules prevent the most common generation failures. They are non-negotiable and take precedence over creative decisions.

### Hero balance rule
The hero uses `display: flex` with two equal `flex: 1` columns. The LEFT column (`hero-text`) and RIGHT column (`hero-visual` form card) must be visually balanced at approximately 500px height each. This means:

- `hero-sub` paragraph: **≤180 characters** — strictly enforced. If copy is longer, the left column grows and the form card floats awkwardly in the middle.
- `hero-bullets`: exactly 3 items, each **≤80 characters** — no line wrapping.
- When in doubt, cut the `hero-sub` — the bullets carry the specifics.

### Feature items must always be 2-column (text + image)
Each `.content-highlight-inner` must have exactly 2 children: `.ch-text` (flex: 1) and `.ch-visual` (flex: 1). Rules:

- Odd-numbered features, or features that lack an image placeholder, will collapse to 1-column.
- Always include `<figure class="framed-image">` inside `.ch-visual`. Use `<img src="" alt="[descriptive alt]">` if no image URL is available — never substitute a card, div, or text block for the figure.
- The 4th feature item may use a `.list-title-section` dark card as its visual; wrap it in `<div class="ch-visual">`.

### The `.reverse` alternation pattern
Even-indexed feature items (0-indexed: items 1 and 3) must get `class="content-highlight-inner reverse"` to alternate image left/right. Applying `.reverse` inconsistently breaks the visual zigzag rhythm. Checklist before output:
- Item 0: `content-highlight-inner` (no reverse)
- Item 1: `content-highlight-inner reverse`
- Item 2: `content-highlight-inner` (no reverse)
- Item 3: `content-highlight-inner reverse`

### Section gaps come from `main { gap: 120px }` — do not add margin to sections
Sections themselves have zero padding and zero margin. Vertical rhythm comes entirely from the `main` flex gap. Never add `margin-top` or `margin-bottom` to `<section>` elements or their `.container` wrappers. Adding extra margin is the primary cause of irregular vertical spacing.

### Never use bare `section { }` CSS rules
Only `.hero` and `.logo-scroller` have section-level classes. All other sections are unstyled `<section>` elements. Never write CSS rules targeting a bare `section` selector in the generated `<style>` block — it will bleed styles into all sections and corrupt layout. Always target inner component classes (`.sec-header`, `.hover-tile-grid`, `.content-highlight`, etc.).

---

## Brand Color System

Use only these exact hex values. Never invent colors outside this palette.

```css
:root {
  /* Neutrals */
  --dh-black:      #000000;
  --dh-off-black:  #161616;
  --dh-neutral-01: #1E1E1E;
  --dh-neutral-02: #3F3F3F;
  --dh-neutral-03: #767473;
  --dh-neutral-04: #B2AEA7;
  --dh-neutral-05: #E3E1D6;
  --dh-off-white:  #F2F1EE;
  --dh-white:      #FFFFFF;

  /* Blue — primary tonal group */
  --dh-blue-01: #002131;   /* Dark */
  --dh-blue-02: #0A4170;   /* Rich */
  --dh-blue-03: #006DCD;   /* Midtone */
  --dh-blue-04: #3CBBEB;   /* Bright */
  --dh-blue-05: #B0EAFC;   /* Light */

  /* Green */
  --dh-green-01: #0A261E;
  --dh-green-02: #004843;
  --dh-green-03: #008070;
  --dh-green-04: #0FC691;
  --dh-green-05: #AAF1BB;

  /* Magenta */
  --dh-magenta-01: #40002D;
  --dh-magenta-02: #7F004B;
  --dh-magenta-03: #CB3276;
  --dh-magenta-04: #FF85CE;
  --dh-magenta-05: #FCD6E4;

  /* Orange */
  --dh-orange-01: #3B0F00;
  --dh-orange-02: #820D00;
  --dh-orange-03: #D23500;
  --dh-orange-04: #EC9E32;
  --dh-orange-05: #F5E0A7;

  /* Typography */
  --font-headline: 'Plantin', 'Castoro', Georgia, serif;
  --font-body:     'Lab Grotesque', 'Geist', sans-serif;

  /* Transitions */
  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-base: 300ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-slow: 500ms cubic-bezier(0.4, 0, 0.2, 1);
}
```

### Color Weighting — Choose One Per Page

| Mode | When to Use | How |
|---|---|---|
| **Neutral** | Information-dense, practical pages | Primarily `--dh-black`, `--dh-white`, neutrals. Color used sparingly. |
| **Neutral + Highlights** | Default for brand-forward LP pages | Blacks & whites dominant; one tonal group for accents, CTAs, badges. |
| **Tonal** | High-impact hero sections, feature callouts | One full tonal group (e.g., all Blue 01–05) used boldly across a section. |

### Legibility Rules

- Dark 01 on Light 05 = AAA accessible ✅
- Midtone on midtone = likely FAIL — avoid ❌
- Always test colored text on colored backgrounds before using
- Do not use low-contrast type on images

### Color Prohibitions

- Do not use colors outside the brand palette
- Do not adjust color transparency
- Do not use illegible color combinations
- Do not place the logo on off-palette backgrounds

---

## Typography

### Typefaces

| Role | Primary | Google Fonts Fallback |
|---|---|---|
| Headlines / Brand | Plantin (Adobe Fonts) | Castoro |
| Body / UI / Small text | Lab Grotesque (Letters From Sweden) | Geist |

### Font Loading (HTML pages)

```html
<!-- Google Fonts fallbacks — use when brand fonts unavailable -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Castoro:ital@0;1&family=Geist:wght@300;400;500;600&display=swap" rel="stylesheet">
```

### Type Rules

- Headlines: sentence case (not Title Case), unless it is a title or H1
- Section headers: sentence case
- No italic text — `font-style: normal` everywhere; never use `<em>` or `<i>` tags
- Do not use Inter, Roboto, Arial, or system fonts — these are explicitly not DataHub fonts
- Icons: use Google Material Icons alongside Lab Grotesque; Light weight with 300 weight icons, Medium with 600 weight icons

---

## Layout System

### The Frame

DataHub layouts use a **frame-and-tile** system: a containing outer frame with inner tiles that hold content, aligned to an underlying grid.

Three layout modes — choose the one that fits the content:

| Layout | Description | Best For |
|---|---|---|
| **Full Frame** | All elements contained within the frame; tight and structured | Heavily branded sections, hero areas |
| **Half Frame** | Hero/logo get open whitespace; body content framed | Brand-forward with breathing room |
| **Framed Image** | Only the image is set in a frame | Image-prominent sections |

### Layout Principles

- Tiles can be any shape or size needed to contain their content — align to the underlying grid
- Use asymmetry, generous negative space, and intentional overlap
- Grid-breaking elements are permitted when they serve the composition
- Avoid predictable symmetrical layouts with equal column widths throughout

### Layout Prohibitions

- Do not break the grid arbitrarily — asymmetry must be intentional
- Do not crowd tiles — spacing is part of the brand character
- Do not use layout patterns that feel generic or templated

---

## Illustration & Graphics

### Three Illustration Types — Choose by Purpose

**3D Renders**
- Use for: high-impact hero backgrounds, brand-forward campaign visuals
- Portrays the speed and precision of DataHub abstractly
- Best paired with the Tonal color weighting mode

**Explainer Diagrams**
- Use for: concept illustrations, architecture diagrams, "how it works" visuals
- Built from: outer frame → inner tiles → 2D primitives (shapes) → connecting lines with arrows
- Corner radius on connecting lines equals corner radius of tiles
- Avoid showing anything that closely resembles actual UI — keep conceptual
- Keep relatively simple: basic shapes + text + icons + logos

**Stylized UI**
- Use for: product feature showcases, landing page product visuals
- Resembles actual DataHub UI but simplified and styled for visual appeal
- Apply brand color palette — can use any tonal group
- Simplify — show the concept, not raw screenshot complexity

### Visual Rules (All Types)

- Every visual must have: `alt` text (include primary keyword naturally) + a caption
- No invented metrics or placeholder logos in visuals
- No raw screenshots — use Stylized UI treatment instead
- Use the brand color palette for all illustration fills and strokes

---

## Motion & Interaction

- Prioritize CSS-only animations for HTML artifacts
- One well-orchestrated page load with staggered reveals (`animation-delay`) creates more impact than scattered micro-interactions
- Hover states should be subtle and purposeful — not decorative
- Use scroll-reveal for below-the-fold content sections
- Avoid animations that feel playful or consumer-product — DataHub's motion should feel precise and confident

**Permitted animation patterns:**
- Staggered fade-in on page load (sections, cards, bullets)
- Subtle translateY on hover for cards
- Underline reveal on nav links
- Logo/trust strip scroll marquee

**Avoid:**
- Bouncing, elastic, or spring animations
- Heavy particle effects or generative motion
- Anything that reads as "startup landing page energy"

---

## Component Patterns

### CTA Buttons

```css
/* Primary CTA — use brand tonal color as background */
.btn-primary {
  background: var(--dh-blue-03);
  color: var(--dh-white);
  font-family: var(--font-body);
  font-weight: 500;
  border-radius: 4px;
  padding: 12px 24px;
  border: none;
  transition: background var(--transition-fast);
}
.btn-primary:hover {
  background: var(--dh-blue-02);
}

/* Secondary CTA */
.btn-secondary {
  background: transparent;
  color: var(--dh-neutral-01);
  border: 1.5px solid var(--dh-neutral-03);
  font-family: var(--font-body);
  border-radius: 4px;
  padding: 12px 24px;
  transition: border-color var(--transition-fast), color var(--transition-fast);
}
.btn-secondary:hover {
  border-color: var(--dh-blue-03);
  color: var(--dh-blue-03);
}
```

### Trust / Logo Strip

- 3–6 logos, grayscale at rest, color on hover
- Scrolling marquee animation for density
- Keep opacity at ~60% at rest — don't let logos compete with content

### Testimonial Blocks

- Always include: quote, full name, title, company
- Prefer quotes that name a specific problem solved — not general praise
- Pair with company logo or avatar initials

### FAQ Accordion

- Question visible, answer collapsed by default
- Expand on click with smooth max-height transition
- No CTA inside FAQ answers

---

## Accessibility

- All color combinations must pass WCAG AA minimum (AAA preferred)
- All images and icons must have descriptive `alt` text
- Interactive elements must have visible focus states
- Use semantic HTML: `<nav>`, `<main>`, `<section>`, `<article>`, `<footer>`
- `aria-expanded` on accordion triggers
- Sufficient touch target sizes (minimum 44×44px) for mobile

---

## SVG Conversion Mode

### When to Enter This Mode

Enter SVG Conversion Mode when the request includes a **source image or diagram to rebrand** into a brand-compliant DataHub illustration. Triggered by phrases like:
- "Convert this to brand"
- "Rebrand this diagram"
- "Turn this into an SVG"
- "Make this DataHub-compliant"

Do not enter this mode for net-new design requests — use the standard design flow above.

---

### Conversion Process (Strict Order)

**Step 1 — Parse the source**
Before writing any code, analyze the source image and extract:
- Overall structure: how many distinct regions, sections, or groupings exist?
- Hierarchy: what is the center/primary element? What are secondary/supporting elements?
- Flow direction: top-down, hub-and-spoke, left-right, layered?
- Labels: capture all text exactly as written — do not paraphrase or rename
- Connectors: note arrow directions, which elements connect to which
- Icon concepts: what does each icon represent? (You will replace them with brand-compliant SVG equivalents)

**Step 2 — Map to brand illustration type**
Choose the correct DataHub illustration type for the content:

| Source Content | Map To |
|---|---|
| Architecture / flow / concept diagram | Explainer |
| Product UI or feature showcase | Stylized UI |
| Abstract / hero / brand-forward visual | 3D Render treatment (CSS/SVG approximation) |

For most architecture diagrams (like platform maps): **Explainer**.

**Step 3 — Map visual elements to brand equivalents**

| Source Element | Brand-Compliant Equivalent |
|---|---|
| Colored section backgrounds | Brand tonal group fills (Blue 05 for light sections, Blue 01/02 for dark) |
| Decorative 3D icons | Flat SVG icons, stroke-only, `stroke="var(--dh-blue-03)"`, `stroke-width="1.8"`, no fill |
| Gradient blobs / glows | Solid brand color tiles with `border-radius: var(--r)` |
| Circle icon containers | `<circle>` or `<rect rx>` in White with Blue 04 stroke |
| Center hub shape | Brand-appropriate primitive (hexagon via `<polygon>`, circle, or rounded rect) |
| Arrow connectors | `<path>` or `<line>` with `marker-end` arrowhead, stroke color `var(--dh-blue-04)` |
| Section header labels | Uppercase, letter-spaced, Geist font, Blue 02 color |
| Dashed borders | `stroke-dasharray="6 3"` on outer frame strokes where appropriate |
| Drop shadows / glows | Remove entirely — not part of the explainer illustration system |
| Off-brand colors (purple, red, generic blue) | Replace with nearest brand tonal equivalent |

**Step 4 — Apply the frame-and-tile structure**
Every conversion must use the DataHub frame system:
- One **outer frame** contains all content — `<rect>` with brand stroke, rounded corners
- **Inner tiles** subdivide the content — each section gets its own tile
- Tiles must align to an implied grid — use consistent x/y positioning
- Corner radius on connecting lines = corner radius of tiles
- Do not nest tiles inside each other
- Do not mix stroke colors within a single frame
- Do not use pill shapes as tiles

**Step 5 — Output clean, portable SVG**
- Output a single self-contained `<svg>` file
- Use `viewBox` (not fixed `width`/`height`) so the SVG scales correctly
- Embed Google Fonts via `<defs><style>@import url(...)</style></defs>` for Castoro and Geist
- Use `<defs>` for reusable elements: arrowhead markers, color variables, repeated icon shapes
- All text must use `font-family="'Geist', sans-serif"` for labels and `font-family="'Castoro', Georgia, serif"` for titles
- Group related elements with `<g>` and meaningful `id` attributes
- Include `<title>` and `<desc>` for accessibility

---

### SVG Output Template Structure

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 640" role="img">
  <title>Diagram Title</title>
  <desc>Brief description of what the diagram shows</desc>

  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Castoro&family=Geist:wght@300;400;500;600&display=swap');
    </style>
    <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="#3CBBEB"/>
    </marker>
  </defs>

  <rect x="20" y="20" width="920" height="600" rx="12" ry="12"
        fill="#FFFFFF" stroke="#3CBBEB" stroke-width="1.5"/>

  <!-- Section tiles, icons, connectors, labels... -->
</svg>
```

---

### SVG Conversion Rules

**Always:**
- Preserve all original labels verbatim — do not rename sections or items
- Preserve the original flow direction and hierarchy
- Replace every icon with a flat, stroke-only SVG equivalent at consistent size (20×20 or 24×24)
- Use `role="img"` on the root `<svg>` with `<title>` and `<desc>`
- Test that the viewBox contains all content with adequate padding (minimum 20px inset)

**Never:**
- Invent new sections, labels, or connections not present in the source
- Use colors outside the brand palette
- Use filled icons — stroke-only only
- Add drop shadows, glows, or blur effects
- Use raster images (`<image>`) inside the SVG output
- Use `px` units on SVG attributes — use unitless numbers inside `viewBox`
- Nest tiles inside other tiles
- Use pill/stadium shapes as tiles (fully rounded rectangles where width >> height)

---

### Conversion QA Checklist

Before finalizing SVG output, verify:
- [ ] All source labels preserved exactly
- [ ] All source connections and flow directions preserved
- [ ] Outer frame present and contains all elements
- [ ] Inner tiles align to implied grid, consistent corner radius
- [ ] All icons are flat, stroke-only, brand color
- [ ] No colors outside brand palette
- [ ] No drop shadows or glow effects
- [ ] Fonts: Castoro for titles, Geist for labels
- [ ] `viewBox` set correctly — no content clipped
- [ ] `<title>` and `<desc>` present
- [ ] Arrowhead markers defined in `<defs>` and referenced correctly
- [ ] SVG is self-contained — no external dependencies except Google Fonts

---

## What This Skill Never Does

Even when the user requests creative latitude:

- Never uses italic text — no `font-style: italic`, no `<em>`, no `<i>`
- Never uses Inter, Roboto, Arial, or system fonts
- Never invents colors outside the DataHub brand palette
- Never uses purple gradients on white — this is explicitly off-brand
- Never uses generic "startup" layout patterns (centered hero, two-column features, purple CTA button)
- Never adds countdown timers, urgency signals, or scarcity language
- Never uses vague or unattributed social proof
- Never uses minimizing language in copy ("just", "simply", "easy")
- Never places the DataHub logo on off-palette backgrounds
- Never adjusts color transparency
- Never uses raw screenshots — always Stylized UI treatment
- Never writes bare `section { }` CSS rules — targets inner component classes only
- Never adds `margin-top` or `margin-bottom` to `<section>` elements — vertical rhythm comes from `main { gap: 120px }` only
- Never substitutes a card or div for `<figure class="framed-image">` inside `.ch-visual`

---

## Quick Decision Guide

| Question | Answer |
|---|---|
| Which font for headlines? | Plantin → Castoro fallback |
| Which font for body/UI? | Lab Grotesque → Geist fallback |
| Which color for a primary CTA? | Blue 03 (`#006DCD`) default; or active tonal group midtone |
| Which color for a dark hero background? | Blue 01 (`#002131`) or Off-Black (`#161616`) |
| Which color for a light page background? | Off-White (`#F2F1EE`) or White (`#FFFFFF`) |
| Which illustration style for "how it works"? | Explainer diagram |
| Which illustration style for a product callout? | Stylized UI |
| Which illustration style for a hero visual? | 3D Render or Tonal color block |
| Light or dark theme? | Either — choose based on page intent. Dark = authority/impact. Light = clarity/approachability. |
| Hero sub copy is too long — what to cut? | Cut `hero-sub` first. Bullets carry specifics. |
| `.reverse` on which feature items? | Items 1 and 3 (0-indexed). Items 0 and 2 have no `.reverse`. |
