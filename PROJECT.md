# LP Agent — Project Reference

_Last updated: 2026-07-18_

Automated SEM workflow for DataHub. Three interlocking pipelines that go from **detecting** what to target → **validating** the fit → **producing** the assets.

```
Signal Radar      ──▶  Detects rising organic queries, flags coverage gaps
Bart Validate     ──▶  Authoritative fit-check for keywords / LP copy / hosted pages
Technical LP      ──▶  Generates long-form technical landing pages as Google Docs
```

All three are Slack-native and share a common backend (FastAPI on Render) fronted by a Cloudflare Worker (`slack-intake`) that handles Slack's 3s ack deadline and hosts a public intake form.

---

## Workflows

### 1. Signal Radar — weekly rising-query triage

**Trigger:** Cloudflare cron, `0 15 * * 1` (Monday 15:00 UTC = 8am PDT / 7am PST).
Also runnable on demand via `POST /api/signal-radar/run` (see Operations).

**Flow:**
1. Pull Google Search Console query performance for `sc-domain:datahub.com`, last 7 days vs. prior 7 days.
2. Filter to rising queries (positive delta, ≥ min impressions).
3. Load the Google Ads keyword export sheet and build a `keyword → ad group` map.
4. Send the top-N rising queries to Claude for triage against DataHub's shipped capabilities (✅ Confirmed / ⚠️ Conditional / ❌ Exclude).
5. Cross-reference each with Ads coverage (exact / fuzzy contains / fuzzy within match).
6. Post ONE digest to `#sem-radar` with three sections:
   - 🚨 **Gap opportunities** — Strategic + no coverage (highest-value)
   - 📈 **Already targeted, rising fast** — Strategic + coverage
   - ⚠️ **Also worth watching** — Watch tier

**Where the code lives:** `pipelines/signal_radar/` + `POST /api/signal-radar/run` in `main.py`.

**Not authoritative** — Signal Radar's classifier is Claude reading a summarized capability list. For real fit-checks, use `/bart-validate`.

---

### 2. Bart Validate — authoritative fit-check

Bart Bot has direct access to the DataHub codebase, so it can give ground-truth answers about what's shipped vs. hypothetical.

**Two entry points:**
| Entry point | For whom |
|---|---|
| Slack: `/bart-validate` | Internal team; anyone in a channel where the bot lives |
| Web form: `https://slack-intake.<WORKER_SUBDOMAIN>.workers.dev/form/bart-validate` | Agency / external partners; password-gated |

**Three input types:**
- `keywords` — Google Sheet with a keyword list
- `lp_content` — Google Doc with LP draft copy
- `html_url` — any public HTML URL (fetched over HTTP, tags stripped)

**Flow (Phase 1):** Fetch source → post validation prompt to `#sem-lp-requests` mentioning `@Bart` → register JOB awaiting `BART_DONE`.

