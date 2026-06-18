-- Run this in Supabase SQL Editor before deploying the onboarding agent

ALTER TABLE companies
  ADD COLUMN IF NOT EXISTS receptionist_name   TEXT    DEFAULT 'Aria',
  ADD COLUMN IF NOT EXISTS system_prompt       TEXT,
  ADD COLUMN IF NOT EXISTS onboarding_data     JSONB   DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS onboarding_complete BOOLEAN DEFAULT FALSE;
