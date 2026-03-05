# DataHub SEM Landing Page Structure Template
*(Conversion-First, Keyword-Exact, Agent-Friendly)*

---

## 0. Metadata (Agent Required)

**Primary Search Term (Exact Match)**
Must appear verbatim in:
- Title tag
- H1
- First 100 words
- At least one H2
- Meta description

**Intent Type:** Transactional | Commercial | Informational

**Primary CTA Type:** Demo | Bi-weekly Demo | Product Tour | Free Trial

### HubSpot Form Mapping

Embed all forms with this script. Use the table below for the correct `formId`. The primary CTA button must anchor-link to the form. The full form embeds again at the end of the page before the footer.

```html
<script charset="utf-8" type="text/javascript" src="//js.hsforms.net/forms/embed/v2.js"></script>
<script>
  hbspt.forms.create({
    portalId: "14552909",
    formId: "",
    region: "na1"
  });
</script>
```

| CTA Type | HubSpot formId |
|---|---|
| Demo | `ed2447d6-e6f9-4771-8f77-825b114a9421` |
| Free Trial | `42182785-f711-40b4-92e7-11468579321b` |
| Bi-weekly Demo | `2bf16106-3e8e-4dc3-9ae4-5b0bce901d88` |
| Product Tour | `aa56e90c-044a-46d8-a92f-cb905ad662f8` |

**CTA Button Labels by Type**
| CTA Type | Button Label |
|---|---|
| Demo | "Request a Demo" |
| Free Trial | "Start Free Trial" |
| Product Tour | "See It in Action" |
| Bi-weekly Demo | "Join a Live Demo" |

---

## SEO + PPC Alignment Layer

| Element | Rule |
|---|---|
| Title tag | ≤60 characters. Format: `[Primary Search Term + Benefit] \| DataHub` |
| Meta description | 150–160 characters. Include search term naturally + outcome. Sentence case. |
| URL slug | `/primary-search-term-variant/` |

---

## Page Sections (Strict Order)

---

### 1. HERO — *Emotional trigger: Recognition*

**H1 (required):** Must include the primary search term verbatim. ≤80 characters.

**Subheadline:** 1–2 lines clarifying who it's for, what it solves, why it's better.

**Supporting bullets:** 3 max. Outcome-driven. Quantifiable where possible. No fluff.

**Primary CTA:** High contrast. Anchor-links to the embedded form below.

**Embedded HubSpot form:** Use `formId` from the CTA mapping table above.

**Trust strip (directly below hero):**
- 3–6 enterprise logos
- Optional security badges
- Credibility line: *"Trusted by enterprise data teams in financial services, healthcare, and technology."*

#### 🎯 Emotional Engagement Rules — Hero

The first emotional job is to make the reader feel *seen*. Apply **specificity as empathy**: generic problem statements read as marketing; specific ones read as understanding.

- Open with the reader's problem — not with DataHub
- Name the role, the moment, and the failure mode — not just the category of problem
- Use second person ("you", "your team") in the subheadline and bullets
- The reader should feel this section was written *about* them, not *at* them

**✅ Do this:** *"Your pipelines pass. Your dashboards break anyway. You find out in the standup."*
**❌ Not this:** *"Data quality is a challenge for modern data teams."*

**Scroll momentum:** End the hero with a subhead or bullet that implies a question the next section will answer.

---

### 2. PROBLEM SECTION — *Emotional trigger: Relief through recognition*

**H2:** "The Real Challenge Behind [Primary Search Term]"

Address: pain, friction, risk, cost of inaction. Use short paragraphs and bullet points. Emotional + operational framing.

#### 🎯 Emotional Engagement Rules — Problem Section

Validate frustration without amplifying anxiety. Name the **invisible cost** for each audience type:

