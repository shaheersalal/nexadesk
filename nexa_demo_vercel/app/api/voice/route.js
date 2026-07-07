import OpenAI from 'openai'
import { VOICE_SYSTEM, WHISPER_PROMPTS, LANG_INSTRUCTIONS } from '@/lib/demoPrompt'

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
    const formData = await request.formData()
    const audioFile = formData.get('audio')
    const lang      = formData.get('lang') || 'en'
    const history   = JSON.parse(formData.get('history') || '[]')

    if (!audioFile) {
      return Response.json({ error: 'No audio' }, { status: 400, headers: CORS })
    }

    const ext = audioFile.type?.includes('mp4') || audioFile.type?.includes('m4a') ? 'm4a'
              : audioFile.type?.includes('ogg') ? 'ogg'
              : 'webm'
    const namedFile = new File([audioFile], `audio.${ext}`, { type: audioFile.type })

    // ── STT ──────────────────────────────────────────────────────────────────
    const sttParams = { model: 'whisper-1', file: namedFile }
    if (lang && lang !== 'auto') {
      sttParams.language = lang
      // Native-script prompt forces Whisper to output Arabic/Nastaliq instead of
      // Latin transliteration (Roman Urdu / Roman Arabic).
      if (WHISPER_PROMPTS[lang]) sttParams.prompt = WHISPER_PROMPTS[lang]
    }

    const transcription = await openai.audio.transcriptions.create(sttParams)
    const transcript = transcription.text?.trim()

    if (!transcript) {
      return Response.json({ error: "Didn't catch that — try again." }, { status: 422, headers: CORS })
    }

    // ── LLM ──────────────────────────────────────────────────────────────────
    // Write the language instruction IN the target language (not in English) so
    // gpt-4o-mini follows it even after a long English system prompt.
    const langInstruction = LANG_INSTRUCTIONS[lang]
    const userContent = langInstruction
      ? `[${langInstruction}]\n\n${transcript}`
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
      return Response.json({ error: 'No response — try again.' }, { status: 500, headers: CORS })
    }

    // ── TTS ──────────────────────────────────────────────────────────────────
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
      historyUser:      transcript,
      historyAssistant: reply,
      audio: audioBuffer.toString('base64'),
    }, { headers: CORS })
  } catch (err) {
    console.error('Voice error:', err)
    return Response.json({ error: 'Something went wrong — try again.' }, { status: 500, headers: CORS })
  }
}
