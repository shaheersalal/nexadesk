# Self-Hosting NexaDesk (Docker)

This runs the backend on a local machine instead of (or alongside) the Hugging
Face Space, using `docker-compose.prod.yml`. There is no managed always-on
host behind this — if the machine sleeps, reboots, or Docker Desktop restarts,
the stack stops and must be started again manually. The frontend's fallback
behavior (see "What happens when it's down" below) is what keeps the public
site honest in the meantime.

## Start it up

```
docker compose -f docker-compose.prod.yml up -d --build
```

First run builds the image (a few minutes). After that, `up -d` (no
`--build`) is enough unless backend code changed.

Verify it's healthy:

```
docker compose -f docker-compose.prod.yml ps
curl http://localhost:8000/docs
```

All three services (`app`, `qdrant`, `redis`) should show `Up`/`healthy`.
`app` runs 4 uvicorn workers and takes a few seconds after `Started` before
all of them report `Application startup complete`.

## After a reboot / sleep / Docker Desktop restart

Docker Desktop does not auto-resume containers after a full reboot unless
it's configured to start on login *and* "Resume containers on startup" is on
in Settings → General. Don't rely on that — just re-run:

```
docker compose -f docker-compose.prod.yml up -d
```

This is idempotent: qdrant/redis data persists in named volumes
(`qdrant_data`, `redis_data`), so the knowledge base and chat history survive
restarts. No flags needed unless the image itself changed.

## Stopping it

```
docker compose -f docker-compose.prod.yml down
```

Add `-v` only if you want to wipe the Qdrant/Redis volumes too (destroys the
ingested knowledge base — don't do this casually).

## What happens when it's down

The dashboard, chat widget, voice demo, and login all use short (~5s)
timeouts and fail to a generic "try again shortly" message — none of them
reveal that the backend is offline, and none of them silently retry forever.
The landing-page demo chat additionally has a canned scripted fallback so it
keeps responding plausibly even with the backend down. The demo/signup form
writes to `localStorage` immediately on submit and falls back to an
independent Vercel serverless function (`dashboard/api/capture-lead.js`,
calls Resend directly) if the FastAPI `/book-demo` call fails — so leads are
still captured even during an outage.

## Troubleshooting notes (from getting this working)

These were real bugs hit while validating this compose file — already fixed
in this repo, kept here in case something regresses:

- **Qdrant healthcheck**: `qdrant/qdrant:latest` ships no `curl`, so a
  curl-based healthcheck never passes, and `app`'s
  `depends_on: condition: service_healthy` then blocks forever. Fixed with a
  bash `/dev/tcp` check instead.
- **tiktoken startup crash**: `tiktoken.get_encoding()` lazy-downloads its BPE
  file from `openaipublic.blob.core.windows.net` on first use. A transient
  DNS blip there crashes the whole container at startup. Fixed by pre-warming
  the tiktoken cache at image build time (see `Dockerfile`), so startup never
  depends on that host being reachable.
- **`QDRANT_HOST`/`REDIS_URL` pointing at `localhost`**: the shared `.env`
  file is written for host-machine development (`localhost` + Docker
  Desktop's host-mapped ports). Inside this compose network, `app` must
  reach `qdrant`/`redis` by their service name on their *internal* port
  instead. Fixed via an `environment:` override block in the `app` service
  in `docker-compose.prod.yml` (which takes precedence over `env_file` for
  the same keys) — `.env` itself was left untouched since it's still correct
  for local/dev use.
- **Qdrant collection-create race under `--workers 4`**: all four uvicorn
  worker processes run the startup `ensure_collection` check concurrently;
  whichever loses the create-collection race got an unhandled 409 and
  crashed that worker. Fixed in `app/dependencies.py` by treating a 409 on
  `create_collection` as "another worker already made it," not an error.
