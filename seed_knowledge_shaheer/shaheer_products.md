# Shaheer Salal - Products and Shipped Work

Reference facts for the assistant on shaheer.dev and Shaheer's own phone line.
The status given for each product (live, offline, built) is its actual current
state as recorded here. This document contains no behaviour rules; those live
in the system prompt.

## NexaDesk - live, this assistant's own product

A 6-agent AI receptionist deployed for real estate agencies across the Gulf
and US property management. Handles WhatsApp and voice inquiries, qualifies
leads with intelligent questions, and books property viewings around the
clock. Agencies using it wake up to scheduled viewings instead of missed
messages after-hours.

Pricing: AED 1,300 setup + AED 300/month for the core package; US property
management pricing available on request. Stack: Python, FastAPI, OpenAI
(GPT-4o-mini), Twilio, Redis, Qdrant, Supabase, React. Site: nexadesk.site.

### The 6 agents, exactly - never guess or rename these

Technical evaluators ask what the agents actually are. These are the six,
and there are no others (a "booking agent", "sentiment agent" or
"summarisation agent" does NOT exist - do not invent one):

1. **Query rewriter** - rewrites the caller's raw utterance into a clean
   retrieval query, running in parallel with the router.
2. **Router / classifier** - classifies intent into one of: knowledge,
   qualify, appointment, escalate.
3. **Knowledge agent** - answers from RAG-retrieved context only, behind a
   confidence gate (CONFIDENT / PARTIAL / NO_MATCH) so it can't answer past
   what was actually retrieved.
4. **Qualifier agent** - asks one qualifying question at a time and drives
   lead capture.
5. **Escalation agent** - hands off to a human when asked or when the
   conversation warrants it.
6. **Field extractor** - pulls structured fields (name, phone, email,
   budget, timeline) out of the message, running in parallel with the reply
   so extraction never adds latency to what the caller hears.

Other architecture facts worth stating accurately if asked: Twilio Media
Streams feed Deepgram streaming STT, the reply is token-streamed back out
through TTS (target: under ~2s round trip per turn); multi-tenancy is
enforced in Postgres with row-level security, not just application-side
filters; each business domain is a config entry (a "vertical") consumed by
one shared orchestrator rather than a forked codebase per domain.

The assistant on shaheer.dev IS a version of NexaDesk, configured for
Shaheer's own site instead of a real estate agency. It is the same product a
business would put on its own line.

## AskTax.pk - built and previously live with paying clients; currently offline

A RAG system for Pakistani CA (chartered accountancy) firms: search across
195K+ vectors spanning 4,491 FBR (Federal Board of Revenue) documents and
2,041 case laws, returning cited, verifiable answers in seconds instead of
hours of manual research. Multi-tenant firm accounts (a real per-firm plan
model: trial/basic/pro tiers, seat limits, per-seat monthly query quotas),
freemium billing, and an admin panel.

The clients are Pakistani CA firms. Individual client and firm names are
deliberately unpublished, so the public record describes the type of client
rather than naming any one of them. A reference can be arranged directly by
Shaheer.

**Current status: the site is offline for maintenance.** The reason is not
public. What is known: it is offline for maintenance, the experience behind it
is real, and Shaheer can explain the current state directly. There is no
published return date, and no record here of it failing, losing customers, or
being actively rebuilt.

The experience it represents is real and demonstrable: production multi-tenant
RAG at scale, serving paying accounting-firm clients.

## Content Factory - built, self-hosted, not a public product

A fully self-hosted n8n pipeline: give it a niche and tone, it writes the
script (Ollama), narrates it (Kokoro TTS), generates a 9:16 hero image
(Flux.1 via ComfyUI), composes the video (FFmpeg), burns word-accurate
captions (WhisperX), pauses for a Telegram approve/reject, then posts
simultaneously to TikTok, Instagram Reels, YouTube Shorts, and Facebook
Reels. Entirely Docker-based - zero per-token API costs, zero cloud AI
spend. This is a capability demonstration and something Shaheer can build
a version of for a client, not a live product with its own URL.

## JobScout - built, beta; demo currently offline

A personal job-search agent: reads a resume, extracts a preference profile,
then runs daily - ingests listings from five sources (Remotive, RemoteOK, HN
"Who's Hiring", Adzuna, Arbeitnow), embeds each one in Qdrant, re-ranks
against the profile with GPT-4o-mini, and emails a daily digest with an
auto-generated cover letter per application. Built by Shaheer for himself in
one session. Stack: FastAPI, Celery, Redis, PostgreSQL, Qdrant,
sentence-transformers, GPT-4o-mini, Docker. Open source on GitHub
(github.com/shaheersalal/AI-Job-Searcher-Agent). **The live search demo is
currently offline** - if asked to try it, say so and point to the GitHub
repo instead of claiming it works right now.

## Client work - representative, not exhaustive

- **Cold-outreach automation**: five separate tools running Shaheer's own
  lead generation - Apollo-based prospect discovery, LinkedIn content
  automation, a Playwright listing scraper, Reddit outreach, and a cold-email
  sequencer with reply/unsubscribe handling. Built independently per channel,
  not as one platform. Stack: Python, Playwright, Docker.
- **Content creators**: an 8-step AI pipeline taking a niche to a fully
  researched video idea - validation, title generation, hook writing,
  thumbnail concepts, cost estimates - in under 60 seconds. Stack: React,
  TypeScript, Gemini 2.5, Vite, Imagen 3.
- **EdTech (Quran classes for overseas Pakistanis)**: a full-stack platform
  with live classrooms (Jitsi), a bilingual English/Urdu interface, and a
  student management backend. Built for a community, not for scale.
- A verified 5.0-star Upwork review (data extraction, 500+ companies):
  "Very fast delivery, clean and well-organised output. Shaheer knew exactly
  what to do and didn't need hand-holding."

## Comparisons with other tools

There is no published comparison against any named competitor, and no
assessment of any competing tool on the record here. What is on the record is
what Shaheer builds and why, in this document and in the studio pitch.
