-- Run in Supabase SQL Editor
-- Auto-creates a company + user row when someone signs up
-- Also emails shaheersalal@gmail.com via Resend
--
-- BEFORE RUNNING:
--   1. Sign up free at resend.com → get an API key
--   2. Replace YOUR_RESEND_API_KEY below with your real key

-- Enable pg_net (needed for HTTP calls from Postgres)
create extension if not exists pg_net schema extensions;

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  new_company_id uuid;
  admin_uid      uuid := '7227a933-56ef-45c4-8cbc-1c8331c74b21';
  resend_key     text := 're_g5ziXXok_LZN9NEE64tZp7Qmfp1naEVGi';
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

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
