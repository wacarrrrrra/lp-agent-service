# DataHub Brand Guidelines — Agent Reference
> Use this file as the hard constraint layer when generating HTML landing pages or product graphics for DataHub. All rules here are drawn from the DataHub Brand Guidelines v1.2 (2026), Editorial Style Guide, and Writing in 2026 Best Practices.

---

## 1. VOICE & TONE

**The DataHub voice:** An experienced architect explaining why foundations matter. Confident, not arrogant. Substantive without being erudite.

- Lead with practitioner insights and concrete outcomes — not marketing claims
- Use precise technical language when it matters; plain language everywhere else
- Be direct about trade-offs and implementation realities
- Choose strategic clarity over buzzwords
- Prove value through specific examples, not abstract promises

**Prohibited tone patterns:**
- Do not oversell or hype
- Do not use vague "AI-powered" filler phrases
- Do not make unsupported product claims
- Do not use passive voice when active is possible ("by zombies" test)
- Do not use long words where short ones work
- Do not use jargon if an everyday equivalent exists

**Writing rules:**
- Say what you mean. Be accurate. Don't exaggerate.
- CTAs and headlines must reflect actual value — no clickbait
- Lead with the most important point; don't bury the lede
- Keep to one tense
- Address the reader directly with "you" where natural
- Rule of three for rhythm, but use sparingly — don't force it
- Get into the content immediately; no "clearing your throat" preamble

---

## 2. GRAMMAR & STYLE

### Abbreviations & Acronyms
- Write out the full name on first use with abbreviation in parentheses: "Model Context Protocol (MCP)"
- Don't spell out well-known acronyms like CEO, AI
- No periods in capital abbreviations: US not U.S.
- Use periods in lowercase abbreviations

### Capitalization
- Title tags: Title Case
- Meta descriptions: Sentence case
- H1: Follow brand style guide casing (typically sentence case for DataHub)
- H2s: Phrase as questions when natural; follow style guide casing

### Numerals
- (Follow AP style unless otherwise specified in brand guide)

### Punctuation
- Oxford comma: use for clarity
- Em dashes for strong breaks; en dashes for ranges
- Exclamation marks: use sparingly

---

## 3. SEO / AEO WRITING RULES

