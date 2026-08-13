# NexaDesk — Pre-Railway Audit

**Date:** 2026-08-13
**Baseline commit:** `7396326`
**Scope:** every layer, from config through deploy, ahead of the Railway migration.
**Method:** static read of every router, dependency and helper in `app/`, plus the
dashboard, SQL schema and CI. Runtime verification is limited — there is no test
suite and no local Docker, so findings are marked CONFIRMED (provable from the
code as written) or LIKELY (depends on runtime data/config).

Legend: `[ ]` open · `[x]` fixed · severity **C**ritical / **H**igh / **M**edium / **L**ow

---

## Summary

| Severity | Count | Fixed | Open |
|---|---|---|---|
| Critical | 3 | 3 | 0 |
| High | 9 | 9 | 0 |
| Medium | 15 | 15 | 0 |
| Low | 7 | 5 | 2 |
| **Total** | **34** | **32** | **2** |

**Open items and where they are handled:**
M15 is environment configuration, covered in DEPLOYMENT.md. L2 is the test
suite (step 8). L7 is a recorded architectural note, not scheduled work.

The three Critical findings are all in the path that a **real Twilio number**
activates. None of them can be reached today because no live number is
provisioned — which is exactly why they must be closed before step 8.

---

## CRITICAL

### [x] C1 — Unrecognised inbound number is routed to an arbitrary tenant
`app/voice/router.py:242-250`

`_resolve_company_id` looks up the company by the dialled number, and when no
row matches it falls back to `SELECT id FROM companies LIMIT 1` — an arbitrary
tenant.

**Failure scenario:** Two agencies are onboarded. A caller dials a number that
isn't yet in `companies.phone` (typo, number not saved, second number on the
account). The call is answered *as* whichever company sorts first, the AI reads
that company's RAG knowledge base aloud to a stranger, and the captured lead and
full transcript are written into that company's `leads` and `conversations`
tables. Cross-tenant disclosure in both directions.

**Fix:** return `None` and play the fallback TwiML when no company matches.
Delete the fallback branch entirely.

### [x] C2 — Admin token emailed in plaintext as a URL parameter
`app/public/router.py:171`

The "Activate Account" button embeds `token={settings.ADMINTOKEN}` in a link sent
through Resend on every demo request.

**Failure scenario:** The admin token grants access to `/admin/invite-quick`,
which issues account invites without a login. It is now sitting in plaintext in
an inbox, in Resend's delivery logs, and — once clicked — in server access logs,
proxy logs, and browser history. Anyone with read access to any of those can mint
NexaDesk accounts indefinitely; the token never rotates.

**Fix:** issue a single-use, short-TTL signed token bound to `request_id`, stored
in Redis. Never send the static admin secret.

### [x] C3 — Twilio webhook signature validation fails open
`app/voice/router.py:33-39`, `app/main.py:67-71`

`_validate_twilio` returns `True` when `TELEPHONY_AUTH_TOKEN` is blank. In
production `main.py` only *logs an error* and boots anyway.

**Failure scenario:** With the env var unset or accidentally cleared on Railway,
`POST /voice/inbound` and `POST /voice/status` accept unsigned requests from
anyone. An attacker forges call events to create leads, poison transcripts, and
drive LLM/TTS spend on your account. The app gives no outward sign anything is
wrong.

**Fix:** raise `RuntimeError` on startup when `APP_ENV == "production"` and the
token is blank — same treatment `APP_SECRET_KEY` already gets at `main.py:76`.

---

## HIGH

### [x] H1 — Two blocking network calls on every authenticated request
`app/dependencies.py:102-128`

`get_current_user` constructs a **new** synchronous Supabase client per request
(line 111) and calls `client.auth.get_user(token)` — a network round-trip — then
`get_company_id` (line 125) issues a second sync query. Both are sync calls
inside `async def`, so they block the event loop rather than yielding.

**Failure scenario:** Under concurrent load every in-flight request on a worker
stalls for the duration of each auth round-trip. Throughput collapses to roughly
one request per auth-latency window per worker, regardless of how much the rest
of the app is async. This is the primary obstacle to the "scalable" goal.

**Fix:** verify the Supabase JWT locally with `python-jose` (already a
dependency) against the project JWT secret — zero network calls — and cache
`company_id` in Redis keyed by user id.

### [x] H2 — Outbound call audio uses the wrong stream identifier
`app/voice/router.py:152-156`

`_send_tts` sends `"streamSid": call_sid`. Twilio Media Streams requires the
`streamSid` issued in the `start` event, which this code never reads.

