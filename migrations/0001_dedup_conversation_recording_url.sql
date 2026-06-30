-- Resolve duplicate conversation recording-URL columns.
--
-- `conversations` had both `call_recording_url` (tracked in alembic/schema.sql, from
-- the original schema) and `recording_url` (added live, untracked, picked up by
-- dashboard/src/pages/LeadDetail.jsx which is the only code that reads either column).
-- No backend code path writes to either column yet, and both are NULL on all 5 existing
-- rows (verified via `SELECT count(*) FILTER (WHERE col IS NOT NULL) ...` before this
-- migration) — so this is a clean drop, not a data migration.
--
-- `recording_url` is canonical (it's the one the frontend actually reads).

ALTER TABLE conversations DROP COLUMN IF EXISTS call_recording_url;
