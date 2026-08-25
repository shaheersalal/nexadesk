/**
 * Engineering notes.
 *
 * Real debugging from building NexaDesk, written up honestly. These exist
 * because the alternative — a keyword-stuffed "AI receptionist" page — does not
 * rank for competitive head terms and reads as spam to the technical audience
 * this product is sold to. Long-tail engineering writing does both jobs: it
 * earns links, and it is the strongest available evidence that whoever built
 * the product knows what they are doing.
 *
 * Block types: p | h2 | list | code | quote | note
 */

export const POSTS = [
  {
    slug: 'ci-red-for-two-months-pytest-import-mode',
    title: 'Our CI was red for two months. The bug was how we invoked pytest.',
    dek: 'Every test passed locally and failed in GitHub Actions. The cause was not the code, the dependencies, or the runner — it was one word on the command line.',
    date: '2026-08-24',
    readingMinutes: 6,
    tags: ['CI/CD', 'Python', 'Testing', 'Automation'],
    body: [
      { type: 'p', text: 'A build that has been red long enough stops being information. People learn the badge is decorative, stop opening the run, and the pipeline quietly becomes a formality. Ours had failed on every commit since early July while the suite passed on every developer machine — the specific failure mode that trains a team to ignore its own tooling.' },
      { type: 'p', text: 'The job reported exit code 2. That number is the whole story, and we missed it for weeks.' },
      { type: 'h2', text: 'Exit 1 and exit 2 are different failures' },
      { type: 'p', text: 'pytest exits 1 when tests run and some fail. It exits 2 when collection itself fails — the run never started. We read "the tests are failing" where the machine was saying "there are no tests, because nothing could be imported".' },
      { type: 'code', lang: 'text', text: 'E   ModuleNotFoundError: No module named app\nImportError while importing test module\n  /home/runner/work/.../tests/test_tts_provider.py' },
      { type: 'h2', text: 'Why it only happened in CI' },
      { type: 'p', text: 'Locally, everyone ran the module form. The workflow ran the console script.' },
      { type: 'code', lang: 'bash', text: 'python -m pytest      # what humans type\npytest                # what the workflow ran' },
      { type: 'p', text: 'They are not equivalent. The -m form puts the current working directory on sys.path — a documented property of -m, not of pytest. The bare console script does not. With no installed package and no pythonpath setting, the repository root was never importable, so every test module died on its first app import.' },
      { type: 'p', text: 'The application imported fine in the same job, because that step ran python -c "import app.main" — the module form again. Two steps apart, one with the working directory on the path and one without, and the difference invisible unless you already suspect it.' },
      { type: 'h2', text: 'The fix is one line' },
      { type: 'code', lang: 'ini', text: '# pytest.ini\n[pytest]\ntestpaths = tests\npythonpath = .' },
      { type: 'p', text: 'That makes both invocations behave identically, which is the actual goal. Pinning the invocation inside the workflow would have fixed the symptom while leaving the next person free to reintroduce it.' },
      { type: 'h2', text: 'The part that cost the most time' },
      { type: 'p', text: 'Diagnosing it was harder than fixing it, because GitHub exposes workflow logs only to repository administrators. The public API returns a conclusion and an exit code and nothing else. We could see that a step failed and not why.' },
      { type: 'p', text: 'The way out was to make the failure public deliberately — emit the error lines as workflow annotations, which are readable without admin rights.' },
      { type: 'code', lang: 'yaml', text: 'if [ $code -ne 0 ]; then\n  grep -E "^E |ModuleNotFoundError|ImportError" pytest-output.txt \\\n    | tail -n 8 \\\n    | while IFS= read -r line; do echo "::error::$line"; done\nfi' },
      { type: 'note', text: 'One annotation per line, deliberately. An earlier attempt escaped newlines into a single annotation with sed, and the escaping broke the YAML badly enough that GitHub ran the workflow with zero jobs — visible only as the run being named after the file path instead of CI.' },
      { type: 'h2', text: 'What to take from it' },
      { type: 'list', items: [
        'Read the exit code before reading the output. 2 is not a worse 1.',
        'Any difference between how humans run tests and how CI runs them is a latent failure, whatever the reason for it.',
        'Pin the environment in configuration the whole team shares, not in the one file only CI reads.',
        'If your logs need admin rights to read, your build is undiagnosable by exactly the contributors most likely to be blocked by it.',
      ] },
    ],
  },

  {
    slug: 'rag-confidence-thresholds-are-not-portable',
    title: 'Your RAG confidence thresholds belong to a scoring function you probably changed',
    dek: 'Retrieval returned the right passage and the assistant refused to use it. Retrieval was never the problem — the number we compared it against was measured on a different scale.',
    date: '2026-08-25',
    readingMinutes: 8,
    tags: ['RAG', 'AI', 'Vector Search', 'Embeddings', 'LLM'],
    body: [
      { type: 'p', text: 'A retrieval-augmented system usually has a gate: score the retrieved context, and if confidence is too low, decline to answer rather than invent something. For anything quoting prices or availability, that gate is the most important safety property in the product.' },
      { type: 'p', text: 'Ours was scoring correct retrievals as NO_MATCH. The receptionist would find exactly the right listing and then tell the caller it did not have the details.' },
      { type: 'h2', text: 'Two scoring functions, one set of thresholds' },
      { type: 'p', text: 'The pipeline embeds the query, pulls a wide candidate set from the vector store by cosine similarity, then re-ranks with a cross-encoder. Confidence came from the top score after reranking.' },
      { type: 'code', lang: 'python', text: 'SCORE_CONFIDENT = 0.78\nSCORE_PARTIAL   = 0.50' },
      { type: 'p', text: 'Those numbers were chosen for the reranker, which emits a calibrated 0-1 relevance score. But the reranker only runs when an API key is present. Without one, the code falls back to raw cosine similarity from the embedding model — and silently keeps comparing against reranker thresholds.' },
      { type: 'p', text: 'Cosine similarity from a modern embedding model does not occupy 0-1 in any useful sense. Measured against our own corpus:' },
      { type: 'code', lang: 'text', text: 'RELEVANT queries      0.413 - 0.742\nIRRELEVANT queries    0.000   (filtered out before scoring)' },
      { type: 'p', text: 'A clearly correct match at 0.64 was judged against a bar of 0.78 and discarded. The gate was not too strict. It was reading a different instrument.' },
      { type: 'h2', text: 'It failed silently, twice over' },
      { type: 'p', text: 'Nothing raised. The retrieval layer treats a low-confidence result the same as an empty one, and the assistant is designed to fall back to taking a message when it has no context. A broken gate is therefore behaviourally identical to an empty knowledge base — polite, plausible, and wrong.' },
      { type: 'quote', text: 'The most dangerous failures in an AI pipeline are the ones whose output is indistinguishable from correct conservative behaviour.' },
      { type: 'h2', text: 'The fix: make the scale explicit' },
      { type: 'p', text: 'The reranking function now reports whether it actually reranked, and the caller picks thresholds to match.' },
      { type: 'code', lang: 'python', text: 'async def _rerank(query, chunks, top_n) -> tuple[list[dict], bool]:\n    """Returns (chunks, reranked). The flag matters: the caller must know\n    which scale the scores are on before comparing them to a threshold."""\n    if not settings.RERANKER_API_KEY or not chunks:\n        return chunks[:top_n], False\n    ...\n\nconfident_at = CONFIDENT_RERANKED if reranked else CONFIDENT_COSINE' },
      { type: 'h2', text: 'Then we enabled the reranker, and it was miscalibrated too' },
      { type: 'p', text: 'Adding the key did not vindicate the original 0.78. Measured on the same corpus, reranked scores for valid queries ran 0.26 to 0.82 — and the low end was ordinary phrasing.' },
      { type: 'code', lang: 'text', text: '0.261  "Do you have anything in London?"     <- real listings exist\n0.330  "Houston family home"                 <- real listings exist\n0.818  "Canary Wharf apartment"' },
      { type: 'p', text: 'A vague, natural question scores far below a precise one even when both match real inventory. Callers ask the vague one. At a 0.78 bar the product would have failed most real traffic while passing every query an engineer thought to test.' },
      { type: 'p', text: 'The insight that fixed it: anything reaching the reranker has already cleared the cosine pre-filter, so irrelevant queries return nothing at all and score zero. The reranker is not separating relevant from irrelevant — it is only ordering what already survived. It does not need a high bar.' },
      { type: 'h2', text: 'What to take from it' },
      { type: 'list', items: [
        'A threshold is a measurement, not a constant. It belongs to the scoring function it was measured against.',
        'If a scoring path can be swapped by configuration, thresholds must swap with it, or the swap is a silent regression.',
        'Measure the distribution before picking a number, and measure it on the phrasing users actually produce.',
        'Test irrelevant queries too. Learning what your pipeline scores for "what is the capital of Peru?" is how you discover the pre-filter is doing the real work.',
      ] },
    ],
  },

  {
    slug: 'webhook-signature-validation-behind-a-proxy',
    title: 'The webhook signature bug that would have failed every phone call',
    dek: 'Signature validation passed in tests, passed locally, and would have rejected one hundred percent of real inbound calls. The URL the app reconstructed was not the URL that was signed.',
    date: '2026-08-25',
    readingMinutes: 5,
    tags: ['Voice AI', 'Telephony', 'Security', 'Webhooks'],
    body: [
      { type: 'p', text: 'Provider webhooks are authenticated by signing the request. The provider computes an HMAC over the destination URL plus the sorted form parameters; you recompute it with your auth token and compare. If they differ, you reject.' },
      { type: 'p', text: 'The obvious implementation reconstructs the URL from the incoming request.' },
      { type: 'code', lang: 'python', text: 'return validate_signature(str(request.url), dict(form), sig)' },
      { type: 'p', text: 'This is wrong the moment anything sits in front of your application.' },
      { type: 'h2', text: 'The scheme does not survive the proxy' },
      { type: 'p', text: 'The provider signs the https URL configured in its console. Behind a platform load balancer, TLS terminates at the edge and your process receives plain HTTP. ASGI servers honour X-Forwarded-Proto only from addresses listed in forwarded-allow-ips, which defaults to loopback — and the platform proxy is not on loopback.' },
      { type: 'p', text: 'So the app reconstructs http while the provider signed https. Different string, different HMAC, 403 on every call. Probing production made it unambiguous.' },
      { type: 'code', lang: 'text', text: 'signed over https://...  ->  403  Invalid signature\nsigned over http://...   ->  200  <Response><Connect><Stream/></Connect></Response>' },
      { type: 'p', text: 'The rest of the pipeline was healthy throughout. The phone line would simply never have answered, and the provider console would have shown webhook failures with no application error to correlate against.' },
      { type: 'h2', text: 'The fix that is not a security regression' },
      { type: 'p', text: 'The tempting fix is to widen forwarded-allow-ips so the framework honours the forwarded scheme. Do not. That simultaneously makes X-Forwarded-For client-controlled, and every per-IP rate limit in the application becomes forgeable by anyone who can set a header.' },
      { type: 'p', text: 'Validate against configuration instead — the same value the webhook was registered with, which is by definition what the provider signed, and which no caller can influence.' },
      { type: 'code', lang: 'python', text: 'def _callback_url(request) -> str:\n    base = (settings.WEBHOOK_BASE_URL or "").rstrip("/")\n    if not base:\n        return str(request.url)          # local dev, no proxy\n    url = f"{base}{request.url.path}"\n    return f"{url}?{request.url.query}" if request.url.query else url' },
      { type: 'note', text: 'Falling back to the request URL when no base is configured keeps local development working without credentials — the only environment where reconstructing from the request is actually correct.' },
      { type: 'h2', text: 'Why tests did not catch it' },
      { type: 'p', text: 'Because the test client and the application agree about the URL. Signature validation belongs to a small class of behaviours verifiable only against real deployment topology — anything depending on what a proxy did to the request is invisible to an in-process test.' },
      { type: 'p', text: 'The regression test we added does not test the HMAC. It asserts that the URL used for validation begins with the configured base rather than the request scheme, which is the property that actually broke.' },
      { type: 'h2', text: 'What to take from it' },
      { type: 'list', items: [
        'Any signature computed over a URL is a signature over your proxy topology.',
        'Never fix a proxy-header problem by trusting proxy headers more broadly. Check what else reads them first.',
        'Prefer configured values over reconstructed ones for anything security-relevant — configuration cannot be influenced by the caller.',
        'Some bugs are only reachable by probing the deployed system. Budget for that, and sign a request by hand when you need certainty.',
      ] },
    ],
  },

  {
    slug: 'streaming-voice-pipeline-latency',
    title: 'Why an AI receptionist has to stream, and what that costs',
    dek: 'The difference between a conversation and a hold queue is about two seconds. Request-and-response architectures cannot get under it.',
    date: '2026-08-25',
    readingMinutes: 7,
    tags: ['Voice AI', 'AI Receptionist', 'Latency', 'Architecture'],
    body: [
      { type: 'p', text: 'A caller tolerates roughly a second of silence before assuming something is wrong. They talk over you, or they hang up. That single number determines the entire architecture of a voice agent, and it rules out the obvious design.' },
      { type: 'h2', text: 'The obvious design does not work' },
      { type: 'p', text: 'Record the caller. Send the audio for transcription. Send the transcript to a language model. Send the reply to speech synthesis. Play the audio. Each stage waits for the previous one to finish.' },
      { type: 'code', lang: 'text', text: 'transcribe   ~600ms   (after the caller stops)\ngenerate     ~900ms   (full reply before first byte)\nsynthesise   ~700ms   (full audio before playback)\n             -------\n             ~2.2s of silence, best case' },
      { type: 'p', text: 'Our first version measured 2.5 to 4.5 seconds per turn. On a phone call that is not a slow product, it is a broken one — callers assumed the line had dropped.' },
      { type: 'h2', text: 'Streaming turns three waits into one' },
      { type: 'p', text: 'Every stage can begin before the previous one finishes.' },
      { type: 'list', items: [
        'Transcription runs continuously over a websocket rather than on a finished recording, so partial transcripts arrive while the caller is still speaking.',
        'The model streams tokens, so generation and synthesis overlap instead of queueing.',
        'Synthesis is chunked on clause boundaries — the first clause is spoken while the rest of the sentence is still being generated.',
      ] },
      { type: 'p', text: 'Perceived latency collapses to roughly the time to the first clause, because everything after it is already in flight.' },
      { type: 'h2', text: 'Knowing when the caller has finished' },
      { type: 'p', text: 'The harder problem is not speed, it is turn-taking. A fixed silence timeout is always wrong: too short and you interrupt someone thinking mid-sentence, too long and you add dead air to every turn.' },
      { type: 'p', text: 'Server-side voice activity detection solves it properly. The transcription service emits an explicit end-of-utterance signal distinguishing a pause from a finished thought, and that signal — not a timer — triggers generation.' },
      { type: 'h2', text: 'What streaming costs you' },
      { type: 'p', text: 'It is not free, and the costs are structural rather than incidental.' },
      { type: 'list', items: [
        'You cannot post-process a complete reply. Anything inspecting the full answer before speaking reintroduces the wait you just removed.',
        'Errors arrive mid-utterance. A synthesis failure halfway through a sentence needs a defined recovery, not a handler that abandons the turn.',
        'Every stage is stateful and long-lived, so session state must live somewhere both the websocket handler and the webhook handler can reach.',
        'Media frames must be addressed with the identifier from the stream start event, not the call identifier. Providers silently drop mismatched frames — no error, just silence, which is the hardest possible failure to debug.',
      ] },
      { type: 'h2', text: 'The part worth designing first' },
      { type: 'p', text: 'Retrieval sits in the middle of this and is the easiest place to lose the budget you just clawed back. Ours runs intent classification and query rewriting in parallel, so retrieval waits on one model round trip rather than two.' },
      { type: 'p', text: 'And when retrieval comes back weak, the correct behaviour is to say so quickly rather than to think harder. A fast honest answer keeps the conversation. A slow invented one loses the customer and creates a liability for the agency whose name is on the call.' },
    ],
  },
]

export const getPost = slug => POSTS.find(p => p.slug === slug)
