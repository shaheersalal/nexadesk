"""
Generate Deepgram Aura-2 samples so a TTS provider choice can be made by ear.

Each voice is rendered twice:

  *_studio.wav  — 24 kHz, what the web demo plays
  *_phone.wav   — 8 kHz passed through mu-law quantisation, i.e. what a caller
                  on a Twilio line actually hears

The second one is the point. Twilio carries 8 kHz mu-law, band-limited to
roughly 300-3400 Hz, which removes most of the high-frequency detail that
distinguishes premium TTS. Comparing providers on studio audio overstates a
difference the phone network erases. `audioop` does the mu-law round trip in
pure Python, so no ffmpeg is needed.

    python scripts/tts_samples.py [output_dir]
"""
import audioop
import os
import pathlib
import sys
import wave

import httpx

SPEAK_URL = "https://api.deepgram.com/v1/speak"

# A line with the things that actually stress a receptionist voice: a greeting,
# a number, a currency, an abbreviation, and a question intonation.
LINES = {
    "en": "Good afternoon, thanks for calling Pinnacle Property. "
          "We have a two bedroom in Dubai Marina at one point four million dirhams. "
          "Would you like to arrange a viewing this week?",
    "es": "Buenas tardes, gracias por llamar a Pinnacle Property. "
          "Tenemos un apartamento de dos habitaciones en Dubai Marina. "
          "¿Le gustaría concertar una visita esta semana?",
    "fr": "Bonjour et merci d'avoir appelé Pinnacle Property. "
          "Nous avons un deux pièces à Dubai Marina. "
          "Souhaitez-vous organiser une visite cette semaine ?",
}

VOICES = [
    ("aura-2-thalia-en", "en", "warm female, US — Deepgram's default agent voice"),
    ("aura-2-andromeda-en", "en", "calm female, US"),
    ("aura-2-apollo-en", "en", "confident male, US"),
    ("aura-2-helena-en", "en", "friendly female, US"),
    ("aura-2-draco-en", "en", "male, British"),
    ("aura-2-carina-es", "es", "female, Spain"),
    ("aura-2-javier-es", "es", "male, Mexico"),
    ("aura-2-agathe-fr", "fr", "female, France"),
]


def load_env(path=".env"):
    p = pathlib.Path(path)
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def synthesize(key: str, model: str, text: str, sample_rate: int) -> bytes | None:
    """Return raw 16-bit PCM at the requested rate, or None on failure."""
    try:
        r = httpx.post(
            SPEAK_URL,
            params={
                "model": model,
                "encoding": "linear16",
                "sample_rate": str(sample_rate),
                "container": "none",
            },
            headers={"Authorization": f"Token {key}", "Content-Type": "application/json"},
            json={"text": text},
            timeout=60,
        )
    except Exception as exc:
        print(f"    request failed: {type(exc).__name__}: {exc}")
        return None
    if r.status_code != 200:
        print(f"    HTTP {r.status_code}: {r.text[:160]}")
        return None
    return r.content


def write_wav(path: pathlib.Path, pcm: bytes, rate: int) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)


def to_phone(pcm8k: bytes) -> bytes:
    """
    Simulate the telephony path: 16-bit PCM -> mu-law -> back to PCM.

    The round trip is lossy in exactly the way Twilio's codec is, so the result
    sounds like the call rather than like the studio render.
    """
    ulaw = audioop.lin2ulaw(pcm8k, 2)
    return audioop.ulaw2lin(ulaw, 2)


def main() -> int:
    load_env()
    key = os.environ.get("STT_API_KEY", "")
    if not key:
        print("STT_API_KEY not set (Deepgram key lives there)")
        return 1

    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "tts_samples")
    out.mkdir(parents=True, exist_ok=True)

    made = 0
    for model, lang, description in VOICES:
        text = LINES[lang]
        print(f"\n{model}  ({description})")

        studio = synthesize(key, model, text, 24000)
        if studio:
            write_wav(out / f"{model}_studio.wav", studio, 24000)
            print(f"    studio  {len(studio)/48000:5.1f}s  {model}_studio.wav")
            made += 1

        narrow = synthesize(key, model, text, 8000)
        if narrow:
            write_wav(out / f"{model}_phone.wav", to_phone(narrow), 8000)
            print(f"    phone   {len(narrow)/16000:5.1f}s  {model}_phone.wav")
            made += 1

    print(f"\n{made} file(s) in {out.resolve()}")
    print("Listen to the _phone pair first — that is what callers actually hear.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
