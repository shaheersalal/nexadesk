import { Link } from 'react-router-dom'
import { Phone, MessageSquare, TrendingUp, Building2, CheckCircle, ArrowRight, Clock, Globe, Linkedin, Info } from 'lucide-react'

const FEATURES = [
  {
    icon: Phone,
    title: 'AI Voice Receptionist',
    desc: 'Answers every inbound call 24/7. Qualifies the client, captures contact details, and understands property interest — all without a human.',
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
  { n: '01', title: 'A client calls or messages', desc: 'Your AI phone number or chat widget receives the inquiry at any hour.' },
  { n: '02', title: 'AI handles the conversation', desc: 'Greets professionally, asks qualifying questions, answers property FAQs from your knowledge base.' },
  { n: '03', title: 'Client appears in your dashboard', desc: 'Full transcript, score, contact details, and AI summary — ready for you to follow up.' },
]

export default function Landing() {
  return (
    <div className="min-h-screen bg-white font-sans">

      {/* Nav */}
      <nav className="fixed top-0 inset-x-0 z-50 bg-white/90 backdrop-blur border-b border-gray-100">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-navy-600 rounded-lg flex items-center justify-center">
              <Phone className="w-4 h-4 text-accent" />
            </div>
            <span className="font-semibold text-gray-900 text-lg">NexaDesk</span>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/login" className="text-sm text-gray-600 hover:text-gray-900 font-medium px-4 py-2">
              Log in
            </Link>
            <Link to="/login?mode=signup" className="text-sm bg-navy-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-navy-700 transition-colors">
              Get Started Free
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-32 pb-20 px-6 bg-gradient-to-b from-navy-600 to-navy-700">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 bg-white/10 text-accent text-xs font-medium px-3 py-1.5 rounded-full mb-6">
            <Clock className="w-3 h-3" />
            Your AI answers. You close deals.
          </div>
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-white leading-tight mb-6">
            Never Miss a Client.<br />
            <span className="text-accent">Your AI Receptionist</span><br />
            Works 24/7.
          </h1>
          <p className="text-lg text-white/70 max-w-2xl mx-auto mb-10 leading-relaxed">
            NexaDesk answers every call and chat, qualifies buyers and tenants, and logs everything to your dashboard — so you close more deals without hiring more staff.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link to="/login?mode=signup"
              className="inline-flex items-center justify-center gap-2 bg-accent text-white font-semibold px-8 py-3.5 rounded-xl hover:bg-accent-dark transition-colors text-sm">
              Start Free Trial <ArrowRight className="w-4 h-4" />
            </Link>
            <Link to="/login"
              className="inline-flex items-center justify-center gap-2 bg-white/10 text-white font-medium px-8 py-3.5 rounded-xl hover:bg-white/20 transition-colors text-sm border border-white/20">
              Sign in
            </Link>
          </div>
        </div>

        {/* Dashboard preview */}
        <div className="max-w-5xl mx-auto mt-16 rounded-2xl overflow-hidden shadow-2xl border border-white/10">
          <div className="bg-navy-800 px-4 py-2.5 flex items-center gap-2">
            <div className="flex gap-1.5">
              <span className="w-3 h-3 rounded-full bg-red-400/60" />
              <span className="w-3 h-3 rounded-full bg-yellow-400/60" />
              <span className="w-3 h-3 rounded-full bg-green-400/60" />
            </div>
            <span className="text-white/30 text-xs ml-2">nexadesk.vercel.app — Dashboard</span>
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
      </section>

      {/* Stats bar */}
      <section className="bg-accent py-5 px-6">
        <div className="max-w-4xl mx-auto flex flex-col sm:flex-row items-center justify-center gap-8 text-white text-sm font-medium">
          {[
            [Clock, '24/7 AI Coverage'],
            [Globe, '10+ Languages Supported'],
            [CheckCircle, 'No Technical Setup Needed'],
          ].map(([Icon, label]) => (
            <div key={label} className="flex items-center gap-2">
              <Icon className="w-4 h-4" /> {label}
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="py-20 px-6 bg-gray-50">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl font-bold text-gray-900">How it works</h2>
            <p className="text-gray-500 mt-3">From first ring to qualified client — fully automated.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {STEPS.map(s => (
              <div key={s.n} className="relative">
                <span className="text-6xl font-black text-gray-100 select-none">{s.n}</span>
                <div className="-mt-6">
                  <h3 className="font-semibold text-gray-900 text-lg mb-2">{s.title}</h3>
                  <p className="text-gray-500 text-sm leading-relaxed">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl font-bold text-gray-900">Everything your agency needs</h2>
            <p className="text-gray-500 mt-3">One platform. No extra staff. No missed opportunities.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {FEATURES.map(f => (
              <div key={f.title} className="p-6 rounded-2xl border border-gray-100 hover:border-accent/40 hover:shadow-md transition-all group">
                <div className="w-10 h-10 bg-accent/10 rounded-xl flex items-center justify-center mb-4 group-hover:bg-accent/20 transition-colors">
                  <f.icon className="w-5 h-5 text-accent" />
                </div>
                <h3 className="font-semibold text-gray-900 mb-2">{f.title}</h3>
                <p className="text-gray-500 text-sm leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="py-20 px-6 bg-gray-50">
        <div className="max-w-md mx-auto text-center">
          <h2 className="text-3xl font-bold text-gray-900 mb-3">Simple pricing</h2>
          <p className="text-gray-500 mb-10">One plan. Everything included. Cancel anytime.</p>
          <div className="bg-white rounded-2xl border border-gray-200 p-8 shadow-sm">
            <p className="text-4xl font-black text-gray-900">499 <span className="text-lg font-normal text-gray-400">AED/mo</span></p>
            <p className="text-gray-400 text-sm mt-1 mb-6">~$136 USD · includes 300 minutes</p>
            <ul className="space-y-3 text-sm text-gray-600 text-left mb-8">
              {[
                'Dedicated AI phone number',
                'Unlimited chat conversations',
                'Client scoring & CRM dashboard',
                'Property knowledge base',
                'Full call transcripts',
                'WhatsApp & website widget',
              ].map(item => (
                <li key={item} className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
                  {item}
                </li>
              ))}
            </ul>

            <Link to="/login?mode=signup"
              className="block w-full text-center bg-navy-600 text-white font-semibold py-3 rounded-xl hover:bg-navy-700 transition-colors">
              Get Started Free
            </Link>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-6 bg-navy-600">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-3xl font-bold text-white mb-4">Ready to stop missing clients?</h2>
          <p className="text-white/60 mb-8">Set up in under 10 minutes. Your AI receptionist starts taking calls today.</p>
          <Link to="/login?mode=signup"
            className="inline-flex items-center gap-2 bg-accent text-white font-semibold px-10 py-4 rounded-xl hover:bg-accent-dark transition-colors">
            Start Free Trial <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-navy-900 py-10 px-6">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2 text-xs text-white/30">
            <Phone className="w-3.5 h-3.5 text-accent" />
            <span className="text-white/50 font-medium">NexaDesk</span>
            <span>— AI Receptionist for Real Estate</span>
          </div>

          {/* LinkedIn founder link */}
          <a
            href="https://www.linkedin.com/in/shaheer-salal/"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2.5 px-4 py-2 rounded-lg border border-white/10 text-white/50 hover:text-white hover:border-white/30 transition-colors group"
          >
            <Linkedin className="w-4 h-4 text-[#0A66C2] group-hover:scale-110 transition-transform" />
            <div className="text-left">
              <p className="text-xs font-medium leading-tight">Built by Shaheer Salal</p>
              <p className="text-[10px] text-white/30 leading-tight">Questions? Let's connect</p>
            </div>
          </a>

          <div className="flex gap-6 text-xs text-white/30">
            <Link to="/login" className="hover:text-white/60 transition-colors">Log in</Link>
            <Link to="/login?mode=signup" className="hover:text-white/60 transition-colors">Sign up</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
