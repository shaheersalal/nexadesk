import OpenAI from 'openai'
import { CHAT_SYSTEM } from '@/lib/demoPrompt'

export const maxDuration = 30

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
}

export async function OPTIONS() {
  return new Response(null, { status: 204, headers: CORS })
}

export async function POST(request) {
  const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY })
  try {
    const { messages } = await request.json()

    if (!messages?.length) {
      return Response.json({ error: 'No messages' }, { status: 400, headers: CORS })
    }

    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: [{ role: 'system', content: CHAT_SYSTEM }, ...messages.slice(-20)],
      max_tokens: 250,
      temperature: 0.6,
    })

    return Response.json({ response: completion.choices[0].message.content }, { headers: CORS })
  } catch (err) {
    console.error('Chat error:', err)
    return Response.json({ error: 'Something went wrong' }, { status: 500, headers: CORS })
  }
}
