import { Link } from 'react-router-dom'
import { ArrowLeft, ArrowUpRight } from 'lucide-react'
import { POSTS } from '../content/posts'
import '../styles/flight.css'

export default function Notes() {
  return (
    <div className="flight-field relative min-h-screen font-sans antialiased">
      <div className="relative z-10 mx-auto max-w-3xl px-6 py-14">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-[13.5px] transition-opacity hover:opacity-70"
          style={{ color: 'var(--ink-mute)' }}
        >
          <ArrowLeft className="h-4 w-4" /> NexaDesk
        </Link>

        <header className="mt-14 mb-16">
          <h1 className="text-[clamp(2.2rem,5vw,3.2rem)] font-semibold leading-[1.05] tracking-[-0.035em]">
            Engineering notes
          </h1>
          <p className="mt-5 max-w-xl text-[16.5px] leading-relaxed" style={{ color: 'var(--ink-soft)' }}>
            Real bugs from building a voice AI receptionist — retrieval calibration,
            telephony authentication, streaming latency, and the CI failure that hid
            behind an exit code for two months.
          </p>
        </header>

        <div className="flex flex-col">
          {POSTS.map(p => (
            <Link
              key={p.slug}
              to={`/notes/${p.slug}`}
              className="group border-t py-8 first:border-t-0"
              style={{ borderColor: 'var(--hairline)' }}
            >
              <div className="flex items-start justify-between gap-6">
                <div>
                  <p className="font-mono text-[11.5px] uppercase tracking-wider" style={{ color: 'var(--ink-mute)' }}>
                    {new Date(p.date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                    {' · '}{p.readingMinutes} min read
                  </p>
                  <h2 className="mt-2.5 text-[19px] font-medium leading-snug tracking-[-0.018em]">
                    {p.title}
                  </h2>
                  <p className="mt-2.5 text-[15px] leading-relaxed" style={{ color: 'var(--ink-soft)' }}>
                    {p.dek}
                  </p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {p.tags.map(t => (
                      <span
                        key={t}
                        className="r-sm px-2.5 py-1 text-[11.5px] font-medium"
                        style={{ background: 'var(--panel)', border: '1px solid var(--panel-edge)', color: 'var(--ink-mute)' }}
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
                <ArrowUpRight
                  className="mt-1 h-5 w-5 shrink-0 transition-transform duration-[var(--motion-base)] ease-[var(--ease-out)] group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
                  style={{ color: 'var(--accent)' }}
                />
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