**Flow (Phase 2, triggered by Bart's reply):** Extract Bart's markdown summary table → post digest to `#sem-lp-build-kits` (main message + threaded prose if it exceeds Slack's 40k char limit).

**Where the code lives:** `pipelines/bart_validate/` + `POST /api/bart-validate` in `main.py`.

---

### 3. Technical LP — long-form Google Doc generation

**Trigger:** `/technical-lp` slash command opens a Slack modal with campaign brief fields.

**Flow (Phase 1):** Modal submit → post grounding request to Bart in `#sem-lp-requests` → register JOB.

**Flow (Phase 2, triggered by Bart's `BART_DONE`):** Parse Bart's TOPIC_FIT verdict. If `NOT_A_FIT` → abort with the reasoning. Otherwise → Claude outline → full copy → QA pass → create Google Doc in the Shared Drive → post URL to `#sem-lp-build-kits`.

**Where the code lives:** `pipelines/technical_lp/` + related handlers in `main.py`.

---

## Architecture

```
                    ┌────────────────────────────────────────┐
                    │   Cloudflare Worker: slack-intake      │
                    │   slack-intake.<WORKER_SUBDOMAIN>.workers.dev │
                    │                                        │
Slack ─POST────────▶│   • Verifies Slack signature           │
                    │   • Returns 200 in <50ms               │
                    │   • Forwards to Render (waitUntil)     │
Cron (Mon 15:00Z)──▶│   • Cron: fires /api/signal-radar/run  │
                    │   • Serves /form/bart-validate         │
                    └───────────────────┬────────────────────┘
                                        │
                                        ▼
                    ┌────────────────────────────────────────┐
                    │   Render: lp-agent-service (FastAPI)   │
                    │   <RENDER_SERVICE>.onrender.com      │
                    │                                        │
                    │   /slack/commands       ─┐             │
                    │   /slack/interactivity  │             │
                    │   /slack/events         ─┤ pipelines/ │
                    │   /api/bart-validate    │             │
                    │   /api/signal-radar/run ─┘             │
                    └───────────────────┬────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
             Google APIs         Anthropic API        Slack Web API
      (Docs, Sheets, Drive,   (Claude Sonnet 4.6)   (chat.postMessage,
       Search Console)                                views.open, etc.)
```

**Slack channels the workflows read/write:**
| Channel | Role |
|---|---|
| `#sem-lp-requests` (<SEM_LP_REQUESTS_CHANNEL_ID>, private) | Bart's home — all `/technical-lp` and `/bart-validate` prompts land here as threaded requests |
| `#sem-lp-build-kits` | `/technical-lp` and `/bart-validate` completion messages |
| `#sem-radar` (<SEM_RADAR_CHANNEL_ID>) | Signal Radar weekly digest |

**Google Cloud project:** `<GCP_PROJECT_ID>`. Two service accounts:
- `blog-agent@...` — writes Google Docs (used by `/technical-lp`)
- `bart-validate@...` — reads Sheets/Docs (used by `/bart-validate` and Signal Radar), plus GSC via `webmasters.readonly` scope

**Shared Drive folder for generated Docs:** `<SHARED_DRIVE_FOLDER_ID>`.

---

## Operations

### Environment variables (Render)

| Var | Purpose |
|---|---|
| `SLACK_BOT_TOKEN` | Slack API auth |
| `SLACK_SIGNING_SECRET` | Verify inbound Slack requests |
| `ANTHROPIC_API_KEY` | Claude for `/technical-lp` + Signal Radar classifier |
| `BART_USER_ID` | `<BART_USER_ID>` — Bart's Slack user ID |
| `SEM_LP_REQUESTS_CHANNEL` | `<SEM_LP_REQUESTS_CHANNEL_ID>` — Bart's channel |
| `SEM_LP_BUILD_KITS_CHANNEL` | Completion channel for LP + validate |
| `SIGNAL_RADAR_CHANNEL` | `<SEM_RADAR_CHANNEL_ID>` — Signal Radar digest destination (falls back to `SIGNAL_RADAR_AGENCY_CHANNEL`, then to build-kits) |
| `SIGNAL_RADAR_ADS_SHEET_URL` | Google Ads keyword export sheet |
| `GSC_PROPERTY` | Defaults `sc-domain:datahub.com` |
| `BART_VALIDATE_API_TOKEN` | Shared secret between Worker and Render (auth on `/api/*` endpoints) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` OR `/etc/secrets/google-service-account.json` | `blog-agent@` credentials for Doc creation |
| `BART_VALIDATE_SERVICE_ACCOUNT_JSON` OR `/etc/secrets/bart-validate-sa.json` | `bart-validate@` credentials for reads |

### Environment variables (Cloudflare Worker)

| Var | Purpose |
|---|---|
| `LP_AGENT_FORWARD_BASE` | `https://<RENDER_SERVICE>.onrender.com` |
| `LP_AGENT_SIGNING_SECRET` | Slack app signing secret (mirrors Render's) |
| `BART_VALIDATE_API_TOKEN` | Must match Render's value |
| `BART_VALIDATE_FORM_PASSWORD` | Password gate on `/submit/bart-validate` |

### Deploy

**Render (FastAPI service)** — auto-deploys on push to `main`:
```
cd ~/lp-agent/lp-agent-service
git push origin main
```

**Cloudflare Worker** — manual deploy:
```
cd ~/slack-intake-worker
CLOUDFLARE_ACCOUNT_ID=<CLOUDFLARE_ACCOUNT_ID> wrangler deploy
```

### Manual triggers

**Force a Signal Radar run** (bypass cron):
```
curl -X POST 'https://<RENDER_SERVICE>.onrender.com/api/signal-radar/run' \
  -H 'X-Api-Token: <BART_VALIDATE_API_TOKEN>'
```

**Tail Worker logs** (Slack request flow):
```
cd ~/slack-intake-worker
CLOUDFLARE_ACCOUNT_ID=<CLOUDFLARE_ACCOUNT_ID> wrangler tail --format pretty
```

**Render logs** — Render dashboard → `lp-agent-service` → **Logs** tab.

---

## Common issues

| Symptom | Likely cause | Fix |
|---|---|---|
| `/technical-lp` or `/bart-validate` modal doesn't open | Render cold start → `trigger_id` expired before Render called `views.open` | Retry — the second attempt usually hits a warm instance |
| `/bart-validate` completes Phase 1 but Phase 2 never fires | Bart forgot to append `BART_DONE` on its own line (known Bart quirk) | Nudge Bart in the thread: `@Bart please reply BART_DONE to close this out` |
| Signal Radar shows all "✗ no coverage" | Env var race — Render module loaded `SIGNAL_RADAR_ADS_SHEET_URL` before it was set | Trigger another run after Render's redeploy finishes |
| `/bart-validate` errors on Sheet URL: "The document must not be an Office file" | User submitted an XLSX uploaded to Drive, not a native Sheet | In Drive → File → Save as Google Sheets; submit the new URL |
| Web form returns "Validation service rejected the submission" | Render missing `BART_VALIDATE_API_TOKEN`, or value doesn't match Worker's | Set on Render; confirm the value matches Worker secret |
| GSC fetch fails with permission error | `bart-validate@...` not granted Restricted role on the GSC property | Search Console → Settings → Users → Add with Restricted permission |
| Render deploy fails | Almost always import / syntax error on a recent commit | Check Render deploy logs → fix and push again |
| SSH push to GitHub prompts for password | Remote URL still using old PAT | `git remote set-url origin git@github.com:<github-org>/lp-agent-service.git` (or check `~/.ssh/id_ed25519` is added to GitHub) |

---

## File map

```
~/lp-agent/
├── lp-agent-service/           ← Render-deployed FastAPI service
│   ├── main.py                 ← All routes, Slack handlers, orchestration
│   ├── PROJECT.md              ← this file
│   ├── README.md
│   ├── requirements.txt
│   ├── render.yaml             ← Render service config
│   ├── pipelines/
│   │   ├── technical_lp/       ← /technical-lp: brief → grounding → Google Doc
│   │   ├── bart_validate/      ← /bart-validate: source → Bart → digest in Slack
│   │   └── signal_radar/       ← Weekly GSC → Claude triage → Ads coverage → digest
│   └── docs/                   ← Editorial style, SEO, structure guides
├── .claude/commands/           ← Claude Code slash commands (local variants of the workflows)
│   ├── technical-lp.md
│   └── bart-validate.md
├── generated-pages/            ← Local HTML LP output from /technical-lp CLI runs
├── templates/                  ← Sample HTML LP structure
└── CLAUDE.md                   ← Full instructions for Claude when working in this repo

~/slack-intake-worker/   ← Cloudflare Worker (Slack ack + web form + cron)
├── src/worker.js               ← 300-ish lines, single-file
└── wrangler.toml               ← Cron triggers + non-secret vars
```

---

## Not built yet / possible next moves

- **Google Ads API integration** — replace the manual keyword-export sheet with live data.
- **Gong transcript signal** — feed customer-language shifts into Signal Radar's triage pool.
- **Notion product-launch anticipation** — inject upcoming feature terms so Signal Radar can pre-position for them.
- **Auto-refresh of the Ads coverage sheet** — the export currently stales; a scheduled Ads → Sheets sync would fix.
- **Bart auto-nudge** — if a JOB waits > N minutes without `BART_DONE`, auto-post a reminder in the thread.
- **DST-safe cron scheduling** — current cron drifts an hour twice a year. Cloudflare doesn't support zoned schedules; alternatives are Render Cron Jobs (paid, timezone-aware) or a small scheduler layer.
