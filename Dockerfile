# Render deploy target. Mirrors nixpacks.toml (the Railway build config) so
# behavior doesn't drift between the two: same Python version, same ffmpeg
# dependency (app/voice/tts.py needs it to decode ElevenLabs MP3 output into
# 8kHz mulaw for Twilio), same tiktoken cache bake so the first request that
# tokenises text doesn't lazily fetch the BPE file and risk a cold-start
# crash if that fetch blips.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    TIKTOKEN_CACHE_DIR=/app/.tiktoken_cache

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Bake the tiktoken encoding into the image at build time, not first request.
RUN python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"

COPY . .

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
