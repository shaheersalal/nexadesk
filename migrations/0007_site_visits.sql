-- Owner-only visitor analytics for shaheer.dev and nexadesk.site — IP, pageview,
-- click, and scroll-depth events. Not company-scoped: this isn't a per-tenant
-- feature, it's Shaheer's own marketing-site analytics, gated purely by
-- ADMIN_UID (app/admin/router.py's require_admin) the same way
-- /dashboard/support and /nxd-c0ns0le already are. No RLS is needed because
-- no non-admin path ever reads this table — see app/analytics/router.py.
--
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS site_visits (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    site        TEXT        NOT NULL CHECK (site IN ('shaheer_dev', 'nexadesk_site')),
    session_id  TEXT        NOT NULL,
    ip_address  TEXT,
    user_agent  TEXT,
    referrer    TEXT,
    path        TEXT,
    event_type  TEXT        NOT NULL CHECK (event_type IN ('pageview', 'click', 'scroll_depth')),
    event_data  JSONB       DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_site_visits_session ON site_visits(session_id);
CREATE INDEX IF NOT EXISTS idx_site_visits_site_created ON site_visits(site, created_at DESC);

COMMENT ON TABLE site_visits IS
    'Owner-only first-party analytics for shaheer.dev/nexadesk.site — never joined against tenant data.';
