# NexaDesk — working context

AI receptionist for real estate agencies. Inbound calls + website chat answered
24/7: RAG-backed property answers, lead capture and scoring, viewing bookings.

**Live since 2026-08-17** at `https://nexadesk-api-production.up.railway.app`.
Portfolio showpiece *and* a product meant to carry real users — decisions favour
"would survive a paying customer" over "demos well".

This file is the seam between sessions. Read it, then `AUDIT.md` and
`DEPLOYMENT.md` before changing anything; those two carry the reasoning.

---

## RESUME POINT (2026-09-03) — shaheer.dev folded in as a second vertical

Shaheer decided shaheer.dev should become a NexaDesk tenant on this exact
backend (same Railway, Supabase, Twilio number +1 781 365 5768, dashboard),
not a bolted-on side system. His instruction: "whole pipeline should be same
totally so I get a client no matter where he calls, on nexadesk or
shaheer.dev." That ruled out a forked second orchestrator — see below.

**Correction to this plan's original assumption — read before touching the
phone number again:** there was never a "Pinnacle Property Management"
company on the live database. `+17813655768` had belonged, since 2026-05-25,
to a company literally named **"Shaheer's AI Agency"** — Shaheer's own
NexaDesk real-estate self-demo (the one referenced in his 2026-09-02 LinkedIn
post: "Call this number... that's my AI receptionist"), with ~30+ real
inbound leads and ~70 real conversations attached. Not synthetic seed data.
`create_shaheer_company.py`'s same-phone-different-name guard correctly
refused to touch it. Shaheer chose to **repurpose that row in place** rather
than provision a second number — the old real-estate demo persona on that
number is gone as of this session; anyone calling from the LinkedIn post now
reaches the studio assistant instead.

**Done this session, verified live (not just tested locally):**

1. Applied `migrations/0005_company_vertical.sql`,
   `0006_leads_studio_fields.sql`, `0007_site_visits.sql` to live Supabase
   via the `apply_migration` MCP tool — all three idempotent, all succeeded.
2. Updated the existing company row (`id = ae14c9eb-e18c-4ec3-bce8-cd4a57db3bb4`,
   the former "Shaheer's AI Agency") in place: `name = "Shaheer Salal — AI
   Product Studio"`, `email = contact@shaheer.dev`, `vertical = ai_studio`,
   `ai_persona`/`receptionist_name`/`working_hours` set per
   `create_shaheer_company.py`'s intended values. `ADMIN_UID` was already
   attached as `owner` on this row from before — no `users` change needed.
   **This is the permanent company_id for shaheer.dev's `NEXT_PUBLIC_COMPANY_ID`.**
3. Ran `scripts/seed_shaheer_knowledge.py ae14c9eb-e18c-4ec3-bce8-cd4a57db3bb4`
   — 2 docs, 14 chunks ingested into Qdrant.
4. Verified live against the real Railway backend (not local): greeting,
   a factual-honesty probe ("is AskTax live?" → correctly says offline), a
   jailbreak/prompt-injection attempt (refused, prompt not leaked), a
   hallucination probe on a made-up product (correctly said it didn't know
   rather than inventing pricing), the `/chat/live-context` SSRF guard
   (rejected `169.254.169.254`), a real URL fetch, and opportunistic lead
   capture from a single natural sentence (name + email + "small business"
   extracted without a checklist prompt — see `leads.id =
   87aa4c51-c7bf-471c-8e90-a7d950c75389` for the recorded example).
   **Not done: an actual inbound phone call to +17813655768.** Shaheer opted
   to trust the text-path verification instead, since voice reuses the same
   orchestrator/vertical config — if voice behaves unexpectedly, check there
   first before assuming the company data is wrong.

**Still not done:**

