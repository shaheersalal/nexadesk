# NexaDesk — AI Receptionist for Real Estate

> 24/7 AI receptionist that handles inbound property enquiries via voice and chat. Qualifies leads, answers FAQs, and books viewings — without a human.

## What It Does

- **Voice calls** — answers inbound calls, understands the caller, qualifies interest (budget, timeline, property type)
- **RAG-powered FAQs** — answers property-specific questions from the agency's knowledge base
- **Lead capture** — extracts and stores lead details automatically into a CRM-style dashboard
- **Viewing bookings** — integrates with Google Calendar to schedule appointments
- **Multi-language** — supports English, Arabic, Urdu, French, Spanish
- **Admin dashboard** — manage properties, review leads, upload knowledge base documents

## Architecture

```mermaid
flowchart TD
    A([📞 Inbound Call / 💬 Web Chat]) --> B[Nginx\nReverse Proxy + TLS]
    B --> C[FastAPI Backend]

    C --> D{Request Type}

    D -->|Voice call| E[Twilio Webhook]
    E --> F[Deepgram STT\nSpeech → Text]
    F --> G[RAG Engine]
    G --> H[Qdrant\nVector Search]
    H --> I[Claude LLM\nAnswer Generation]
    I --> J[ElevenLabs TTS\nText → Speech]
    J --> E

    D -->|Chat message| G

    D -->|Lead captured| K[PostgreSQL\nSupabase]
    D -->|Viewing request| L[Google Calendar API]

    subgraph Data Layer
        H
        K
        M[Redis Cache]
        N[MinIO\nDocument Storage]
    end

    subgraph AI Layer
        F
        G
        I
        O[OpenAI Embeddings]
    end

    G --> O
    O --> H
    C --> M
```

<details>
<summary>Text diagram</summary>

```
Browser / Phone Call
        ↓
    Nginx (reverse proxy + TLS)
        ↓
    FastAPI (Python)
     ├── /voice      ← Twilio webhook handler, STT, TTS
     ├── /chat       ← WebSocket chat endpoint
     ├── /leads      ← Lead capture + Google Calendar
     ├── /properties ← Property listings management
     ├── /rag        ← Document ingestion + vector search
     └── /auth       ← JWT authentication
        ↓
   ┌────────────────────────────────┐
   │  Claude (LLM)                  │
   │  Deepgram (Speech-to-Text)     │
   │  ElevenLabs (Text-to-Speech)   │
   │  OpenAI Embeddings             │
   └────────────────────────────────┘
        ↓
   ┌──────────────────┐
   │  Qdrant (vectors)│
   │  Supabase (DB)   │
   │  Redis (cache)   │
   └──────────────────┘
```

</details>

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python |
| LLM | Anthropic Claude |
| Voice STT | Deepgram nova-2 |
| Voice TTS | ElevenLabs |
| Embeddings | OpenAI text-embedding-3-small |
| Vector DB | Qdrant |
| Database | Supabase (PostgreSQL) |
| Cache | Redis |
| Telephony | Twilio |
| Calendar | Google Calendar API |
| Frontend | React, Tailwind CSS, Vite |
| Infrastructure | Docker, Nginx |

## Setup

```bash
cp .env.example .env
# Fill in your API keys in .env

docker compose up -d
```

API docs available at `http://localhost:8000/docs`

## Environment Variables

See `.env.example` for all required variables. Key ones:

```
LLM_API_KEY=          # Anthropic Claude API key
STT_API_KEY=          # Deepgram API key
TTS_API_KEY=          # ElevenLabs API key
EMBED_API_KEY=        # OpenAI API key (embeddings)
TELEPHONY_ACCOUNT_SID= # Twilio SID
SUPABASE_URL=         # Supabase project URL
QDRANT_HOST=          # Qdrant host
```

## Status

MVP — built for real estate agencies to handle inbound enquiries autonomously.