| Element | Rule |
|---|---|
| Page title | Under 60 characters. Include primary keyword. Title Case. Format: `[Title] \| DataHub` |
| Meta description | Under 140 characters. Include keyword + reason to click. Sentence case. |
| H1 | Under 80 characters. Include primary keyword/entity verbatim. |
| H2s | Phrase as questions when natural. Used to organize content logically. |
| First hyperlink | Link to the "money page"; anchor from the relevant keyphrase. |
| Keyword density | 0.8%–1.5%. No stuffing. |
| Primary entity | Define it early. Expand acronyms on first use. Use low-ambiguity language. Re-anchor in later sections. Consider "negative clarification" (what it's NOT). |
| Secondary entities | Name explicitly. Add a brief clarifying sentence on first use. Avoid pronouns ("it", "this") before the name is anchored. |

**Primary search term must appear in:**
- Title tag
- H1 (verbatim)
- First 100 words
- At least one H2
- Meta description

---

## 4. BRAND COLORS

### Palette Structure
The brand palette uses warm neutrals + four tonal groups: Blue, Green, Magenta, Orange.
Each group has 5 values: Dark (01) → Rich (02) → Midtone/Bright (03) → Bright/Light (04) → Light/Pale (05).

### Key Color Hex Values

**Neutrals**
| Name | Hex |
|---|---|
| Black | `#000000` |
| Off-Black | `#161616` |
| Neutral 01 | `#1E1E1E` |
| Neutral 02 | `#3F3F3F` |
| Neutral 03 | `#767473` |
| Neutral 04 | `#B2AEA7` |
| Neutral 05 | `#E3E1D6` |
| Off-White | `#F2F1EE` |
| White | `#FFFFFF` |

**Blue (Primary Tonal Group)**
| Name | Hex |
|---|---|
| Blue 01 (Dark) | `#002131` |
| Blue 02 (Rich) | `#0A4170` |
| Blue 03 (Midtone) | `#006DCD` |
| Blue 04 (Bright) | `#3CBBEB` |
| Blue 05 (Light) | `#B0EAFC` |

**Green**
| Name | Hex |
|---|---|
| Green 01 (Dark) | `#0A261E` |
| Green 02 (Rich) | `#004843` |
| Green 03 (Midtone) | `#008070` |
| Green 04 (Bright) | `#0FC691` |
| Green 05 (Light) | `#AAF1BB` |

**Magenta**
| Name | Hex |
|---|---|
| Magenta 01 (Dark) | `#40002D` |
| Magenta 02 (Rich) | `#7F004B` |
| Magenta 03 (Midtone) | `#CB3276` |
| Magenta 04 (Bright) | `#FF85CE` |
| Magenta 05 (Light) | `#FCD6E4` |

**Orange**
| Name | Hex |
|---|---|
| Orange 01 (Dark) | `#3B0F00` |
| Orange 02 (Rich) | `#820D00` |
| Orange 03 (Midtone) | `#D23500` |
| Orange 04 (Bright) | `#EC9E32` |
| Orange 05 (Light) | `#F5E0A7` |

### Color Weighting Approaches

| Approach | When to Use |
|---|---|
| **Neutral Palette** | Practical, information-dense applications. Primarily blacks & whites with neutrals for variation. |
| **Neutral + Highlights** | Default for brand-forward applications. Blacks & whites + one tonal group for highlights. |
| **Tonal Palette** | High-impact, heavily brand-focused. One full tonal group for maximum color impact. |

### Color Rules
- Do not use solid colors outside of the brand palette
- Do not use illegible color combinations (refer to legibility chart)
- Do not adjust transparency of colors
- Do not use low-contrast type (especially on images)
- Do not use the logo on colors outside the palette
- Do not change the colors of the multi-color logo
- Dark (01) on Light (05) = AAA accessible. Midtone/Bright combinations may fail — check the legibility chart.

---

## 5. TYPOGRAPHY

### Primary Typeface: Plantin
- A sturdy serif; use for headlines and brand-forward applications
- Available from Adobe Fonts (`fonts.adobe.com/fonts/plantin`) or Monotype

### Secondary Typeface: Lab Grotesque
- A neo-grotesque; subtle technical feel
- Best for body copy and small text
- Available from Letters From Sweden (`lettersfromsweden.se/font/lab-grotesque`)
- Weights: Light, Medium

### Google Fonts Alternatives (if brand fonts unavailable)
- Plantin alternative: **Castoro** (`fonts.google.com/specimen/Castoro`)
- Lab Grotesque alternative: **Geist** (`fonts.google.com/specimen/Geist`)

### CSS Font Stack (HTML pages)
```css
/* Headlines */
font-family: 'Plantin', 'Castoro', Georgia, serif;

/* Body / UI */
font-family: 'Lab Grotesque', 'Geist', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
```

---

## 6. HTML PAGE STRUCTURE

### Required Sections (in order)

1. **`<head>`** — title tag, meta description, viewport, font imports
2. **Hero** — H1 (search term verbatim), subheadline, 3 bullets max, primary CTA button (anchor to form), embedded HubSpot form
3. **Trust Strip** — 3–6 enterprise logos + credibility line
4. **Problem Section** — H2 addressing pain, friction, risk, cost of inaction
5. **Solution Section** — H2 with 3–5 benefit blocks (H3 + 2–3 sentences each)
6. **How It Works** — H2, 3-step: Connect → Contextualize → Activate
7. **Technical Credibility** — H2, Bart-validated claims only. No invented metrics.
8. **Visual Section** — H2 "See It in Action", product UI / architecture diagram / before-after
9. **Social Proof** — H2, testimonial or stat
10. **FAQ** — H2, 3–6 questions with 3–5 sentence answers
11. **Final CTA** — H2, repeat CTA, embed form again
12. **Footer**

### Performance Rules
- Minimal nav — remove global nav on SEM pages
- Above-the-fold CTA required
- Page length: 900–1,500 words
- Mobile-friendly layout
- No unnecessary scripts
- No invented metrics or logos

### HubSpot Form Embed Script
```html
<script charset="utf-8" type="text/javascript" src="//js.hsforms.net/forms/embed/v2.js"></script>
<script>
  hbspt.forms.create({
    portalId: "14552909",
    formId: "FORM_ID_HERE",
    region: "na1"
  });
</script>
```

### HubSpot Form IDs by CTA Type
| CTA Type | formId |
|---|---|
| Demo | `ed2447d6-e6f9-4771-8f77-825b114a9421` |
| Free Trial | `42182785-f711-40b4-92e7-11468579321b` |
| Bi-weekly Demo | `2bf16106-3e8e-4dc3-9ae4-5b0bce901d88` |
| Product Tour | `aa56e90c-044a-46d8-a92f-cb905ad662f8` |

### CTA Button Labels by Type
| CTA Type | Button Label |
|---|---|
| Demo | "Request a Demo" |
| Free Trial | "Start Free Trial" |
| Product Tour | "See It in Action" |
| Bi-weekly Demo | "Join a Live Demo" |

### CSS Variable Template
```css
:root {
  /* Core Neutrals */
  --dh-black: #000000;
  --dh-off-black: #161616;
  --dh-neutral-01: #1E1E1E;
  --dh-neutral-03: #767473;
  --dh-neutral-05: #E3E1D6;
  --dh-off-white: #F2F1EE;
  --dh-white: #FFFFFF;

  /* Blue (primary tonal group) */
  --dh-blue-dark: #002131;
  --dh-blue-rich: #0A4170;
  --dh-blue-mid: #006DCD;
  --dh-blue-bright: #3CBBEB;
  --dh-blue-light: #B0EAFC;

  /* Green */
  --dh-green-dark: #0A261E;
  --dh-green-mid: #008070;
  --dh-green-bright: #0FC691;
  --dh-green-light: #AAF1BB;

  /* Magenta */
  --dh-magenta-dark: #40002D;
  --dh-magenta-mid: #CB3276;
  --dh-magenta-bright: #FF85CE;

  /* Orange */
  --dh-orange-mid: #D23500;
  --dh-orange-bright: #EC9E32;

  /* Typography */
  --font-headline: 'Plantin', 'Castoro', Georgia, serif;
  --font-body: 'Lab Grotesque', 'Geist', 'Inter', sans-serif;
}
```

---

## 7. GRAPHICS & ILLUSTRATION

### Three Illustration Types

**3D Renders**
- Best for: High-impact, heavily branded hero applications
- Portrays speed and precision of DataHub in an abstract way
- Use when you need maximum visual impact

**Explainer Diagrams**
- Best for: Illustrating concepts, software interactions, tech stacks
- Avoid showing anything that closely resembles actual UI
- Built from: outer frame, inner tiles, 2D primitives (shapes), connecting lines with arrows
- Corner radius on lines = corner radius of tiles
- Keep relatively simple — basic elements + text + icons + logos

**Stylized UI**
- Best for: Showcasing the product
- Resembles actual product UI but simplified and stylized
- Makes the product visually appealing and quick to digest
- Apply brand color palette (can use any tonal group)

### Layout Approaches for Graphics

| Layout | Description | Best For |
|---|---|---|
| **Full Frame** | All elements framed; tight and contained | Heavily branded, structured look |
| **Half Frame** | Hero/logo get whitespace; body content framed | Brand-forward with breathing room |
| **Framed Image** | Only the image is framed | Image-prominent compositions |

### Visual Rules
- Every visual must have: `alt` text (include primary keyword naturally) + a caption explaining what the viewer is seeing
- No invented metrics in visuals
- No placeholder logos
- Product screenshots in "Stylized UI" style — simplified, not raw screenshots
- Monotone treatment available for secondary applications

### Photography Style
- **Functional photography:** Authentic, real people, real environments
- **Illustrative photography:** Conceptual (e.g., rocket launch = speed). Unsplash-sourced images acceptable.
- Avoid low contrast. Avoid illegible color on image overlays.

---

## 8. LOGO RULES

- Never alter, modify, or redraw the logo
- Use the logo as the first-choice graphic element to represent the brand
- Do not place the logo on colors outside the brand palette
- Do not change the colors of the multi-color logo
- Do not use the logo on illegible color combinations

---

## 9. QUICK AGENT CHECKLIST

Before finalizing any HTML page or graphic asset, verify:

- [ ] Primary search term appears in title tag, H1, first 100 words, at least one H2, and meta description
- [ ] Title tag ≤ 60 characters (excluding brand name)
- [ ] Meta description ≤ 140 characters, sentence case
- [ ] H1 ≤ 80 characters
- [ ] CTA is above the fold and repeated near page end
- [ ] Correct HubSpot formId is used for the CTA type
- [ ] All visuals have alt text + captions
- [ ] No invented metrics, no unsupported product claims
- [ ] Only Bart-validated technical claims in the Technical Credibility section
- [ ] No prohibited phrases from `must_not_say` field
- [ ] Color combinations pass legibility (no midtone-on-midtone pairings)
- [ ] Fonts: Plantin for headlines, Lab Grotesque for body (or Google Fonts alternates)
- [ ] Page word count: 900–1,500 words
- [ ] Keyword density: 0.8%–1.5%
- [ ] Minimal nav (global nav removed on SEM landing pages)
