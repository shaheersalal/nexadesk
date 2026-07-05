import './globals.css'

export const metadata = {
  title: 'NexaDesk — AI Property Receptionist Demo',
  description: 'Try Nexa: an AI receptionist that answers property enquiries by voice and chat — 24/7, in any language.',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 min-h-screen text-gray-900 antialiased">{children}</body>
    </html>
  )
}
