-- NexaDesk — Supabase/Postgres Schema
-- Run this in the Supabase SQL Editor or via psql
-- ─────────────────────────────────────────────────────────────────────────────

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─────────────────────────────────────────────────────────────────────────────
-- Companies (multi-tenant root)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS companies (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT        NOT NULL,
    phone           TEXT,
    email           TEXT,
    address         TEXT,
    working_hours   JSONB       DEFAULT '{"Mon-Fri": "9:00-17:00"}',
    ai_persona      TEXT        DEFAULT 'a friendly and professional real estate receptionist',
    calendar_tokens TEXT,       -- encrypted JSON from Google OAuth
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Users (linked to Supabase Auth)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id          UUID    PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    company_id  UUID    REFERENCES companies(id) ON DELETE SET NULL,
    full_name   TEXT,
    role        TEXT    DEFAULT 'agent' CHECK (role IN ('owner', 'admin', 'agent')),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Properties
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS properties (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id      UUID        NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    title           TEXT        NOT NULL,
    address         TEXT,
    city            TEXT,
    state           TEXT,
    zip             TEXT,
    property_type   TEXT        CHECK (property_type IN ('house','condo','apartment','townhouse','land','commercial')),
    bedrooms        INTEGER,
    bathrooms       NUMERIC(3,1),
    sqft            INTEGER,
    price           NUMERIC(12,2),
    status          TEXT        DEFAULT 'active' CHECK (status IN ('active','pending','sold','off_market')),
    description     TEXT,
    features        JSONB       DEFAULT '[]',
    images          JSONB       DEFAULT '[]',
    mls_number      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER properties_updated_at
    BEFORE UPDATE ON properties
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ─────────────────────────────────────────────────────────────────────────────
-- Leads
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS leads (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id      UUID        NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name            TEXT,
    phone           TEXT,
    email           TEXT,
    source          TEXT        DEFAULT 'manual' CHECK (source IN ('voice','chat','web_form','manual')),
    status          TEXT        DEFAULT 'new'
                                CHECK (status IN ('new','contacted','qualified','appointment','closed_won','closed_lost')),
    score           INTEGER     DEFAULT 0,
    score_breakdown JSONB       DEFAULT '{}',
    interested_in   UUID[]      DEFAULT '{}',
    assigned_to     UUID        REFERENCES users(id) ON DELETE SET NULL,
    notes           TEXT,
    language        TEXT        DEFAULT 'en',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TRIGGER leads_updated_at
    BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ─────────────────────────────────────────────────────────────────────────────
-- Conversations (voice + chat)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id                  UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID        NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    lead_id             UUID        REFERENCES leads(id) ON DELETE SET NULL,
    channel             TEXT        CHECK (channel IN ('voice','chat')),
    session_id          TEXT        UNIQUE,
    transcript          JSONB       DEFAULT '[]',
    summary             TEXT,
    sentiment           TEXT,
    language            TEXT        DEFAULT 'en',
    call_duration       INTEGER,
    call_recording_url  TEXT,
    started_at          TIMESTAMPTZ DEFAULT NOW(),
    ended_at            TIMESTAMPTZ
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Appointments
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS appointments (
    id                  UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID        NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    lead_id             UUID        NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    property_id         UUID        REFERENCES properties(id) ON DELETE SET NULL,
    agent_id            UUID        REFERENCES users(id) ON DELETE SET NULL,
    datetime            TIMESTAMPTZ NOT NULL,
    duration_minutes    INTEGER     DEFAULT 30,
    type                TEXT        DEFAULT 'showing'
                                    CHECK (type IN ('showing','call','meeting','open_house')),
    status              TEXT        DEFAULT 'scheduled'
                                    CHECK (status IN ('scheduled','confirmed','completed','cancelled','no_show')),
    google_event_id     TEXT,
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Documents (RAG source tracking)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id      UUID        NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    filename        TEXT,
    file_type       TEXT,
    category        TEXT        CHECK (category IN ('listing','faq','policy','brochure','notes','other')),
    property_id     UUID        REFERENCES properties(id) ON DELETE SET NULL,
    chunk_count     INTEGER     DEFAULT 0,
    quality_score   NUMERIC(3,2),
    status          TEXT        DEFAULT 'processing'
                                CHECK (status IN ('processing','completed','failed')),
    error_message   TEXT,
    uploaded_by     UUID        REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Row-Level Security
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE companies     ENABLE ROW LEVEL SECURITY;
ALTER TABLE users         ENABLE ROW LEVEL SECURITY;
ALTER TABLE properties    ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads         ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments  ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents     ENABLE ROW LEVEL SECURITY;

-- Helper: get the company_id for the current authenticated user
CREATE OR REPLACE FUNCTION current_company_id() RETURNS UUID AS $$
    SELECT company_id FROM users WHERE id = auth.uid();
$$ LANGUAGE SQL SECURITY DEFINER STABLE;

-- RLS Policies
CREATE POLICY "company_isolation_properties"    ON properties    FOR ALL USING (company_id = current_company_id());
CREATE POLICY "company_isolation_leads"         ON leads         FOR ALL USING (company_id = current_company_id());
CREATE POLICY "company_isolation_conversations" ON conversations FOR ALL USING (company_id = current_company_id());
CREATE POLICY "company_isolation_appointments"  ON appointments  FOR ALL USING (company_id = current_company_id());
CREATE POLICY "company_isolation_documents"     ON documents     FOR ALL USING (company_id = current_company_id());
CREATE POLICY "users_own_row"                   ON users         FOR ALL USING (id = auth.uid());
CREATE POLICY "users_see_company"               ON companies     FOR SELECT USING (id = current_company_id());

-- ─────────────────────────────────────────────────────────────────────────────
-- Indexes
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_leads_company       ON leads(company_id);
CREATE INDEX IF NOT EXISTS idx_leads_status        ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_score         ON leads(score DESC);
CREATE INDEX IF NOT EXISTS idx_convs_company       ON conversations(company_id);
CREATE INDEX IF NOT EXISTS idx_convs_session       ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_appts_company_dt    ON appointments(company_id, datetime);
CREATE INDEX IF NOT EXISTS idx_props_company       ON properties(company_id);
CREATE INDEX IF NOT EXISTS idx_docs_company        ON documents(company_id);
