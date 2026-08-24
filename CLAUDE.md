# NexaDesk — working context

AI receptionist for real estate agencies. Inbound calls + website chat answered
24/7: RAG-backed property answers, lead capture and scoring, viewing bookings.

**Live since 2026-08-17** at `https://nexadesk-api-production.up.railway.app`.
Portfolio showpiece *and* a product meant to carry real users — decisions favour
"would survive a paying customer" over "demos well".

This file is the seam between sessions. Read it, then `AUDIT.md` and
`DEPLOYMENT.md` before changing anything; those two carry the reasoning.

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