- **Platform Engineers:** Name the cognitive load. The context switching. The hours spent explaining why a pipeline failed upstream. The feeling of being blamed for something they didn't control.
- **Economic Buyers:** Name the decision risk. The audit question they can't answer. The data incident that surfaced in a board meeting. The cost of not knowing what "trusted" means across the stack.

Write for whichever `primary_audience` is set in the request — but keep both in mind.

**One paragraph max** on cost of inaction. Do not dwell. Move to solution.

**Scroll momentum:** End with a statement that creates forward pull — the reader should feel *"Yes, that's exactly it — and I want to know if there's a better way."* Not dread.

---

### 3. SOLUTION SECTION — *Emotional trigger: Confidence*

**H2:** "A Better Way to [Primary Outcome]"

Explain: how the product solves the problem, why it's different from legacy tools, why it's different from competitors.

**Structure:** 3–5 benefit blocks. Each block: H3 + 2–3 sentence explanation + optional bullet list. Focus on benefits, not feature dumps.

#### 🎯 Emotional Engagement Rules — Solution Section

Apply **competence transfer**: the reader needs to be able to explain the value to someone else — their manager, their team, their procurement committee. Write benefit blocks so they function as internal talking points.

- Each H3 headline should be a claim the reader could repeat in a meeting
- The 2–3 sentence explanation gives them the *why behind the what*
- Write as if the reader will screenshot this section and send it to someone
- Use concrete before abstract: say what happens first, then why it matters
- If a benefit requires more than one sentence to explain what it even is, rewrite the H3

**Scroll momentum:** End with an implied curiosity bridge toward "How It Works."

---

### 4. HOW IT WORKS — *Emotional trigger: Momentum*

**H2:** "How It Works"

Simple 3-step structure: **Connect → Contextualize → Activate**

Each step: one-sentence headline + 2–3 lines of explanation + optional micro-diagram or visual.

#### 🎯 Emotional Engagement Rules — How It Works

Reduce the perceived switching cost. The reader is asking: *"Is this actually possible for us?"* Apply **normalizing the path**: show that the steps are linear and achievable. Assume the reader is competent and their environment is complex — not that DataHub is magic.

- **Never use minimizing language:** "just", "simply", "easily" — it reads as dismissive to engineers
- Each step should answer an implicit objection: *"What if our stack is different?"* or *"What do we actually get at the end of this?"*
- Tone: *"Here is what happens. It works with what you have."*

**✅ Do this:** *"Connect your existing sources — Snowflake, dbt, Looker — without rebuilding pipelines."*
**❌ Not this:** *"Get up and running in minutes with our easy setup wizard."*

**Scroll momentum:** End with an implied validation — people like them have already done this.

---

### 5. TECHNICAL CREDIBILITY — *(Bart-validated facts only)*

**H2:** "Built for Enterprise-Grade [Security / Governance / Scale]"

Use Bart bot output to support: deployment options, security posture, compliance alignment, scalability claims.

**NO invented claims. NO vague "AI-powered" fluff.**

---

### 6. VISUAL SECTION

**H2:** "See It in Action"

Include: screenshot / product UI, architecture diagram, before/after state, or short demo video embed.

Every visual must include:
- Alt text with primary keyword naturally incorporated
- Caption explaining what the viewer is seeing

---

### 7. SOCIAL PROOF — *Emotional trigger: Belonging*

**H2:** "Trusted by Modern Data Teams"

Options: testimonial block (with title/company), short case stat, industry logos, quote with attribution.

#### 🎯 Emotional Engagement Rules — Social Proof

Apply **peer specificity**: give the reader permission to move forward by showing people like them already did.

- Prioritize testimonials that name a specific problem solved — not general satisfaction
- Company logos only work when they are companies the reader recognizes and respects
- Pair stats with a human quote: stats create credibility, quotes create connection
- Ideal combination: recognizable logo + quote that names the problem + specific outcome

**Scroll momentum:** End with a statement of implied readiness — *"you've seen the evidence — here's what's next."*

---

### 8. FAQ SECTION — *Emotional trigger: Trust*

