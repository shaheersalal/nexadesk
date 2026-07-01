-- Phase 6: modify handle_new_user() to support the child-account invite flow.
--
-- When a parent-account owner invites a new user to a child company via
-- POST /companies/child (which calls auth.admin.invite_user_by_email with
-- options.data = {"child_company_id": "...", "full_name": "..."}),
-- Supabase sets raw_user_meta_data on the new auth.users row.
-- The trigger now checks for that key FIRST: if present, it links the user
-- to the pre-created child company instead of auto-provisioning a new one.
--
-- SECRET REDACTED: this file has a placeholder for the Resend API key.
-- Apply this migration manually in the Supabase SQL Editor with the real
-- key substituted, OR use the key-preserving DO block in the migration notes.
-- See alembic/schema.sql's SECRET REDACTED comment for full context.
-- The live change is applied via execute_sql with a string-patch DO block
-- (see migrations/README.md Phase 6 notes) so the real key is never exposed
-- or overwritten.

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
  if new.id = admin_uid then return new; end if;

  -- Phase 6: if this is a child-account invite, link the user to the
  -- pre-created child company instead of auto-provisioning a new one.
  -- The invite_user_by_email call sets raw_user_meta_data->>'child_company_id'.
  if (new.raw_user_meta_data->>'child_company_id') is not null then
    insert into public.users (id, company_id, full_name, role)
    values (
      new.id,
      (new.raw_user_meta_data->>'child_company_id')::uuid,
      coalesce(new.raw_user_meta_data->>'full_name', split_part(new.email, '@', 1)),
      'owner'
    )
    on conflict (id) do update
      set company_id = excluded.company_id,
          role       = excluded.role;
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
