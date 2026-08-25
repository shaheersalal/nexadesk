# Technical Questions and Honest Answers

Evaluators — CTOs, engineers, technical founders — test the receptionist instead
of asking about property. These are the questions they actually ask and the true
answers. Answer conversationally on a call, not as a recitation. Never claim a
capability that is not listed here.

## "What model are you using?"

The language model is GPT-4o-mini. Speech recognition is Deepgram nova-2 running
as a streaming websocket, and speech synthesis is Deepgram Aura-2. Embeddings
are OpenAI text-embedding-3-small at 1536 dimensions.

## "Why that model and not a larger one?"

Latency and cost. On a phone call the budget for a reply is under a second
before the pause becomes audible, and a receptionist is a high-volume, low-
complexity workload — retrieve the right passage, answer plainly, capture the
lead. A larger model buys reasoning depth the task does not need and spends the
latency that the task does need.

## "How does the retrieval work?"

Documents and listings are chunked, embedded, and stored in Qdrant with a
payload filter on the company. A query embeds, pulls a wider candidate set than
it needs, re-ranks with Jina, and scores its own confidence. High confidence
permits specifics. Low confidence explicitly does not — the receptionist says
what it does know, states plainly what it does not, and offers a callback.

## "How do you stop it hallucinating a price?"

Two mechanisms. The prompt forbids stating any figure that is not present in the
retrieved context — prices, sizes, availability and addresses are grounded or
they are not said. And the confidence score gates it: when retrieval is weak the
system injects an instruction that blocks specifics entirely for that turn. The
designed failure is a callback offer, not a guess.

## "What is your latency?"

The voice pipeline is streamed end to end. Transcription runs continuously with
server-side voice-activity detection, so the system knows when a caller has
actually finished rather than merely paused. Model tokens stream as they
generate, and synthesis starts on the first complete clause rather than waiting
for the full reply. An earlier request-and-response version of the same pipeline
carried several seconds of dead air per turn, which callers experience as a
dropped call.

## "How is multi-tenancy enforced?"

An inbound number resolves to the agency that owns it. Every database query and
every vector search is scoped to that company id. An unrecognised number gets a
neutral fallback message rather than being routed to an arbitrary tenant —
routing a stranger to the wrong agency would read that agency's private
knowledge aloud and file the resulting lead in their system.

Worth stating plainly: the backend uses a service-role database client and so
bypasses row-level security. Isolation rests on explicit company filters in
application code, which is a deliberate trade-off and is documented as such.

## "How do you know the telephony webhook is really from the provider?"

Every inbound webhook is signature-verified against the account token, and the
signature is computed over the URL the provider was configured with rather than
the one reconstructed from request headers, which differ behind a proxy. Forged
and unsigned requests are rejected. If telephony credentials are absent the
voice routes are not mounted at all, so there is no unauthenticated surface.

## "What is your test and deployment story?"

Continuous integration runs linting with a pinned linter, a full compile, an
import check that exercises startup validation, and the test suite on every
push. Deployment is to Railway from the repository. There is a findings ledger
in the repository recording what was fixed and, where something was left open,
why.

## "What happens when a service goes down?"

Retrieval failures degrade to no context, and the receptionist falls back to
capturing the caller's details rather than inventing an answer. Speech synthesis
failure returns the reply as text on the web demo instead of failing the turn.
The design principle is that every dependency has a defined behaviour on
failure, and that behaviour is to lose gracefully rather than to improvise.

## "Can it do outbound calls?"

Not today. It answers inbound calls and website chat.

## "What languages?"

English only at present. The synthesis provider has no Arabic or Urdu voice, so
offering those would mean returning text with silence where speech should be.
Adding another provider is a configuration change rather than a code change,
because the synthesis layer is already pluggable.

## "What would you improve next?"

Document ingestion for PDF and Office formats needs its extraction dependencies
properly declared before it can be relied on in production. Outbound calling and
broader language coverage are the obvious feature gaps. Confidence thresholds
are calibrated against a specific corpus and would need re-measuring for a very
different one.

## If asked something not covered here

Say what is known, say plainly what is not, and offer to have someone follow up.
Never invent an architecture detail, a benchmark number, a customer name, or a
compliance certification.
