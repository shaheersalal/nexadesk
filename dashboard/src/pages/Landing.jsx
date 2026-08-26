import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Phone } from 'lucide-react'
import FlightPath from '../components/flight/FlightPath'
import Cruise from '../components/flight/Cruise'
import VoiceDemoWidget from '../components/VoiceDemoWidget'
import DemoPreviewModal from '../components/DemoPreviewModal'
import '../styles/flight.css'

/* The live demo line. E.164 for the tel: href, formatted for display. */
const PHONE_E164 = '+17813655768'
const PHONE_DISPLAY = '+1 (781) 365-5768'

/* One conversion action, one label, reused verbatim in nav, hero and footer. */
const CTA = 'Call the live line'

const METRICS = [
  { value: '24/7', label: 'Inbound calls answered', note: 'No voicemail, no queue' },
  { value: '<1s', label: 'To first spoken word', note: 'Streamed, not batched' },
  { value: '0', label: 'Prices ever invented', note: 'Grounded or it is not said' },
]

const CAPABILITIES = [
  {
    title: 'It answers the phone',
    body: 'A real number your clients dial. Calls are transcribed as they are spoken, answered while the sentence is still being generated, and logged in full.',
    detail: 'Streaming speech recognition with server-side voice activity detection — it knows the difference between a pause and a finished thought.',
  },
  {
    title: 'It knows your listings',
    body: 'Upload brochures, paste descriptions, or let it read your property records. It answers from your inventory, not from the internet.',
    detail: 'Documents are chunked, embedded and re-ranked per query, then scored for confidence before a word is spoken.',
  },
  {
    title: 'It refuses to guess',
    body: 'When the answer is not in your knowledge base it says so and takes a message. That is the designed behaviour, not a limitation.',
    detail: 'An invented price is a liability with your name on it. The system is built to lose gracefully rather than improvise.',
  },
  {
    title: 'It qualifies and books',
    body: 'Every caller is scored on budget, timeline and intent. Viewings go straight into your calendar; the hottest leads surface first.',
    detail: 'Lead scoring is rule-based and runs without an extra model call, so it costs nothing in latency.',
  },
  {
    title: 'It keeps agencies apart',
    body: 'Each agency has its own number, its own knowledge, its own leads. An unrecognised caller gets a neutral message, never someone else’s data.',
    detail: 'Tenant isolation is enforced on every query and every retrieval, and an unknown number is answered by nobody rather than by the wrong agency.',
  },
]

const PIPELINE = [
  { stage: 'Caller speaks', detail: 'Audio streams in continuously' },
  { stage: 'Transcribed live', detail: 'End-of-utterance detected, not timed' },
  { stage: 'Your knowledge searched', detail: 'Retrieved, re-ranked, confidence scored' },
  { stage: 'Reply streams out', detail: 'Spoken from the first complete clause' },
]

function Nav() {
  return (
    <header className="relative z-20">
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <Link to="/" className="flex items-center gap-2.5 text-[15px] font-semibold tracking-[-0.01em]">
          <span
            className="grid h-7 w-7 place-items-center rounded-[9px] text-[13px] font-bold"
            style={{ background: 'var(--accent-cta)', color: '#fff' }}
          >
            N
          </span>
          NexaDesk
        </Link>
        <div className="flex items-center gap-7 text-[14px]">
          <Link to="/login" className="hidden transition-colors sm:block hover:opacity-70"
                style={{ color: 'var(--ink-soft)' }}>
            Sign in
          </Link>
          <a
            href={`tel:${PHONE_E164}`}
            className="rounded-full px-4 py-2 text-[13.5px] font-medium transition-transform duration-[var(--motion-fast)] hover:-translate-y-px"
            style={{ border: '1px solid var(--panel-edge)', background: 'var(--panel)' }}
          >
            {CTA}
          </a>
        </div>
      </nav>
    </header>
  )
}

/* Fold: stacked. Headline sits ~22% down the fold; nothing else rides it. */
function Hero() {
  return (
    <section className="relative z-10 mx-auto flex min-h-[88vh] max-w-4xl flex-col justify-start px-6 pb-24 pt-[22vh] text-center">
      <h1 className="text-balance text-[clamp(2.6rem,7vw,4.6rem)] font-semibold leading-[1.02] tracking-[-0.035em]">
        Your phone stops
        <br />
        going unanswered.
      </h1>

      <p
        className="mx-auto mt-7 max-w-lg text-[17px] leading-relaxed"
        style={{ color: 'var(--ink-soft)' }}
      >
        An AI receptionist for estate agencies that answers every call, day or night.
      </p>

      <div className="mt-10 flex flex-col items-center gap-4">
        <a
          href={`tel:${PHONE_E164}`}
          className="group inline-flex items-center gap-3 rounded-full px-7 py-4 text-[19px] font-semibold tracking-[-0.01em] text-white shadow-lg transition-transform duration-[var(--motion-base)] ease-[var(--ease-out)] hover:-translate-y-0.5"
          style={{ background: 'var(--accent-cta)', boxShadow: '0 1px 2px rgba(0,0,0,.16), 0 14px 34px -12px rgba(200,112,58,.55)' }}
        >
          <Phone className="h-[18px] w-[18px]" />
          {PHONE_DISPLAY}
        </a>
        <p className="text-[13px]" style={{ color: 'var(--ink-mute)' }}>
          Dial it now — it answers. No signup, no form.
        </p>
      </div>
    </section>
  )
}

