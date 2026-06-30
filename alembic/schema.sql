-- NexaDesk — Supabase/Postgres Schema
-- This file is a generated SNAPSHOT of the live database, regenerated from
-- information_schema / pg_catalog as of 2026-06-30 (Phase 2 schema reconciliation).
-- It documents current state — it is not run directly against a fresh database step
-- by step. For actual schema changes going forward, see migrations/README.md: write a
-- numbered file in migrations/, apply it live, then regenerate this file.
-- ─────────────────────────────────────────────────────────────────────────────

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─────────────────────────────────────────────────────────────────────────────
-- Companies (multi-tenant root)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS companies (
    id                   UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                 TEXT        NOT NULL,
    phone                TEXT,
    email                TEXT,
    address              TEXT,
    working_hours        JSONB       DEFAULT '{"Mon-Fri": "9:00-17:00"}',
    ai_persona           TEXT        DEFAULT 'a friendly and professional real estate receptionist',
    calendar_tokens      TEXT,       -- encrypted JSON from Google OAuth
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    receptionist_name    TEXT        DEFAULT 'Nexa',
    system_prompt        TEXT,
    onboarding_data      JSONB       DEFAULT '{}',
    onboarding_complete  BOOLEAN     DEFAULT FALSE
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

CREATE TRIGGER properties_updated_at
    BEFORE UPDATE ON properties
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ─────────────────────────────────────────────────────────────────────────────
-- Leads
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS leads (
    id                UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id        UUID        NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name              TEXT,
    phone             TEXT,
    email             TEXT,
    source            TEXT        DEFAULT 'manual' CHECK (source IN ('voice','chat','web_form','manual')),
    status            TEXT        DEFAULT 'new'
                                  CHECK (status IN ('new','contacted','qualified','appointment','closed_won','closed_lost')),
    score             INTEGER     DEFAULT 0,
    score_breakdown   JSONB       DEFAULT '{}',
    interested_in     UUID[]      DEFAULT '{}',
    assigned_to       UUID        REFERENCES users(id) ON DELETE SET NULL,
    notes             TEXT,
    language          TEXT        DEFAULT 'en',
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW(),
    budget_min        INTEGER,
    budget_max        INTEGER,
    area_preference   TEXT,
    bedrooms_needed   INTEGER,
    timeline          TEXT,
    intent            TEXT,
    needs_human       BOOLEAN     DEFAULT FALSE
);

CREATE TRIGGER leads_updated_at
    BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ─────────────────────────────────────────────────────────────────────────────
-- Conversations (voice + chat)
-- ─────────────────────────────────────────────────────────────────────────────
-- NOTE: this table used to also have `call_recording_url` (tracked schema, original
-- design) alongside `recording_url` (added live, untracked, the one actually read by
-- dashboard/src/pages/LeadDetail.jsx). Both were NULL on every existing row. Resolved
-- in migrations/0001_dedup_conversation_recording_url.sql — `call_recording_url`
-- dropped, `recording_url` is canonical.
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
    started_at          TIMESTAMPTZ DEFAULT NOW(),
    ended_at            TIMESTAMPTZ,
    recording_url       TEXT
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
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    storage_path    TEXT
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Support messages (in-app support chat between agency users and admin)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS support_messages (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID        REFERENCES companies(id) ON DELETE CASCADE,
    sender_role     TEXT        NOT NULL CHECK (sender_role IN ('user','admin')),
    content         TEXT        NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    read_by_admin   BOOLEAN     DEFAULT FALSE,
    read_by_user    BOOLEAN     DEFAULT FALSE,
    user_id         UUID        REFERENCES auth.users(id),
    user_email      TEXT
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Demo requests (public landing page "Book a Demo" form)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS demo_requests (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT,
    email           TEXT,
    agency_name     TEXT,
    phone           TEXT,
    country         TEXT,
    monthly_calls   TEXT,
    status          TEXT        DEFAULT 'pending',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Functions
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

-- Helper: get the company_id for the current authenticated user
CREATE OR REPLACE FUNCTION current_company_id() RETURNS UUID AS $$
    SELECT company_id FROM users WHERE id = auth.uid();
$$ LANGUAGE SQL SECURITY DEFINER STABLE;

CREATE OR REPLACE FUNCTION increment_lead_score(p_lead_id UUID, p_delta INTEGER) RETURNS VOID AS $$
    UPDATE leads SET score = GREATEST(0, COALESCE(score, 0) + p_delta) WHERE id = p_lead_id;
$$ LANGUAGE SQL;

-- Fires on new Supabase Auth signup (auth.users INSERT): auto-provisions a company +
-- links the user as its owner, then emails the admin via Resend.
--
-- SECRET REDACTED: the live version of this function has a Resend API key
-- (`re_...`) hardcoded in `resend_key` below. That key is LIVE and was found
-- committed nowhere except inside this Postgres function body — do not paste the
-- real key back into this tracked file (it would commit a live credential to git,
-- same class of mistake as the HF token incident from Phase 1).
--
-- TODO before next deploy that touches this function: rotate the Resend key, then
-- move it out of inline SQL entirely — either Supabase Vault (`vault.decrypted_secrets`)
-- or have this function call out to a backend webhook that holds the key in env vars,
-- instead of embedding a credential directly in a database function.
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
declare
  new_company_id uuid;
  admin_uid      uuid := '7227a933-56ef-45c4-8cbc-1c8331c74b21';
  resend_key     text := '<REDACTED — see comment above, set the real key only in the live DB, never in this tracked file>';
begin
  -- Skip auto-provision for the admin account
  if new.id = admin_uid then
    return new;
  end if;

  -- 1. Create a company for this user
  insert into public.companies (name, email)
  values (
    split_part(new.email, '@', 1) || ' Agency',
    new.email
  )
  returning id into new_company_id;

  -- 2. Link auth user → company
  insert into public.users (id, company_id, full_name, role)
  values (
    new.id,
    new_company_id,
    split_part(new.email, '@', 1),
    'owner'
  )
  on conflict (id) do update
    set company_id = excluded.company_id,
        role       = excluded.role;

  -- 3. Notify admin by email (async, non-blocking)
  if resend_key <> 'YOUR_RESEND_API_KEY' then
    perform net.http_post(
      url     := 'https://api.resend.com/emails',
      headers := jsonb_build_object(
        'Authorization', 'Bearer ' || resend_key,
        'Content-Type',  'application/json'
      ),
      body    := jsonb_build_object(
        'from',    'NexaDesk <onboarding@resend.dev>',
        'to',      array['shaheersalal@gmail.com'],
        'subject', 'New NexaDesk signup: ' || new.email,
        'text',    'Someone just signed up for NexaDesk.' ||
                   E'\n\nEmail: ' || new.email ||
                   E'\nTime:  ' || now()::text ||
                   E'\n\nCheck Supabase Auth → Users to see their account.'
      )
    );
  end if;

  return new;

exception when others then
  -- Never block signup even if something above fails
  raise warning 'handle_new_user failed for %: %', new.email, sqlerrm;
  return new;
end;
$$;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- ─────────────────────────────────────────────────────────────────────────────
-- Row-Level Security
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE companies         ENABLE ROW LEVEL SECURITY;
ALTER TABLE users              ENABLE ROW LEVEL SECURITY;
ALTER TABLE properties         ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads              ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations      ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments       ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents          ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_messages   ENABLE ROW LEVEL SECURITY;
ALTER TABLE demo_requests      ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "company_isolation_properties"    ON properties    FOR ALL USING (company_id = current_company_id());
CREATE POLICY "company_isolation_leads"         ON leads         FOR ALL USING (company_id = current_company_id());
CREATE POLICY "company_isolation_conversations" ON conversations FOR ALL USING (company_id = current_company_id());
CREATE POLICY "company_isolation_appointments"  ON appointments  FOR ALL USING (company_id = current_company_id());
CREATE POLICY "company_isolation_documents"     ON documents     FOR ALL USING (company_id = current_company_id());
CREATE POLICY "users_own_row"                   ON users         FOR ALL USING (id = auth.uid());
CREATE POLICY "users_see_company"               ON companies     FOR SELECT USING (id = current_company_id());

-- demo_requests: public landing page form — anyone can submit, only the admin
-- account can read/update (lead follow-up triage)
CREATE POLICY "anyone_can_submit"   ON demo_requests FOR INSERT TO anon, authenticated WITH CHECK (true);
CREATE POLICY "admin_only_read_update" ON demo_requests FOR SELECT TO authenticated
    USING (auth.uid() = '7227a933-56ef-45c4-8cbc-1c8331c74b21'::uuid);
CREATE POLICY "admin_only_update"   ON demo_requests FOR UPDATE TO authenticated
    USING (auth.uid() = '7227a933-56ef-45c4-8cbc-1c8331c74b21'::uuid);

-- support_messages: admin sees/sends everything; a regular user sees/sends their own
-- messages and any tied to their company
CREATE POLICY "support_insert" ON support_messages FOR INSERT
    WITH CHECK (
        auth.uid() = '7227a933-56ef-45c4-8cbc-1c8331c74b21'::uuid
        OR (sender_role = 'user' AND auth.uid() = user_id)
    );
CREATE POLICY "support_read" ON support_messages FOR SELECT
    USING (
        auth.uid() = '7227a933-56ef-45c4-8cbc-1c8331c74b21'::uuid
        OR auth.uid() = user_id
        OR (company_id IS NOT NULL AND company_id IN (SELECT company_id FROM users WHERE id = auth.uid()))
    );
CREATE POLICY "support_update" ON support_messages FOR UPDATE
    USING (
        auth.uid() = '7227a933-56ef-45c4-8cbc-1c8331c74b21'::uuid
        OR auth.uid() = user_id
        OR (company_id IS NOT NULL AND company_id IN (SELECT company_id FROM users WHERE id = auth.uid()))
    );

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
