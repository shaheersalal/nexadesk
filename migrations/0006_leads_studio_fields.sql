-- Additive lead fields for the 'ai_studio' vertical (see 0005_company_vertical.sql).
--
-- The existing qualifier fields (budget_min/budget_max, area_preference,
-- bedrooms_needed) are real-estate-shaped: numeric AED ranges and bedroom
-- counts don't fit a freelance/agency inquiry. Rather than overload those
-- columns, this adds three new nullable ones used only by the ai_studio
-- prompt/extraction path (app/agents/tools.py). Real-estate leads never
-- populate these; ai_studio leads never populate budget_min/max or
-- bedrooms_needed. Both verticals still write to one `leads` table through
-- one `capture_lead_fields()` function.
--
-- Idempotent: safe to re-run.

ALTER TABLE leads
    ADD COLUMN IF NOT EXISTS client_company TEXT,
    ADD COLUMN IF NOT EXISTS project_type   TEXT,
    ADD COLUMN IF NOT EXISTS budget_text    TEXT;

COMMENT ON COLUMN leads.client_company IS 'ai_studio vertical: caller''s company/agency name.';
COMMENT ON COLUMN leads.project_type   IS 'ai_studio vertical: e.g. "RAG system", "AI receptionist", "automation pipeline".';
COMMENT ON COLUMN leads.budget_text    IS 'ai_studio vertical: free-text budget range, unlike the numeric AED budget_min/max used for real estate.';
