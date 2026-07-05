import OpenAI from 'openai'
import { VOICE_SYSTEM, LANG_NAMES } from '@/lib/demoPrompt'

export const maxDuration = 30

export async function POST(request) {
  const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY })
  try {
    const formData = await request.formData()
    const audioFile = formData.get('audio')   // File/Blob
    const lang      = formData.get('lang') || 'en'
    const history   = JSON.parse(formData.get('history') || '[]')

    if (!audioFile) {
      return Response.json({ error: 'No audio' }, { status: 400 })
    }

    // ── STT ──────────────────────────────────────────────────────────
    // Give the file a proper name so whisper knows the container format.
    const ext = audioFile.type?.includes('mp4') || audioFile.type?.includes('m4a') ? 'm4a'
              : audioFile.type?.includes('ogg') ? 'ogg'
              : 'webm'
    const namedFile = new File([audioFile], `audio.${ext}`, { type: audioFile.type })

    const sttParams = { model: 'whisper-1', file: namedFile }
    if (lang && lang !== 'auto') sttParams.language = lang

    const transcription = await openai.audio.transcriptions.create(sttParams)
    const transcript = transcription.text?.trim()

    if (!transcript) {
      return Response.json({ error: "Didn't catch that — try again." }, { status: 422 })
    }

    // ── LLM ──────────────────────────────────────────────────────────
    // Embed the language instruction directly in the user message — much more
    // reliable than burying it in a long system prompt.
    const langName = LANG_NAMES[lang]
    const userContent = langName
      ? `[Respond in ${langName} only — do not use English]\n\n${transcript}`
      : transcript

    const messages = [
      ...history.slice(-10),
      { role: 'user', content: userContent },
    ]

    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: [{ role: 'system', content: VOICE_SYSTEM }, ...messages],
      max_tokens: 150,
      temperature: 0.5,
    })

    const reply = completion.choices[0].message.content?.trim()
    if (!reply) {
      return Response.json({ error: 'No response — try again.' }, { status: 500 })
    }

    // ── TTS ──────────────────────────────────────────────────────────
    const tts = await openai.audio.speech.create({
      model: 'tts-1',
      voice: 'alloy',
      input: reply,
      response_format: 'mp3',
    })

    const audioBuffer = Buffer.from(await tts.arrayBuffer())

    return Response.json({
      transcript,
      reply,
      // Stored in history without the language prefix so context stays clean
      historyUser:      transcript,
      historyAssistant: reply,
      audio: audioBuffer.toString('base64'),
    })
  } catch (err) {
    console.error('Voice error:', err)
    return Response.json({ error: 'Something went wrong — try again.' }, { status: 500 })
  }
}
