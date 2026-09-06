-- Durable, owner-only logging for shaheer.dev/nexadesk.site visitor activity,
-- separate from the ephemeral Redis live-fetch context in app/rag/live_fetch.py
-- (which stays ephemeral and still gets deleted from the model's own working
-- context at session end - that deletion is about what the LLM sees, not
-- about the owner's own records, which is what this migration is for).
--
-- Not company-scoped, no RLS - protected purely by require_admin, same as
-- site_visits (0007_site_visits.sql).
--
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS site_live_fetches (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    site              TEXT        NOT NULL CHECK (site IN ('shaheer_dev', 'nexadesk_site')),
    session_id        TEXT        NOT NULL,
    phone             TEXT,
    ip_address        TEXT,
    url               TEXT        NOT NULL,
    scraped_excerpt   TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_site_live_fetches_session ON site_live_fetches(session_id);
CREATE INDEX IF NOT EXISTS idx_site_live_fetches_phone ON site_live_fetches(phone) WHERE phone IS NOT NULL;

CREATE TABLE IF NOT EXISTS site_reviews (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    site         TEXT        NOT NULL CHECK (site IN ('shaheer_dev', 'nexadesk_site')),
    session_id   TEXT        NOT NULL,
    ip_address   TEXT,
    stars        SMALLINT    CHECK (stars BETWEEN 1 AND 5),
    review_text  TEXT,
    email        TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_site_reviews_session ON site_reviews(session_id);

-- One row per (site, ip_address) - the visitor "identity" record. Upserted
-- on every session-end finalize (POST /analytics/session-end) rather than
-- creating a new row per visit, so a returning IP accumulates visit_dates
-- instead of appearing as N separate log entries.
CREATE TABLE IF NOT EXISTS site_visitors (
    site               TEXT        NOT NULL CHECK (site IN ('shaheer_dev', 'nexadesk_site')),
    ip_address         TEXT        NOT NULL,
    first_seen         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    visit_dates        DATE[]      NOT NULL DEFAULT '{}',
    session_count      INT         NOT NULL DEFAULT 0,
    last_session_id    TEXT,
    last_entered_url   TEXT,
    last_scraped_excerpt TEXT,
    email              TEXT,
    last_review_stars  SMALLINT,
    last_review_text   TEXT,
    last_conversation_id UUID,
    notified_at        TIMESTAMPTZ,
    PRIMARY KEY (site, ip_address)
);

COMMENT ON TABLE site_visitors IS
    'One row per (site, ip_address) - accumulates visit_dates instead of a new row per visit. See app/analytics/router.py::finalize_session.';
