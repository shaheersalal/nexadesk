# Migrations

Every schema change from this point forward gets a numbered SQL file here, applied to
live Supabase the same session it's written. This replaces the old workflow of editing
`alembic/schema.sql` directly and pasting changes into the Supabase SQL editor by hand
— that workflow is how the tracked schema drifted out of sync with the live database
(see the Phase 2 schema reconciliation).

## Convention

- `NNNN_short_description.sql`, numbered sequentially starting at `0001`, zero-padded
  to 4 digits.
- One logical change per file (e.g. one column drop, one new table, one RLS policy).
- Each file is idempotent where practical (`IF EXISTS` / `IF NOT EXISTS`) so re-running
  it against an already-migrated database is a no-op, not an error.
- After writing a migration file, apply it to live Supabase immediately (Supabase SQL
  editor, or the `apply_migration` MCP tool in a Claude Code session) — don't let the
  file and the live database diverge.
- After applying, regenerate `alembic/schema.sql` from live truth so it stays a correct
  full snapshot. `alembic/schema.sql` is documentation of current state; the files in
  this folder are the history of how it got there.

## Numbering note

This folder starts at `0001` as of 2026-06-30 (Phase 2 schema reconciliation). Schema
changes before this date (initial schema, demo_requests table + RLS, leads qualifier
fields, companies onboarding columns, etc.) predate this convention and aren't
backfilled here — they're documented in `alembic/schema.sql` (current state) and git
history (when/why). Supabase's own migration history (`supabase migration list` /
`list_migrations`) separately tracks `create_demo_requests` and
`add_qualifier_fields_to_leads` from before this convention existed.
