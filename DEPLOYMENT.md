# Deploying NexaDesk

NexaDesk runs as a **single Railway service** plus two managed data stores.
Nothing is self-hosted; there is no Docker, no Cloudflare Tunnel, and no
dependency on any machine staying awake.

```
nexadesk.site          → Vercel        (dashboard SPA, React + Vite)
api.nexadesk.site      → Railway       (FastAPI, this repo)
                         Qdrant Cloud  (vector search)
                         Upstash Redis (call/session state)
                         Supabase      (Postgres + auth + file storage)
```

## One-time setup

### 1. Qdrant Cloud

Create a free cluster (1 GB is ample — the knowledge base is text chunks) at
<https://cloud.qdrant.io>. Copy the cluster URL and an API key.

```
QDRANT_URL=https://xxxx.aws.cloud.qdrant.io:6333
QDRANT_API_KEY=...
```

`app/dependencies.py:35-48` already branches on `QDRANT_URL`, so no code change
is needed. Leave `QDRANT_URL` empty to fall back to `QDRANT_HOST`/`QDRANT_PORT`
for local development.

The collection is created automatically on first boot by `ensure_collection()`.

### 2. Upstash Redis

Create a free database at <https://upstash.com>. Copy the **TLS** connection
string — the scheme must be `rediss://`, not `redis://`:

```
REDIS_URL=rediss://default:<password>@<endpoint>.upstash.io:6379
```

### 3. Railway

```bash
railway login
railway init            # or: railway link   (to attach to an existing project)
railway up
```

Set every variable from `.env.example` in the Railway dashboard
(Variables → Raw Editor makes bulk paste easy). **`APP_ENV=production` is
mandatory** — several security guards in `app/main.py` are gated on it and are
inert otherwise.

Railway injects `$PORT`; `railway.json` already binds uvicorn to it. Do not
hardcode 8000.

### 4. Custom domain

Add `api.nexadesk.site` under Railway → Settings → Networking, then create the
CNAME it gives you in Namecheap DNS. Update `APP_BASE_URL` and
`TELEPHONY_WEBHOOK_BASE_URL` to match.

## Build configuration

| File | Purpose |
|---|---|
| `railway.json` | start command, `/health` healthcheck, restart policy |
| `nixpacks.toml` | Python 3.12 + ffmpeg, tiktoken cache baked at build time |
| `requirements.txt` | pinned; see the comments — loose pins previously made the tree unresolvable |

Workers are set to **2** in `railway.json`, not the 4 the old compose file used.
Railway's smaller instances have less memory, and the webhook retry loop is
per-worker (see `AUDIT.md` H6) — fewer workers means fewer duplicate deliveries
until that is fixed with a lock.

## Local development

No containers required.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Point `QDRANT_URL` and `REDIS_URL` at the same cloud instances as production, or
at a separate free Qdrant cluster / Upstash database if you want isolation.
`APP_ENV=development` locally.

### Testing Twilio voice locally

Twilio must be able to reach your machine, so tunnel it:

```powershell
ngrok http 8000
```

Set `TELEPHONY_WEBHOOK_BASE_URL` to the `https://` ngrok URL and point your
Twilio number's voice webhook at `<ngrok-url>/voice/inbound`. The URL changes
every time ngrok restarts on the free tier — update both places when it does.

`TELEPHONY_AUTH_TOKEN` must be set even locally, or signature validation is
skipped entirely (`AUDIT.md` C3).

## Storage

Uploaded knowledge-base documents go to **Supabase Storage**
(`SUPABASE_STORAGE_BUCKET`, handled in `app/rag/pipeline.py`). Nothing is
written to the container filesystem, which is ephemeral on Railway and is wiped
on every redeploy.

## Dashboard

The dashboard is a separate Vercel project and does **not** deploy from here.
Push to the GitHub `Shaheer` branch and Vercel rebuilds it. Set `VITE_API_URL`
in Vercel to `https://api.nexadesk.site`.

## What replaced what

| Was | Now |
|---|---|
| `Dockerfile` | `nixpacks.toml` |
| `docker-compose.prod.yml` (app) | Railway service |
| `docker-compose.prod.yml` (qdrant) | Qdrant Cloud |
| `docker-compose.prod.yml` (redis) | Upstash Redis |
| Cloudflare Tunnel | Railway's own domain + TLS |
| `render.yaml` | unused, deleted |
| `models/kokoro/` (115 MB) | deleted — nothing imported it |