function Proof() {
  return (
    <section className="relative z-10 mx-auto max-w-5xl px-6 py-24">
      <div className="grid gap-px overflow-hidden rounded-[20px]"
           style={{ background: 'var(--hairline)', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))' }}>
        {METRICS.map(m => (
          <div key={m.label} className="lift p-8" style={{ background: 'var(--panel)' }}>
            <p className="text-[2.6rem] font-semibold leading-none tracking-[-0.04em] tabular-nums"
               style={{ color: 'var(--accent)' }}>
              {m.value}
            </p>
            <p className="mt-3 text-[14.5px] font-medium">{m.label}</p>
            <p className="mt-1 text-[13px]" style={{ color: 'var(--ink-mute)' }}>{m.note}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

/* Distinct family: a vertical timeline, not cards and not a split. */
function Pipeline() {
  return (
    <section className="relative z-10 mx-auto max-w-3xl px-6 py-28">
      <h2 className="lift text-[clamp(1.9rem,4vw,2.6rem)] font-semibold leading-[1.08] tracking-[-0.03em]">
        What happens in the second
        <br className="hidden sm:block" /> after someone speaks
      </h2>

      <ol className="mt-12">
        {PIPELINE.map((s, i) => (
          <li key={s.stage} className="lift relative flex gap-6 pb-10 last:pb-0">
            <div className="flex flex-col items-center">
              <span
                className="grid h-8 w-8 shrink-0 place-items-center rounded-full font-mono text-[11px] tabular-nums"
                style={{ border: '1px solid var(--accent)', color: 'var(--accent)' }}
              >
                {i + 1}
              </span>
              {i < PIPELINE.length - 1 && (
                <span className="mt-1 w-px flex-1" style={{ background: 'var(--hairline)' }} />
              )}
            </div>
            <div className="pt-1">
              <p className="text-[16.5px] font-medium tracking-[-0.01em]">{s.stage}</p>
              <p className="mt-1 text-[14px]" style={{ color: 'var(--ink-soft)' }}>{s.detail}</p>
            </div>
          </li>
        ))}
      </ol>

      <p className="lift mt-10 border-l-2 pl-5 text-[14.5px] leading-relaxed"
         style={{ borderColor: 'var(--accent)', color: 'var(--ink-soft)' }}>
        Nothing waits for the previous step to finish. The earlier design queued them and
        left two to four seconds of silence on every turn — which callers hear as a dropped line.
      </p>
    </section>
  )
}

function TryInBrowser() {
  return (
    <section className="relative z-10 mx-auto max-w-2xl px-6 py-24">
      <div className="lift panel r-lg p-8">
        <p className="text-[13px]" style={{ color: 'var(--ink-mute)' }}>
          Somewhere you cannot take a call?
        </p>
        <h2 className="mt-2 text-[1.6rem] font-semibold tracking-[-0.025em]">
          Speak to it here instead
        </h2>
        <div className="mt-8">
          <VoiceDemoWidget />
        </div>
      </div>
    </section>
  )
}

function FinalCall({ onRequestAccess }) {
  return (
    <section className="relative z-10 mx-auto max-w-3xl px-6 py-32 text-center">
      <h2 className="lift text-[clamp(2rem,5vw,3rem)] font-semibold leading-[1.05] tracking-[-0.03em]">
        Hear it before you believe it
      </h2>
      <div className="lift mt-9 flex flex-col items-center gap-4">
        <a
          href={`tel:${PHONE_E164}`}
          className="inline-flex items-center gap-3 rounded-full px-7 py-4 text-[18px] font-semibold text-white transition-transform duration-[var(--motion-base)] ease-[var(--ease-out)] hover:-translate-y-0.5"
          style={{ background: 'var(--accent-cta)', boxShadow: '0 12px 30px -12px rgba(200,112,58,.5)' }}
        >
          <Phone className="h-[17px] w-[17px]" />
          {PHONE_DISPLAY}
        </a>
        <p className="text-[13px]" style={{ color: 'var(--ink-mute)' }}>
          A US number, dialable worldwide. Your usual international rates apply.
        </p>
        <button
          onClick={onRequestAccess}
          className="mt-2 text-[14px] underline decoration-1 underline-offset-4 transition-opacity hover:opacity-70"
          style={{ color: 'var(--ink-soft)' }}
        >
          Or request access for your agency
        </button>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className="relative z-10 border-t" style={{ borderColor: 'var(--hairline)' }}>
      <div className="mx-auto flex max-w-6xl flex-col gap-8 px-6 py-12 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-[14px] font-semibold">NexaDesk</p>
          <p className="mt-1.5 text-[13px]" style={{ color: 'var(--ink-mute)' }}>
            AI receptionist for real estate. Answers in English.
          </p>
        </div>
        <nav className="flex flex-wrap gap-x-7 gap-y-3 text-[13.5px]" style={{ color: 'var(--ink-soft)' }}>
          <a href={`tel:${PHONE_E164}`} className="hover:opacity-70">{CTA}</a>
          <Link to="/login" className="hover:opacity-70">Sign in</Link>
        </nav>
      </div>
    </footer>
  )
}

export default function Landing() {
  const [accessOpen, setAccessOpen] = useState(false)

  return (
    <div className="flight-field relative min-h-screen font-sans antialiased">
      <FlightPath />
      <Nav />
      <main>
        <Hero />
        <Proof />
        <Cruise
          eyebrow="On board"
          heading="What it does once the call connects"
          intro="Five things, in the order a call actually goes."
          items={CAPABILITIES}
        />
        <Pipeline />
        <TryInBrowser />
        <FinalCall onRequestAccess={() => setAccessOpen(true)} />
      </main>
      <Footer />
      {accessOpen && <DemoPreviewModal onClose={() => setAccessOpen(false)} />}
    </div>
  )
}