**Failure scenario:** Twilio silently discards media frames whose `streamSid`
doesn't match the active stream. The caller hears the call connect and then
nothing — the AI's greeting and every reply are dropped. LIKELY rather than
CONFIRMED only because it depends on Twilio's runtime behaviour, but the code
never captures the real `streamSid` anywhere, so there is no path by which it
could be correct.

**Fix:** capture `msg["start"]["streamSid"]` on the `start` event and use it for
all outbound media.

### [x] H3 — Public demo chat is an unmetered LLM cost sink
`app/public/router.py:185-216`

`POST /demo/chat` has no authentication, no rate limit, and no cap on individual
message length — only a 30-message count limit.

**Failure scenario:** A script posts 30 messages of 50 KB each in a loop. Each
request bills ~400k input tokens against your key. There is no throttle to stop
it and no per-IP budget. `book_demo` on the same router *does* have a Redis
throttle, so the omission is inconsistent rather than deliberate.

**Fix:** Redis per-IP rate limit, a per-message character cap, and a daily budget
guard.

### [x] H4 — Invalid API key returns HTTP 500 instead of 401
`app/v1/router.py:36-37`, `app/mcp/server.py:98-99`

Both call `.single()` on the `api_keys` lookup. supabase-py raises when no row
matches rather than returning empty data. In `mcp/server.py` the `_auth` call
(line 205) sits **outside** the surrounding `try`, so nothing catches it.

**Failure scenario:** Any client with a wrong or rotated key gets an opaque 500.
Legitimate integrations cannot distinguish "bad credentials" from "server
broken", and the 500s pollute error monitoring. Note `FLOWS.md` records this same
`.single()` pattern as fixed elsewhere — these two are regressions of a
previously-known bug.

**Fix:** use `.maybe_single()` or `.limit(1)` and return 401 explicitly.

### [x] H5 — Fire-and-forget webhook tasks can be garbage collected
`app/integrations/events.py:155`, `:147`

`asyncio.create_task(...)` is called without retaining a reference. CPython only
holds a weak reference to running tasks; a task with no strong reference may be
collected mid-flight.

**Failure scenario:** Under GC pressure a `lead.created` webhook is silently
dropped — no delivery, no log row update, no error. The customer's CRM
desynchronises and nothing indicates why.

**Fix:** keep a module-level `set` of pending tasks and discard on completion.

### [x] H6 — Webhook retry loop runs once per uvicorn worker
`app/main.py:91-101`

The retry loop is started inside `lifespan`, which executes in **every** worker
process. `docker-compose.prod.yml` runs 4 workers.

**Failure scenario:** Four workers independently query `webhook_logs` for due
retries and deliver each one — the customer's endpoint receives up to 4×
duplicate deliveries per retry cycle, with no idempotency key to deduplicate on.

**Fix:** a Redis lock so exactly one worker owns the loop, or move it to a
separate Railway service.

### [x] H7 — Tenant-supplied webhook URLs enable SSRF
`app/integrations/events.py:39-60`

`endpoint["url"]` comes from customer input and is POSTed to with no validation
of scheme, host, or resolved IP.

**Failure scenario:** A tenant registers a webhook pointing at
`http://169.254.169.254/latest/meta-data/` or a Railway private-network address.
Your server makes the request from inside the trust boundary and writes the
response status into `webhook_logs`, which the tenant can read back — a blind
SSRF with an oracle. Higher risk on Railway than on the current setup because of
private service networking.

**Fix:** allowlist `https://`, resolve the host and reject private/link-local/
loopback ranges, disable redirects.

### [x] H8 — Any company member can mint full-scope API keys
`app/integrations/api_keys_router.py:43-61`

`create_key` depends only on `CurrentUser` + `CompanyId`. It never calls
`require_owner_or_admin`, which exists at `app/auth/middleware.py:19`.

**Failure scenario:** A low-privilege member creates an API key with
`leads:write`, then uses `/v1` or `/mcp` to read and modify all company data
outside the dashboard's permission model, with no audit trail beyond `last_used`.

**Fix:** add the `require_owner_or_admin` dependency; cap keys per company.

### [x] H9 — CRM OAuth tokens stored in plaintext
`app/integrations/events.py:109-114`, `supabase/migrations/20260720_crm_connections.sql`

`access_token` and `refresh_token` for HubSpot and Zoho are written to
`crm_connections` as plain text columns.