**H2:** "Frequently Asked Questions About [Primary Search Term]"

Include 3–6 questions covering: implementation complexity, security concerns, integration, ROI, timeline.

Each answer: 3–5 sentences max. Clear. Not bloated.

#### 🎯 Emotional Engagement Rules — FAQ

Apply **objection respect**: write answers as if the question was asked by someone smart with a legitimate concern — not as a sales deflection. The reader is doing due diligence.

- Answer the actual question directly in the first sentence
- Acknowledge complexity where it exists — don't paper over it
- If an answer is "it depends," say so and explain what it depends on
- Never use FAQ answers to pitch additional features
- Do not end answers with a CTA — FAQs build trust, not conversions
- Questions must come from real implementation concerns, not softballs

---

### 9. FINAL CTA SECTION — *Emotional trigger: Confidence + Low Risk*

**H2:** "Ready to [Primary Outcome]?"

Restate: core benefit, risk reduction. Repeat primary CTA. Embed form again. Reinforce credibility.

#### 🎯 Emotional Engagement Rules — Final CTA

Apply **friction reduction through clarity**: the reader's hesitation is almost never "I don't want this." It's "I'm not sure what happens next." Resolve that.

- Name what happens after the click: *"You'll speak with a DataHub engineer — not a sales script — about your specific environment."*
- **For Product Tour CTAs:** emphasize self-directed, no-pressure exploration
- **For Demo CTAs:** emphasize that it's scoped to their environment, not a generic walkthrough
- Restate the core outcome (not the feature) in one sentence before the CTA button
- **Remove any language implying urgency, scarcity, or pressure** — this audience will distrust it

---

### 10. FOOTER

---

## Performance Optimization Rules (Agent Constraints)

- Search term density: 0.8%–1.5%
- No keyword stuffing
- CTA above the fold
- Minimal nav — remove global nav on SEM pages
- Page length: 900–1,500 words
- Mobile-friendly layout
- Load optimized — no unnecessary scripts

---

## Scroll Momentum Architecture (Full Page)

Every section must end with a **micro-forward-pull** — a question implied, a tension slightly unresolved, a promise partially made.

| Section | Implied Pull |
|---|---|
| Hero | "So what do you do instead?" |
| Problem | "There's a better way" |
| Solution | "See how it actually works" |
| How It Works | "Teams like yours have already done this" |
| Social Proof | "You've seen the evidence — here's what's next" |
| FAQ | "You know what you're getting into" |

### Progressive Risk Reduction Arc

Each section further down the page neutralizes a different reader fear:

| Section | Risk Being Neutralized |
|---|---|
| Hero | Relevance — *"Is this even for me?"* |
| Problem | Credibility — *"Do they understand my world?"* |
| Solution | Capability — *"Can it actually do what I need?"* |
| How It Works | Complexity — *"Can we realistically implement this?"* |
| Social Proof | Social — *"Have others like me done this successfully?"* |
| FAQ | Trust — *"What am I not seeing?"* |
| Final CTA | Commitment — *"What am I actually agreeing to?"* |

### Emotional Register by Scroll Depth

- **Top of page:** Confident and direct — reader is scanning, not committed
- **Middle of page:** Specific and substantive — reader is evaluating, give them content
- **Bottom of page:** Warm and clear — reader is ready to act, reduce friction

---

## Emotional Engagement — Hard Prohibitions

Even in service of engagement or conversion, the agent must never:

- Use countdown timers, urgency language, or scarcity signals ("limited spots", "act now", "only X left")
- Use vague or unattributed social proof ("a leading enterprise company")
- Use minimizing words that patronize engineers: "just", "simply", "easy", "plug and play"
- Sustain fear across multiple sections — one honest acknowledgment of risk is the limit
- Write H2s that don't deliver on their implied promise
- Include invented metrics or outcomes not validated by Bart output
- Add CTAs inside FAQ answers
