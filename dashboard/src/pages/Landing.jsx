import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import {
  Phone, MessageSquare, TrendingUp, Building2, CheckCircle, ArrowRight, Clock, Globe,
  Linkedin, Briefcase, Wrench, RefreshCw, ShoppingBag, ChevronDown, Lock, Tag,
  Database, Puzzle, Code2,
} from 'lucide-react'
import DemoPreviewModal from '../components/DemoPreviewModal'
import PricingCalculator from '../components/PricingCalculator'
import DiscountChat from '../components/DiscountChat'
import Reveal from '../components/Reveal'

const UPWORK_URL = 'https://www.upwork.com/freelancers/shaheersalal'
const LINKEDIN_URL = 'https://www.linkedin.com/in/shaheer-salal/'

const SERVICES = [
  { icon: Phone, title: 'AI Voice Agents', desc: 'Automated receptionists and call handling for businesses.' },
  { icon: Database, title: 'RAG / Knowledge Platforms', desc: 'AI search tools trained on your documents.' },
  { icon: Puzzle, title: 'AI Integration', desc: 'Adding ChatGPT/Claude-type features into existing apps and websites.' },
  { icon: Code2, title: 'Backend Development', desc: 'FastAPI/Python systems, APIs, and automation.' },
]

const FEATURES = [
  {
    icon: Phone,
    title: 'AI Voice Receptionist',
    desc: 'Answers every inbound call 24/7. Qualifies the client, captures contact details, and understands property interest, all without a human.',
  },
  {
    icon: MessageSquare,
    title: 'Instant Chat Widget',
    desc: 'Embed on your website or WhatsApp. The AI answers property FAQs, qualifies buyers, and hands off hot clients to you immediately.',
  },
  {
    icon: TrendingUp,
    title: 'Smart Client Scoring',
    desc: 'Every client gets a score based on budget, timeline, and intent. Your hottest prospects surface to the top automatically.',
  },
  {
    icon: Building2,
    title: 'Property Knowledge Base',
    desc: 'Upload listings, brochures, or paste descriptions. The AI knows your inventory and answers specific questions about each property.',
  },
]

const STEPS = [
  { n: '01', title: 'See it in action', desc: 'Tour the live dashboard, lead pipeline, and AI conversations, no sign-up needed. Then request access in 60 seconds.' },
  { n: '02', title: 'We set everything up', desc: 'We configure your AI phone number, upload your knowledge base, and connect the chat widget to your website, fully handled.' },
  { n: '03', title: 'You start closing deals', desc: 'Every call and chat is handled, qualified, and logged. Open your dashboard and follow up on only the hottest leads.' },
]

const SHOWCASE = [
  {
    icon: ShoppingBag,
    color: 'text-accent bg-accent/10',
    title: 'Buyer Inquiry',
    channel: 'Voice call',
    sample: '"Hi, I\'m looking for a 2-bedroom near downtown, budget around $400K, is anything available?"',
    outcome: 'Qualified, scored 82, follow-up call booked for tomorrow.',
  },
  {
    icon: RefreshCw,
    color: 'text-purple-500 bg-purple-50',
    title: 'Lease Renewal',
    channel: 'Website chat',
    sample: '"My lease is up next month, can I renew at the same rate?"',
    outcome: 'Logged as lease renewal, routed to property manager.',
  },
  {
    icon: Wrench,
    color: 'text-orange-500 bg-orange-50',
    title: 'Maintenance Request',
    channel: 'WhatsApp',
    sample: '"The AC in unit 4B stopped working, it\'s pretty urgent."',
    outcome: 'Flagged urgent, ticket created, tenant notified of next steps.',
  },
]

const FAQS = [
  {
    q: 'How fast can NexaDesk go live?',
    a: 'Most agencies are live within 48 hours of signing up. We handle the AI phone number setup, knowledge base ingestion, and widget install, you don\'t need to configure anything yourself.',
  },
  {
    q: 'What languages does the AI support?',
    a: 'Speaks your client\'s language, automatically. From Arabic to Spanish to Urdu and everything in between, NexaDesk detects and replies in whatever language your client uses, on both voice and chat.',
  },
  {
    q: 'Can I change my plan later?',
    a: 'Yes — minutes and seats can be adjusted at any time from your dashboard settings, and your next invoice is prorated automatically.',
  },
  {
    q: 'What happens if I go over my included minutes?',
    a: 'You\'re charged a flat per-minute overage rate shown in your plan breakdown, no surprise fees, no automatic plan upgrades.',
  },
  {
    q: 'Is my client data secure?',
    a: 'All call transcripts and client data are stored on encrypted servers and are never sold or shared with third parties.',
  },
]

