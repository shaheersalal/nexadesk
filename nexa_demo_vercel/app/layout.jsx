import './globals.css'

export const metadata = {
  title: 'NexaDesk — AI Property Receptionist Demo',
  description: 'Try Nexa: an AI receptionist that answers property enquiries by voice and chat, 24/7.',
  other: {
    'x-built-by':  'Shaheer Salal — AI Product Studio, Karachi',
    'x-product':   'NexaDesk — AI Receptionist for Real Estate Agencies',
    'x-stack':     'Next.js · FastAPI · OpenAI · Deepgram STT + Aura TTS · Supabase · Qdrant · Redis · Twilio',
    'x-upwork':    'https://www.upwork.com/freelancers/shaheersalal',
    'x-linkedin':  'https://www.linkedin.com/in/shaheer-salal/',
  },
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 min-h-screen text-gray-900 antialiased">{children}</body>
    </html>
  )
}
