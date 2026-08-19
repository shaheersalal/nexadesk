"""
End-to-end test of POST /demo/voice against a deployed instance.

Uploads a real speech clip and reports what each stage produced, so it is
obvious which provider is doing work and which is silently returning nothing.

    python scripts/test_demo_voice.py [base_url] [wav_path]
"""
import pathlib
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://nexadesk-api-production.up.railway.app"
CLIP = pathlib.Path(sys.argv[2] if len(sys.argv) > 2
                    else "tts_samples/aura-2-thalia-en_studio.wav")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def main() -> int:
    if not CLIP.is_file():
        print(f"clip not found: {CLIP}")
        return 1

    audio = CLIP.read_bytes()
    print(f"POST {BASE}/demo/voice")
    print(f"  clip: {CLIP.name}  ({len(audio)/1024:.0f} KB)\n")

    try:
        r = httpx.post(
            f"{BASE}/demo/voice",
            headers={"User-Agent": UA},
            files={"audio": (CLIP.name, audio, "audio/wav")},
            data={"lang": "en", "history": "[]"},
            timeout=120,
        )
    except Exception as exc:
        print(f"request failed: {type(exc).__name__}: {exc}")
        return 1

    print(f"HTTP {r.status_code}")
    if r.status_code != 200:
        print(r.text[:400])
        return 1

    d = r.json()
    transcript = d.get("transcript") or ""
    reply = d.get("reply") or ""
    audio_b64 = d.get("audio") or ""

    print(f"\n  STT  (Deepgram)   {'OK' if transcript else 'EMPTY'}")
    print(f"       heard: {transcript[:150]!r}")
    print(f"\n  LLM  (gpt-4o-mini) {'OK' if reply else 'EMPTY'}")
    print(f"       said:  {reply[:150]!r}")
    print(f"\n  TTS  (ElevenLabs)  {'OK — ' + str(len(audio_b64)) + ' b64 chars' if audio_b64 else 'EMPTY — no audio returned'}")

    if transcript and reply and not audio_b64:
        print("\n  => speech-in and reasoning work; speech-out is not configured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