const NAV_LINKS = [
  { id: 'hero', label: 'Home' },
  { id: 'demo', label: 'Demo' },
  { id: 'how-it-works', label: 'How it works' },
  { id: 'pricing', label: 'Pricing' },
  { id: 'services', label: 'Services' },
  { id: 'showcase', label: 'Showcase' },
  { id: 'faq', label: 'FAQ' },
]

function scrollToId(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
}

function FaqItem({ item, open, onToggle }) {
  return (
    <div className="border-b border-gray-100 last:border-0">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between gap-4 py-5 text-left"
      >
        <span className="font-medium text-gray-900 text-sm md:text-base">{item.q}</span>
        <ChevronDown className={`w-4 h-4 text-gray-400 flex-shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      <div className={`grid transition-all duration-300 ease-out ${open ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'}`}>
        <div className="overflow-hidden">
          <p className="text-sm text-gray-500 leading-relaxed pb-5">{item.a}</p>
        </div>
      </div>
    </div>
  )
}

export default function Landing() {
  const [demoOpen, setDemoOpen] = useState(false)
  const [offerPlan, setOfferPlan] = useState(null)
  const [openFaq, setOpenFaq] = useState(0)
  const [activeSection, setActiveSection] = useState('hero')

  useEffect(() => {
    const sections = NAV_LINKS.map(l => document.getElementById(l.id)).filter(Boolean)
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter(e => e.isIntersecting)
        if (visible.length > 0) {
          setActiveSection(visible[0].target.id)
        }
      },
      { rootMargin: '-40% 0px -50% 0px' }
    )
    sections.forEach(s => observer.observe(s))
    return () => observer.disconnect()
  }, [])

  return (
    <div className="min-h-screen bg-white font-sans">
      {demoOpen && <DemoPreviewModal onClose={() => setDemoOpen(false)} />}
      {offerPlan && <DiscountChat plan={offerPlan} onClose={() => setOfferPlan(null)} />}

      {/* Nav */}
      <nav className="fixed top-0 inset-x-0 z-40 bg-white/90 backdrop-blur border-b border-gray-100">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <button onClick={() => scrollToId('hero')} className="flex items-center gap-2">
            <div className="w-8 h-8 bg-navy-600 rounded-lg flex items-center justify-center">
              <Phone className="w-4 h-4 text-accent" />
            </div>
            <span className="font-semibold text-gray-900 text-lg">NexaDesk</span>
          </button>

          <div className="hidden lg:flex items-center gap-1">
            {NAV_LINKS.map(l => (
              <button
                key={l.id}
                onClick={() => scrollToId(l.id)}
                className={`text-sm px-3 py-2 rounded-lg font-medium transition-colors ${
                  activeSection === l.id ? 'text-accent' : 'text-gray-500 hover:text-gray-900'
                }`}
              >
                {l.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <Link to="/login" className="text-sm text-gray-600 hover:text-gray-900 font-medium px-4 py-2">
              Log in
            </Link>
            <Link
              to="/login?mode=signup"
              className="text-sm bg-navy-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-navy-700 transition-colors"
            >
              Sign up
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section id="hero" className="pt-32 pb-20 px-6 bg-gradient-to-b from-navy-600 to-navy-700">
        <div className="max-w-4xl mx-auto text-center">
          <p className="text-accent text-sm font-medium tracking-wide mb-4">Your AI answers. You close deals.</p>
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-white leading-tight mb-6">
            Never Miss a Client.<br />
            <span className="text-accent">Your AI Receptionist</span><br />
            Works 24/7.
          </h1>
          <p className="text-lg text-white/70 max-w-2xl mx-auto mb-10 leading-relaxed">
            NexaDesk answers every call and chat, qualifies buyers and tenants, and logs everything to your dashboard — so you close more deals without hiring more staff.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button
              onClick={() => setDemoOpen(true)}
              className="inline-flex items-center justify-center gap-2 bg-accent text-white font-semibold px-8 py-3.5 rounded-xl hover:bg-accent-dark transition-colors text-sm"
            >
              See It in Action <ArrowRight className="w-4 h-4" />
            </button>
            <Link to="/login"
              className="inline-flex items-center justify-center gap-2 bg-white/10 text-white font-medium px-8 py-3.5 rounded-xl hover:bg-white/20 transition-colors text-sm border border-white/20">
              Sign in
            </Link>
          </div>
        </div>

        {/* Dashboard preview — placeholder mockup, swap for a real product screenshot when available */}
        <Reveal delay={150}>
          <div className="max-w-5xl mx-auto mt-16 rounded-2xl overflow-hidden shadow-2xl border border-white/10">
            <div className="bg-navy-800 px-4 py-2.5 flex items-center gap-2">
              <div className="flex gap-1.5">
                <span className="w-3 h-3 rounded-full bg-red-400/60" />
                <span className="w-3 h-3 rounded-full bg-yellow-400/60" />
                <span className="w-3 h-3 rounded-full bg-green-400/60" />
              </div>
              <span className="text-white/30 text-xs ml-2">nexadesk.site — Dashboard</span>
            </div>
            <div className="bg-navy-900 p-6 grid grid-cols-4 gap-4">
              {[['24', 'Total Clients'], ['78', 'Avg Score'], ['5', 'Upcoming'], ['12', 'Conversations']].map(([v, l]) => (
                <div key={l} className="bg-white/5 rounded-xl p-4 border border-white/10">
                  <p className="text-2xl font-bold text-white">{v}</p>
                  <p className="text-xs text-white/40 mt-1">{l}</p>
                </div>
              ))}
            </div>
            <div className="bg-navy-900 px-6 pb-6 grid grid-cols-3 gap-3">
              {[
                ['Ahmed Al-Rashid', 'Buyer Inquiry', '82', 'qualified'],
                ['Sara Khalid', 'Lease Renewal', '67', 'contacted'],
                ['James Miller', 'Maintenance', '45', 'new'],
              ].map(([name, type, score, status]) => (
                <div key={name} className="bg-white/5 rounded-lg p-3 border border-white/10">
                  <p className="text-white text-xs font-medium">{name}</p>
                  <p className="text-white/40 text-xs mt-0.5">{type}</p>
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-accent text-xs font-semibold">Score {score}</span>
                    <span className="text-xs text-white/30 capitalize">{status}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </Reveal>
      </section>

      {/* Stats bar */}
      <section className="bg-accent py-5 px-6">
        <div className="max-w-4xl mx-auto flex flex-col sm:flex-row items-center justify-center gap-8 text-white text-sm font-medium">
          {[
            [Clock, '24/7 AI Coverage'],
            [Globe, "Speaks your client's language — automatically"],
            [CheckCircle, 'Full Setup Included'],
          ].map(([Icon, label]) => (
            <div key={label} className="flex items-center gap-2">
              <Icon className="w-4 h-4" /> {label}
            </div>
          ))}
        </div>
      </section>

      {/* Demo */}
      <section id="demo" className="py-20 px-6 bg-gray-50 scroll-mt-16">
        <Reveal>
          <div className="max-w-2xl mx-auto text-center">
            <h2 className="text-3xl font-bold text-gray-900">See It in Action</h2>
            <p className="text-gray-500 mt-3 mb-10">This is exactly what your clients experience when they contact your agency.</p>
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-10 flex flex-col items-center gap-6">
              <div className="flex gap-3 flex-wrap justify-center">
                {['🎙️ Voice Demo', '💬 Chat Demo', '🌐 Urdu · Arabic · English', '💰 Currency Conversion'].map(f => (
                  <span key={f} className="text-xs bg-gray-50 border border-gray-200 text-gray-600 px-3 py-1.5 rounded-full">{f}</span>
                ))}
              </div>
              <p className="text-gray-500 text-sm max-w-sm">
                Talk or type — ask about any property, Golden Visa, mortgage rates, or investment returns. Nexa responds in your language.
              </p>
              <a
                href="https://nexadesk-1j2y-p5gc1nuno-shaheer-salal-s-projects.vercel.app/"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 bg-accent text-white px-8 py-3 rounded-full font-semibold text-sm hover:opacity-90 transition-opacity"
              >
                Open Live Demo <ArrowRight size={16} />
              </a>
              <p className="text-xs text-gray-400">Opens in a new tab — no sign-up required</p>
            </div>
          </div>
        </Reveal>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="py-20 px-6 scroll-mt-16">
        <div className="max-w-5xl mx-auto">
          <Reveal>
            <div className="text-center mb-14">
              <h2 className="text-3xl font-bold text-gray-900">How it works</h2>
              <p className="text-gray-500 mt-3">From first look to qualified client — we set it all up for you.</p>
            </div>
          </Reveal>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-20">
            {STEPS.map((s, i) => (
              <Reveal key={s.n} delay={i * 100}>
                <div className="relative">
                  <span className="text-6xl font-black text-gray-100 select-none">{s.n}</span>
                  <div className="-mt-6">
                    <h3 className="font-semibold text-gray-900 text-lg mb-2">{s.title}</h3>
                    <p className="text-gray-500 text-sm leading-relaxed">{s.desc}</p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>

          <Reveal>
            <div className="text-center mb-14">
              <h2 className="text-2xl font-bold text-gray-900">Everything your agency needs</h2>
              <p className="text-gray-500 mt-3">One platform. No extra staff. No missed opportunities.</p>
            </div>
          </Reveal>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {FEATURES.map((f, i) => (
              <Reveal key={f.title} delay={i * 80}>
                <div className="p-6 rounded-2xl border border-gray-100 hover:border-accent/40 hover:shadow-md transition-all group h-full">
                  <div className="w-10 h-10 bg-accent/10 rounded-xl flex items-center justify-center mb-4 group-hover:bg-accent/20 transition-colors">
                    <f.icon className="w-5 h-5 text-accent" />
                  </div>
                  <h3 className="font-semibold text-gray-900 mb-2">{f.title}</h3>
                  <p className="text-gray-500 text-sm leading-relaxed">{f.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-20 px-6 bg-gray-50 scroll-mt-16">
        <div className="max-w-4xl mx-auto">
          <Reveal>
            <div className="text-center mb-10">
              <h2 className="text-3xl font-bold text-gray-900 mb-3">Simple, transparent pricing</h2>
              <p className="text-gray-500">Pick a tier or build your own — minutes and seats, nothing hidden.</p>
            </div>
          </Reveal>
          <Reveal delay={100}>
            <PricingCalculator onOffer={setOfferPlan} />
          </Reveal>
          <p className="text-center text-xs text-gray-400 mt-6 flex items-center justify-center gap-1.5">
            <Lock className="w-3 h-3" /> Final pricing is always verified server-side — no contracts, cancel anytime.
          </p>
        </div>
      </section>

      {/* Services */}
      <section id="services" className="py-20 px-6 scroll-mt-16">
        <Reveal>
          <div className="max-w-3xl mx-auto text-center mb-12">
            <div className="w-12 h-12 bg-navy-600 rounded-2xl flex items-center justify-center mx-auto mb-6">
              <Briefcase className="w-5 h-5 text-accent" />
            </div>
            <h2 className="text-3xl font-bold text-gray-900 mb-4">Built and run by an AI engineer</h2>
            <p className="text-gray-500 leading-relaxed">
              NexaDesk is built and operated by Shaheer Salal. Have a custom AI project in mind? Here's what I build:
            </p>
          </div>
        </Reveal>

        <div className="max-w-3xl mx-auto grid grid-cols-1 sm:grid-cols-2 gap-5 mb-10">
          {SERVICES.map((s, i) => (
            <Reveal key={s.title} delay={i * 80}>
              <div className="p-5 rounded-2xl border border-gray-100 hover:border-accent/40 hover:shadow-md transition-all group h-full text-left flex items-start gap-4">
                <div className="w-10 h-10 bg-accent/10 rounded-xl flex items-center justify-center flex-shrink-0 group-hover:bg-accent/20 transition-colors">
                  <s.icon className="w-5 h-5 text-accent" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 mb-1">{s.title}</h3>
                  <p className="text-gray-500 text-sm leading-relaxed">{s.desc}</p>
                </div>
              </div>
            </Reveal>
          ))}
        </div>

        <Reveal>
          <div className="max-w-3xl mx-auto text-center">
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <a
                href={UPWORK_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 bg-[#14a800] text-white font-semibold px-6 py-3 rounded-xl hover:opacity-90 transition-opacity text-sm"
              >
                <Briefcase className="w-4 h-4" /> Hire me on Upwork
              </a>
              <a
                href={LINKEDIN_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 bg-[#0A66C2] text-white font-semibold px-6 py-3 rounded-xl hover:opacity-90 transition-opacity text-sm"
              >
                <Linkedin className="w-4 h-4" /> Connect on LinkedIn
              </a>
            </div>
          </div>
        </Reveal>
      </section>

      {/* Showcase */}
      <section id="showcase" className="py-20 px-6 bg-gray-50 scroll-mt-16">
        <div className="max-w-5xl mx-auto">
          <Reveal>
            <div className="text-center mb-14">
              <h2 className="text-3xl font-bold text-gray-900">What your AI handles every day</h2>
              <p className="text-gray-500 mt-3">Real scenarios NexaDesk qualifies, logs, and routes automatically.</p>
            </div>
          </Reveal>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {SHOWCASE.map((s, i) => (
              <Reveal key={s.title} delay={i * 100}>
                <div className="bg-white rounded-2xl border border-gray-100 p-6 h-full flex flex-col">
                  <div className={`w-9 h-9 rounded-lg flex items-center justify-center mb-4 ${s.color}`}>
                    <s.icon className="w-4.5 h-4.5" />
                  </div>
                  <h3 className="font-semibold text-gray-900 mb-1">{s.title}</h3>
                  <p className="text-xs text-gray-400 mb-4">{s.channel}</p>
                  <p className="text-sm text-gray-600 italic leading-relaxed mb-4 flex-1">{s.sample}</p>
                  <p className="text-xs font-medium text-green-700 bg-green-50 rounded-lg px-3 py-2">{s.outcome}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="py-20 px-6 scroll-mt-16">
        <div className="max-w-2xl mx-auto">
          <Reveal>
            <div className="text-center mb-10">
              <h2 className="text-3xl font-bold text-gray-900">Frequently asked questions</h2>
            </div>
          </Reveal>
          <Reveal delay={100}>
            <div>
              {FAQS.map((item, i) => (
                <FaqItem
                  key={item.q}
                  item={item}
                  open={openFaq === i}
                  onToggle={() => setOpenFaq(openFaq === i ? -1 : i)}
                />
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-6 bg-navy-600">
        <Reveal>
          <div className="max-w-2xl mx-auto text-center">
            <h2 className="text-3xl font-bold text-white mb-4">Ready to stop missing clients?</h2>
            <p className="text-white/60 mb-8">Your AI receptionist can be live within 48 hours, we handle the entire setup.</p>
            <button
              onClick={() => setDemoOpen(true)}
              className="inline-flex items-center gap-2 bg-accent text-white font-semibold px-10 py-4 rounded-xl hover:bg-accent-dark transition-colors"
            >
              See It in Action <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </Reveal>
      </section>

      {/* Privacy Policy placeholder */}
      <section id="privacy" className="py-14 px-6 bg-navy-900 border-t border-white/5 scroll-mt-16">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-lg font-semibold text-white mb-3">Privacy Policy</h2>
          <p className="text-sm text-white/40 leading-relaxed">
            Full policy coming soon. In short: call transcripts and client data are stored on encrypted servers,
            used only to operate your AI receptionist, and never sold or shared with third parties.
            Questions in the meantime? <a href={`mailto:shaheersalal@gmail.com`} className="text-accent hover:underline">Email us</a>.
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-navy-900 py-10 px-6 border-t border-white/5">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2 text-xs text-white/30">
            <Phone className="w-3.5 h-3.5 text-accent" />
            <span className="text-white/50 font-medium">NexaDesk</span>
            <span>— AI Receptionist for Real Estate</span>
          </div>

          <div className="flex gap-6 text-xs text-white/30">
            <button onClick={() => scrollToId('privacy')} className="hover:text-white/60 transition-colors">Privacy</button>
            <Link to="/login" className="hover:text-white/60 transition-colors">Log in</Link>
          </div>
        </div>
        <p className="text-center text-[11px] text-white/20 mt-6 max-w-xl mx-auto">
          All call transcripts and client data stored securely on encrypted servers. Never sold or shared.
        </p>
      </footer>
    </div>
  )
}
