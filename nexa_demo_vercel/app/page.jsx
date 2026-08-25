import dynamic from 'next/dynamic'

const VoiceWidget = dynamic(() => import('@/components/VoiceWidget'), { ssr: false })
const ChatWidget  = dynamic(() => import('@/components/ChatWidget'),  { ssr: false })

export default function Page() {
  return (
    <main className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-accent text-white px-6 py-4 flex items-center justify-between shadow-md">
        <div>
          <h1 className="text-xl font-bold tracking-tight">NexaDesk</h1>
          <p className="text-blue-200 text-xs">AI Property Receptionist</p>
        </div>
        <span className="text-xs bg-blue-800 text-blue-100 px-2.5 py-1 rounded-full">Live Demo</span>
      </header>

      {/* Hero */}
      <section className="bg-white border-b border-gray-100 px-6 py-8 text-center">
        <p className="text-sm text-accent font-semibold uppercase tracking-widest mb-2">Powered by AI</p>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Talk to Nexa — your 24/7 property advisor</h2>
        <p className="text-gray-500 text-sm max-w-lg mx-auto">
          Ask about any property, prices, the market in the US, UK or UAE, or how the
          system itself works. Nexa answers in English.
        </p>
      </section>

      {/* Widgets */}
      <section className="flex-1 px-4 py-8 max-w-4xl mx-auto w-full">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Voice */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 flex flex-col">
            <div className="flex items-center gap-2 mb-5">
              <span className="text-2xl">🎙️</span>
              <div>
                <h3 className="font-semibold text-gray-900">Voice Demo</h3>
                <p className="text-xs text-gray-400">Click mic → speak → hear reply</p>
              </div>
            </div>
            <VoiceWidget />
          </div>

          {/* Chat */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 flex flex-col" style={{ minHeight: '480px' }}>
            <div className="flex items-center gap-2 mb-4">
              <span className="text-2xl">💬</span>
              <div>
                <h3 className="font-semibold text-gray-900">Chat Demo</h3>
                <p className="text-xs text-gray-400">Type a question</p>
              </div>
            </div>
            <div className="flex-1">
              <ChatWidget />
            </div>
          </div>
        </div>

        {/* Feature pills */}
        <div className="flex flex-wrap justify-center gap-2 mt-8">
          {[
            '🇦🇪 UAE Properties', '🇬🇧 UK Properties', '🇺🇸 US Properties',
            '💬 Grounded Answers', '📞 Real Phone Line', '🔎 RAG Retrieval',
          ].map(f => (
            <span key={f} className="text-xs bg-white border border-gray-200 text-gray-600 px-3 py-1.5 rounded-full shadow-sm">
              {f}
            </span>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="text-center py-5 text-xs text-gray-400 border-t border-gray-100">
        Pinnacle Property Management — demo powered by NexaDesk AI
      </footer>
    </main>
  )
}