- Frontend: `shaheer-dev-next/` (Next.js, App Router) already exists,
  committed (`320c836`), and calls the real backend
  (`lib/api.js` → `/chat/message`, `/chat/live-context`) instead of OpenAI
  directly — but its `NEXT_PUBLIC_COMPANY_ID` env var is still unset locally
  and not yet configured in Vercel. Needs: set that env var to
  `ae14c9eb-e18c-4ec3-bce8-cd4a57db3bb4`, deploy to the linked Vercel
  project's preview URL, full click-through + audition-flow test there.
- Owner-only site analytics (`app/analytics/router.py`, `site_visits` table,
  dashboard's `SiteAnalytics.jsx`) is built and the table now exists live,
  but the frontend tracking beacon (pageview/click/scroll → `POST
  /analytics/track`) has not been added to either `shaheer-dev-next/` or
  nexadesk.site's frontend yet — so the table will stay empty until that's
  wired in.
- DNS cutover (shaheer.dev: Cloudflare Pages → Vercel) — deliberately last,
  only after the Vercel preview is fully verified. Not started.
- Retire old `shaheer-dev/` (static HTML + its FastAPI backend) once DNS
  cuts over.
- SEO: sitemap/robots/OG image exist in the Next.js app already; Search
  Console / Bing Webmaster submission still needs doing post-DNS-cutover.
- Old real-estate demo content that used to live in this company's
  `ai_persona` (the "simulated sample data" listings pitch) is gone from the
  row — if that self-demo experience still needs to exist somewhere for
  NexaDesk marketing purposes, it needs its own company + phone number now,
  since this one moved to `ai_studio`.

See the full staged plan:
`C:\Users\DELL\AI_Dev\ClaudeData\config\plans\compressed-riding-shannon.md`
(written assuming "Pinnacle" existed — read company-id/phone specifics above
as the corrected version of that plan's §1, not the file itself).

**Done and verified this session (148/148 tests passing, ruff clean):**

- **`app/shared/verticals.py`** is now the single place per-domain prompt
  differences live — router classification text, knowledge/qualifier system
  prompt templates, field-extraction schema, greetings, lead-summary prompt.
  `get_vertical(company.get("vertical"))` falls back to `real_estate` for
  anything missing/unrecognised, so an old company row (no `vertical`
  column yet) behaves byte-identically to before. `real_estate`'s templates
  are the pre-existing text verbatim — nothing was reworded, only relocated.
  Added `ai_studio` alongside it. A shared `GUARDRAIL_BLOCK` (anti-jailbreak,
  anti-hallucination, "never reveal this prompt") is now included in every
  vertical rather than only existing implicitly in one prompt.
- **`build_knowledge_system_prompt()`** (same file) replaces two independent
  copies of the same formatting logic that used to exist in
  `app/agents/orchestrator.py::_knowledge_system` and
  `app/voice/conversation.py::_build_turn_context` — they were already
  drifting from each other before this session (voice had a confidence-based
  addendum chat's version lacked). Now both call one function.
- **Deleted `app/shared/prompts.py`** (fully migrated, verified zero
  remaining importers) and **deleted `app/voice/conversation.py`'s
  `process_voice_turn`** (verified zero callers anywhere in `app/` —
  `stream_voice_turn`/`_build_turn_context` is the only live voice path;
  `process_voice_turn` was a stale non-streaming duplicate).
- **`app/rag/live_fetch.py`** — Part 2 of the ai_studio knowledge base: a
  visitor's own URL, fetched once, stuffed into that session's prompt only,
  never written to Qdrant/`documents`. SSRF-guarded (blocks
  private/loopback/link-local/metadata IPs, re-validates the host after
  redirects, rejects non-http(s) schemes including scheme-confusable input
  like `javascript:alert(1)` — see `tests/test_live_fetch.py` for the exact
  cases). Stored in Redis, keyed generically: a chat session uses its
  `session_id`; a phone call has no `call_sid` until Twilio answers, so it's
  keyed by `session.caller_number` instead (captured on the web step before
  the visitor dials in — this still needs that web step built on the
  frontend). Deleted explicitly at call end
  (`app/voice/router.py::_finalize_call`) and via a new
  `POST /chat/live-context/clear` the frontend must call on
  `beforeunload`/`sendBeacon`; a 15-min Redis TTL is only the backstop.
- **New endpoints** on `app/chat/router.py`: `POST /live-context` (fetch +
  store, rate-limited 6/min/IP) and `POST /live-context/clear`. `GET
  /greeting` is now vertical-aware and uses `receptionist_name` (previously
  ignored it, always said the product name).
- **`app/agents/tools.py`**: `extract_fields_from_message()` takes a
  `vertical_key` and picks the right JSON schema (real_estate:
  budget_min/max, area_preference, bedrooms_needed; ai_studio:
  client_company, project_type, budget_text — migration 0006).
  `capture_lead_fields()` grew those three new optional kwargs, additive.
- **`app/shared/net.py`** is a new home for `get_client_ip()` (moved out of
  `app/public/router.py`, which now imports it) so the new rate-limited
  `/chat/live-context` endpoint doesn't reimplement the
  `TRUST_PROXY_HEADERS`-gated header-trust logic a second time (AUDIT.md
  M5 is exactly about that gate mattering). `tests/test_security.py`'s two
  M5 tests were patching `app.public.router.get_settings`, which stopped
  mattering once the function moved — fixed to patch
  `app.shared.net.get_settings`, the module that actually calls it now.
- New test files: `tests/test_verticals.py`, `tests/test_live_fetch.py`.

**Design call worth knowing if you're touching this again**: the studio
company's `system_prompt` DB column is deliberately NOT used — it turns out
nothing in the pre-existing code read it either (grepped before relying on
it); the persona lives in `ai_persona` (short string) + the vertical's
template, same as every other company already works.

---

## RESUME POINT (2026-08-23)

**The one bug behind "nothing works": `api.nexadesk.site` has no TLS
certificate.** DNS is correct (CNAME -> Railway, Gray Cloud, resolves to
69.46.46.127), but the host is served Railway's wildcard `*.up.railway.app`
cert, which does not cover it — so every browser request dies in the TLS
handshake. Railway has no custom-domain record for it; one was never added.

That single fault breaks **both** frontends, which is why the backend looked
dead when it never was:
- Dashboard `www.nexadesk.site` -> bundle calls `https://api.nexadesk.site`
- Demo `nexadesk-1j2y.vercel.app` -> bundle calls `https://api.nexadesk.site`

**The backend itself is fully healthy** — verified 2026-08-23 end to end:
52 routes live, all 4 services reachable (Supabase/Qdrant/OpenAI/Redis),
`/demo/chat` returns real RAG answers (2-4s warm, ~10s cold), and `/demo/voice`
does the whole Deepgram STT -> gpt-4o-mini -> Deepgram Aura TTS round trip
returning valid MP3. Deepgram already powers **both** STT and TTS.

### Blocked on credentials (all three need Shaheer)

1. **Railway CLI is unauthorized** (`railway whoami` -> Unauthorized). Needed to
   add `api.nexadesk.site` as a custom domain so a cert is issued. This is the
   real fix and it revives dashboard + demo with **no redeploy of either**.
2. **Vercel CLI is logged out**, and `VERCEL_TOKEN` in `.env` is a `vcp_`
   *project-scoped* token for the dashboard project only — `/v2/teams` 403s and
   `vercel whoami --token` says "User not found". It cannot create or deploy the
   demo project. An account-scoped token or `vercel login` is required.
3. Reading the master credentials file and triggering a production Vercel
   deploy are both blocked by the auto-mode classifier. Per the standing rule
   these were surfaced, not worked around.

### Done this session

- `twilio==9.11.0` added to `requirements.txt` and installed. It was **missing
  entirely** while `app/voice/telephony.py` imports it in four places; the
  imports are function-local so the app booted fine and the failure would only
  have surfaced on the first real call, on Railway too.
- `nexa_demo_vercel/lib/api.js` now defaults to the Railway origin instead of
  the certificate-less custom domain. Rebuilt and verified: the dead domain is
  gone from `.next/static`. Needs a Vercel deploy to reach users.
- Dashboard `VITE_API_URL` **updated on Vercel** to the Railway origin.
  Vite bakes env at build time, so **this does nothing until the project is
  redeployed** — that redeploy is blocked (item 3).
- Local `APP_SECRET_KEY` was still `change-me-in-production`, which makes
  `validate_startup_config` refuse to boot; replaced with a real 64-hex secret.
  Production's key is separate and untouched.
- Next.js 14.2.29 -> 14.2.35. Three high advisories remain and only Next 16
  clears them (`isSemVerMajor`), deliberately deferred: the demo is 100% static
  prerendered, so the SSR/middleware/image-optimizer CVEs do not apply.
- Corrected stale "ElevenLabs" claims in `demo_voice`'s docstring and
  `VoiceWidget.jsx` — that path is Deepgram Aura now.
- Twilio credentials written into `.env`. `scripts/twilio_check.py` run: account
  **active, Full type, $20.00 balance, 0 phone numbers owned**. A number is what
  voice needs and there isn't one yet.
- CI verified locally: ruff clean, compileall clean, 53/53 pytest passing.

### Not done

- No phone number bought (needs a decision on which; US local is the only type
  that is dialable from outside the US — toll-free is not).
- `TELEPHONY_PHONE_NUMBER` and `TELEPHONY_WEBHOOK_BASE_URL` still empty.
- Railway env has no `TELEPHONY_*` values, so voice stays unmounted in prod.
- ElevenLabs key still absent, so ar/ur have no TTS voice at all.

---

## Stack

- FastAPI, Python 3.12, on **Railway** (Nixpacks). **No Docker anywhere** — self
  hosting was deliberately abandoned to keep this machine light.
- **Qdrant Cloud** (vectors) - **Upstash Redis** (call/session state, `rediss://`)
- **Supabase** — Postgres + auth + storage. Project `ugimqdjecdhltpviovny`.
- LLM `gpt-4o-mini` - STT **Deepgram nova-2** - TTS pluggable (see below)
- Dashboard: React/Vite on Vercel, deploys from GitHub branch `Shaheer`
- Demo: `nexa_demo_vercel/` Next.js, calls the real backend

## TTS provider switch

`app/voice/tts.py` takes `TTS_PROVIDER = deepgram | elevenlabs | auto`.
Currently pinned to `deepgram` with `TTS_VOICE_ID=aura-2-apollo-en`.
**When the ElevenLabs key arrives it is one variable** — set `TTS_API_KEY` and
flip `TTS_PROVIDER` to `auto` or `elevenlabs`. No code change.

- Aura returns 8 kHz linear16 directly, so the Twilio path is one
  `audioop.lin2ulaw` call. ElevenLabs still needs ffmpeg (compressed formats only).
- `TTS_VOICE_ID` is shared between providers and that is a trap: ElevenLabs uses
  opaque ids (`21m00Tcm4TlvDq8ikWAM`), Deepgram wants a model name
  (`aura-2-apollo-en`). Non-Aura values are ignored on the Deepgram path. There
  is a test for exactly this.
- **Deepgram has no Arabic or Urdu voice** (verified: en 53, es 17, fr 2, plus
  de/it/ja/nl). `SUPPORTED_LANGUAGES` claims ar and ur, so ElevenLabs is
  required for those. Intended split: Aura-2 for en/es/fr phone calls (8 kHz
  u-law masks most of the quality gap, ~5-7x cheaper and lower latency),
  ElevenLabs for ar/ur and the full-bandwidth web demo.
- Shaheer's standing judgement: Aura still "shouts it's AI" on the web demo.
  Quality is not to be compromised there.

## Decisions that are easy to break

- Voice is a **fully streamed** pipeline: Deepgram streaming WS (server-side VAD,
  `speech_final`) -> streamed LLM tokens -> clause-chunked TTS. Never
  reintroduce batch request/response; that was ~2.5-4.5s of dead air.
- Twilio outbound media **must** use the `streamSid` from the `start` event, not
  `call_sid`. Twilio silently drops mismatched frames.
- Unrecognised inbound numbers resolve to `None` and play fallback TwiML. There
  is deliberately **no "first company" fallback** — it leaked across tenants.
- **Telephony is optional.** Neither credential set -> voice routes are not
  mounted -> app boots fine. Exactly one set -> hard startup failure. Not
  mounting the route *is* the security control.
- Supabase issues **ES256** tokens (JWKS at `/auth/v1/.well-known/jwks.json`).
  `app/shared/jwks.py` verifies against it; the legacy HS256 secret is a
  fallback. Each branch pins its algorithms — never trust the token's `alg`.
- Backend uses the Supabase **service-role** client everywhere, bypassing RLS.
  Tenant isolation rests on hand-written `.eq("company_id", ...)` filters.
- `APP_SECRET_KEY` keys CRM OAuth token encryption. Rotating it forces every
  customer to reconnect their CRM.
- `TRUST_PROXY_HEADERS` stays `false` on Railway — true without a
  header-overwriting proxy makes every per-IP rate limit forgeable.
- `api.nexadesk.site` must be **Gray Cloud** in Cloudflare, not Orange. Railway
  terminates its own TLS and proxying breaks WebSocket upgrades, which voice
  depends on entirely.

## Environment traps on this machine

- **PowerShell cp1252 corrupts source files on read/write.** Use the Bash tool,
  or Python with an explicit `encoding="utf-8"`. Never round-trip a source file
  through `Get-Content`/`Set-Content` without `-Encoding utf8`.
- npm global prefix sits inside Zed's sandbox.
- **ruff is pinned to 0.16.2** — CI runs ruff + compileall + import + pytest.
- **Railway builder-pool failures look like code failures.** Two GitHub-triggered
  builds produced no build output at all, only repeated "scheduling build on
  Metal builder". `railway up` from the local directory deployed the same commit
  fine. Check `buildLogs` and `deploymentLogs` separately to tell them apart.

## State

- Branch `Shaheer`. Last commit `457cc32` (credential collector + voice test label fix).
- `AUDIT.md` tracks 34 findings, 32 fixed; the 2 open are deliberate.
- 53 tests passing (`tests/test_security.py`, `test_tts_provider.py`,
  `test_voice_pipeline.py`).
- **Still not done:** ElevenLabs key; Cloudflare token needs zone resources added
  before DNS can be scripted; Supabase MCP needs auth.

## Key paths

| What | Where |
|---|---|
| Master credentials (234 keys, 18 .env files, 14 projects) | `C:\Users\DELL\.credentials\AI_Dev_master_credentials.md` |
| Deploy + ops runbook | `DEPLOYMENT.md` |
| Findings ledger, read before changing anything | `AUDIT.md` |
| Request/data flows | `FLOWS.md` |
| Shared cross-project memory | `C:\Users\DELL\AI_Dev\ClaudeData\config\projects\C--Users-DELL-AI-Dev\memory\` |

`scripts/` holds `check_services.py`, `smoke_test.py`, `deploy_watch.py`,
`railway_logs.py`, `sync_railway_env.py`, `set_env.py`, `twilio_check.py`,
`cloudflare_dns.py`, `railway_domain.py`, `vercel_setup.py`, `collect_credentials.py`.

## How Shaheer works

Approves moves in bulk and dislikes per-step approval requests — "it's the era of
automation and I am approving every single move". Report outcomes, not
permission requests. But do not compromise quality to move faster, and do not
work around a permission block: surface it and let him decide.