**Failure scenario:** Any read access to that table — a leaked service key, a SQL
injection elsewhere, a Supabase backup, or the service-role key that every
backend route already uses — yields live OAuth tokens granting write access to
customers' CRMs. Refresh tokens are long-lived, so rotation of your own keys does
not revoke them.

**Fix:** encrypt at rest with `APP_SECRET_KEY`-derived key material (the
`cryptography` package is already installed), or use Supabase Vault.

---

## MEDIUM

### [x] M1 — Audio buffer is 160 ms, not the documented 1 second
`app/voice/router.py:30`

`AUDIO_BUFFER_CHUNKS = 8` is commented "~1 second of 8kHz mulaw". Twilio media
frames are 20 ms each, so 8 chunks is **160 ms**. A Deepgram REST call fires
roughly 6× per second per call, each transcribing a fragment far too short to
contain a complete phrase. Drives both cost and the latency problem in M2.

### [x] M2 — STT uses the batch endpoint, not streaming
`app/voice/stt.py:1-5, 43-49`

The module docstring says "streaming transcription over WebSocket"; the code
POSTs to Deepgram's pre-recorded `/v1/listen`. There is no VAD or endpointing, so
utterances are cut on a fixed byte boundary mid-word.

### [x] M3 — Synchronous translation blocks the event loop
`app/shared/language.py:21-38`

`GoogleTranslator(...).translate(...)` is a blocking HTTP call invoked from
`async` code in both the chat and voice paths.

### [x] M4 — Synchronous company fetch on every voice turn
`app/voice/conversation.py:47-49`

`sb.table("companies").select("*")...execute()` runs per turn, blocking, fetching
all columns. The company row changes rarely and should be cached in Redis.

### [x] M5 — Client IP is attacker-controlled, defeating the throttle
`app/public/router.py:17-24`

`CF-Connecting-IP` and `X-Forwarded-For` are trusted unconditionally with no
check that the request actually arrived via a trusted proxy.

**Failure scenario:** `curl -H "CF-Connecting-IP: <random>"` gives a fresh
throttle bucket per request, nullifying the `book_demo` rate limit. On Railway
there is no Cloudflare in front by default, so the header is fully spoofable.

### [x] M6 — reCAPTCHA fails open
`app/public/router.py:27-39`

Returns `True` when unconfigured *and* on any exception. A verification outage or
a malformed response silently disables bot protection.

### [x] M7 — Demo email crashes when a discount has no price
`app/public/router.py:153-162`

The discount block renders `${body.original_price:.2f}` guarded only by
`if body.discount_pct`. All three price fields are `Optional[float] = None`.

**Failure scenario:** A client posts `discount_pct=20` with null prices —
`TypeError: unsupported format string passed to NoneType` — unhandled, HTTP 500,
and the demo request is lost after already being inserted.

### [x] M8 — Unescaped user input interpolated into outbound email HTML
`app/public/router.py:133-178`

`body.name`, `body.email`, `body.agency`, `body.country`, `body.monthly_calls`
are f-string-interpolated into the email body with no escaping, including inside
`href` attributes.

**Failure scenario:** An attacker submits a name containing `</a><a href="...">`
and turns your own notification email into a convincing phishing link, sent from
your domain to yourself.

### [x] M9 — `bootstrap_company` can silently relocate an existing user
`app/auth/middleware.py:49-51`

`upsert` on `users` overwrites `company_id` and resets `role` to `owner` for an
id that already exists, with no check for a prior company link.

### [x] M10 — `last_used` write on every API request
`app/v1/router.py:44-45`, `app/mcp/server.py:102-103`

Every authenticated read triggers a write to `api_keys`, doubling round-trips and
generating unnecessary row churn. Should be sampled or debounced.

### [x] M11 — Untyped JSON-RPC arguments reach `min()` unvalidated
`app/mcp/server.py:119, 145, 154`

`min(args.get("limit", 20), 100)` raises `TypeError` when a client sends
`"limit": "20"` — legal JSON-RPC, since the schema is advertised but never
enforced server-side. Caught by the generic handler and reported as "Internal
server error", masking a client error as a server fault. Negative values are also
unguarded.

### [x] M12 — Unguarded `result.data[0]` after insert
`app/v1/router.py:90`, `app/mcp/server.py:133`, `app/auth/middleware.py:47`,
`app/integrations/api_keys_router.py:60`

`IndexError` → 500 whenever an insert returns no representation (RLS rejection,
trigger, or a `returning=minimal` client default).

