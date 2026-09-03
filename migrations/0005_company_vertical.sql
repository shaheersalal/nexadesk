-- Adds a `vertical` column to `companies` so the shared orchestrator
-- (app/agents/orchestrator.py, app/shared/prompts.py, app/agents/tools.py)
-- can serve more than one business domain through one pipeline, instead of
-- forking a second code path per vertical.
--
-- Default 'real_estate' preserves every existing company's behaviour exactly
-- as-is — nothing changes for a live tenant until its row is explicitly
-- switched. The application code also treats a missing/NULL vertical as
-- 'real_estate' (see app/shared/verticals.py), so this migration is safe to
-- apply before or after the code that reads it.
--
-- Idempotent: safe to re-run.

ALTER TABLE companies
    ADD COLUMN IF NOT EXISTS vertical TEXT NOT NULL DEFAULT 'real_estate'
        CHECK (vertical IN ('real_estate', 'ai_studio'));

COMMENT ON COLUMN companies.vertical IS
    'Which prompt/field-schema set the orchestrator uses for this company. '
    'Add new values here (and in app/shared/verticals.py) rather than forking '
    'a parallel orchestrator per domain.';
