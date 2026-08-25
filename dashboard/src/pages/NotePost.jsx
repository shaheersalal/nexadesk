import { useEffect } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'
import { ArrowLeft, Phone } from 'lucide-react'
import { getPost, POSTS } from '../content/posts'
import '../styles/flight.css'

const PHONE_E164 = '+17813655768'
const PHONE_DISPLAY = '+1 (781) 365-5768'

function Block({ block }) {
  switch (block.type) {
    case 'h2':
      return (
        <h2 className="mt-14 mb-4 text-[1.55rem] font-semibold leading-snug tracking-[-0.025em]">
          {block.text}
        </h2>
      )
    case 'code':
      return (
        <pre
          className="r-md my-7 overflow-x-auto p-5 font-mono text-[13px] leading-relaxed"
          style={{ background: 'var(--panel)', border: '1px solid var(--panel-edge)' }}
        >
          <code>{block.text}</code>
        </pre>
      )
    case 'list':
      return (
        <ul className="my-6 flex flex-col gap-3">
          {block.items.map(item => (
            <li key={item} className="flex gap-3 text-[16px] leading-relaxed" style={{ color: 'var(--ink-soft)' }}>
              <span aria-hidden="true" className="mt-[9px] h-1 w-4 shrink-0" style={{ background: 'var(--accent)' }} />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )
    case 'quote':
      return (
        <blockquote
          className="my-9 border-l-2 pl-6 text-[18px] font-medium leading-relaxed tracking-[-0.01em]"
          style={{ borderColor: 'var(--accent)' }}
        >
          {block.text}
        </blockquote>
      )
    case 'note':
      return (
        <aside
          className="r-md my-7 p-5 text-[14.5px] leading-relaxed"
          style={{ background: 'var(--panel)', border: '1px solid var(--panel-edge)', color: 'var(--ink-soft)' }}
        >
          {block.text}
        </aside>
      )
    default:
      return (
        <p className="my-5 text-[16.5px] leading-[1.72]" style={{ color: 'var(--ink-soft)' }}>
          {block.text}
        </p>
      )
  }
}

export default function NotePost() {
  const { slug } = useParams()
  const post = getPost(slug)

  useEffect(() => { window.scrollTo(0, 0) }, [slug])

  useEffect(() => {
    if (!post) return
    const previous = document.title
    document.title = `${post.title} — NexaDesk`
    let meta = document.querySelector('meta[name="description"]')
    const hadMeta = Boolean(meta)
    const previousDesc = meta?.getAttribute('content')
    if (!meta) {
      meta = document.createElement('meta')
      meta.setAttribute('name', 'description')
      document.head.appendChild(meta)
    }
    meta.setAttribute('content', post.dek)
    return () => {
      document.title = previous
      if (hadMeta && previousDesc != null) meta.setAttribute('content', previousDesc)
      else if (!hadMeta) meta.remove()
    }
  }, [post])

  if (!post) return <Navigate to="/notes" replace />

  const others = POSTS.filter(p => p.slug !== post.slug).slice(0, 2)

  return (
    <div className="flight-field relative min-h-screen font-sans antialiased">
      <article className="relative z-10 mx-auto max-w-[42rem] px-6 py-14">
        <Link
          to="/notes"
          className="inline-flex items-center gap-2 text-[13.5px] transition-opacity hover:opacity-70"
          style={{ color: 'var(--ink-mute)' }}
        >
          <ArrowLeft className="h-4 w-4" /> Engineering notes
        </Link>

        <header className="mt-12 mb-10">
          <p className="font-mono text-[11.5px] uppercase tracking-wider" style={{ color: 'var(--ink-mute)' }}>
            {new Date(post.date).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}
            {' · '}{post.readingMinutes} min read
          </p>
          <h1 className="mt-4 text-[clamp(1.95rem,4.6vw,2.7rem)] font-semibold leading-[1.1] tracking-[-0.03em]">
            {post.title}
          </h1>
          <p className="mt-5 text-[17.5px] leading-relaxed" style={{ color: 'var(--ink-soft)' }}>
            {post.dek}
          </p>
        </header>

        <div style={{ borderTop: '1px solid var(--hairline)' }} className="pt-2">
          {post.body.map((block, i) => <Block key={i} block={block} />)}
        </div>

        <div
          className="r-lg mt-16 p-7"
          style={{ background: 'var(--panel)', border: '1px solid var(--panel-edge)' }}
        >
          <p className="text-[15.5px] font-medium">This is the system described above, running.</p>
          <p className="mt-1.5 text-[14px]" style={{ color: 'var(--ink-soft)' }}>
            Dial it and ask it how it works — it will tell you.
          </p>
          <a
            href={`tel:${PHONE_E164}`}
            className="mt-5 inline-flex items-center gap-2.5 rounded-full px-5 py-3 text-[15.5px] font-semibold text-white transition-transform duration-[var(--motion-base)] ease-[var(--ease-out)] hover:-translate-y-0.5"
            style={{ background: 'var(--accent-cta)' }}
          >
            <Phone className="h-4 w-4" />
            {PHONE_DISPLAY}
          </a>
        </div>

        {others.length > 0 && (
          <nav className="mt-16 border-t pt-8" style={{ borderColor: 'var(--hairline)' }}>
            <p className="mb-5 text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--accent)' }}>
              Keep reading
            </p>
            <div className="flex flex-col gap-5">
              {others.map(o => (
                <Link key={o.slug} to={`/notes/${o.slug}`} className="group">
                  <p className="text-[16px] font-medium leading-snug tracking-[-0.015em] transition-opacity group-hover:opacity-70">
                    {o.title}
                  </p>
                  <p className="mt-1 font-mono text-[11.5px] uppercase tracking-wider" style={{ color: 'var(--ink-mute)' }}>
                    {o.tags.slice(0, 3).join(' · ')}
                  </p>
                </Link>
              ))}
            </div>
          </nav>
        )}
      </article>
    </div>
  )
}