### [x] M13 — Default `LLM_MODEL` is incompatible with the client
`app/config.py:17`

Default is `claude-sonnet-4-6`, but `app/shared/llm.py:10` constructs
`openai.AsyncOpenAI`. Any deploy that forgets to override `LLM_MODEL` fails at
the first LLM call. The default should be a valid model for the SDK in use.

### [x] M14 — SPA catch-all swallows unknown API paths
`app/main.py:163-171`

`@app.get("/{full_path:path}")` returns `index.html` with HTTP 200 for any
unmatched GET, so a typo'd or removed API route returns an HTML page instead of
404. Breaks client error handling and hides routing regressions.

### [ ] M15 — Production guards are inert in the committed environment
`.env` (`APP_ENV=development`)

The `APP_SECRET_KEY` and `TELEPHONY_AUTH_TOKEN` guards in `main.py` are gated on
`APP_ENV == "production"`. The environment file ships as `development`, so both
protections are off by default and only activate if Railway's env is set
correctly.

---

## LOW

### [x] L1 — CI "Verify imports" step is a no-op
`.github/workflows/ci.yml`

The comprehension ends in `and False`, so `errors` is always empty and no file is
ever actually parsed. The step prints a count and passes unconditionally — CI has
never once verified that the app imports.

### [ ] L2 — No test suite
Only `scripts/test_login.py`, a manual script. Nothing gates a regression.

### [x] L3 — 115 MB of orphaned model weights
`models/kokoro/` is referenced only by the stale `Dockerfile`; no Python source
imports `kokoro` or `faster_whisper` any more. `models/` is untracked in git, so
the Dockerfile's `COPY models/kokoro` would fail on any clean clone.

### [x] L4 — Uploads written to ephemeral local disk
`app/main.py:87`

`uploads/` does not survive a Railway redeploy. `SUPABASE_STORAGE_BUCKET` is
configured but unused.

### [x] L5 — Demo app duplicated and diverged
`nexa_demo_vercel/` exists both inside `nexa_desk/` and at `AI_Dev/` top level.
`layout.jsx` and `demoPrompt.js` differ; the API routes exist only in the outer
copy. `demoPrompt.js` (14.8 KB) also duplicates `app/shared/prompts.py`.

### [x] L6 — Dashboard ships an in-browser Whisper runtime
`dashboard/package.json` pulls `onnxruntime-web` / `onnxruntime-node` and
`src/components/whisper-worker.js`. Large Vercel bundle for a feature the Vercel
demo already covers server-side.

### [ ] L7 — RLS is bypassed by the backend
`app/dependencies.py:19-22`

The SQL schema's row-level security is thorough and correct — but every backend
route uses the service-role client, which bypasses it. Isolation therefore rests
entirely on hand-written `.eq("company_id", ...)` filters. Those are correct in
`v1/` and `mcp/` today; C1 is what happens when one is missed. Consider this a
standing architectural risk rather than a specific bug.

---

## Not defects

Recorded so they aren't re-investigated:

- **`call_session.py` is fully Redis-backed** with a 1 h TTL. No in-memory call
  state — horizontal scaling on Railway is safe.
- **RLS policies in `alembic/schema.sql:353-420`** are comprehensive and
  correctly written across all 9 tables (see L7 for the caveat).
- **`_RETRY_DELAYS` indexing in `events.py:67-69` is safe** — the
  `next_attempt > len(...)` guard short-circuits before the out-of-range index.
- **`key_prefix = raw_key[:16]`** in `api_keys_router.py:50` is correct:
  `"nxd_live_"` is 9 chars + 7 hex = 16.
- **The pricing discount ladder** is server-authoritative and prompt-injection
  resistant by design (`app/pricing/router.py:47-68`) — the LLM never chooses the
  percentage.

---

## Deferred — cost and architecture

Not fixed in this pass; recorded for a decision after deploy.

- **TTS is ~85% of per-minute call cost.** ElevenLabs at ~$0.12–0.22 per 1k chars
  versus OpenAI `tts-1` at ~$0.015. Switching drops per-minute cost from ~$0.13
  to ~$0.025.
- **Overage pricing is below cost after discount.** `PER_MINUTE_OVERAGE = $0.18`
  against ~$0.10–0.17 actual; the 20% discount ladder puts it at $0.144 — a loss
  on ElevenLabs' lower tiers.
- **Sequential turn pipeline** costs ~2.5–4.5 s of dead air. Addressed by the
  streaming rewrite (step 6), not by a point fix.
