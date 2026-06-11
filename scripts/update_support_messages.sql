-- Run in Supabase SQL Editor

-- Add user_id and user_email; make company_id nullable
alter table support_messages
  add column if not exists user_id uuid references auth.users(id),
  add column if not exists user_email text;

alter table support_messages alter column company_id drop not null;

-- Backfill user_id from company membership for any existing rows (best effort)
update support_messages sm
set user_id = u.id
from users u
where u.company_id = sm.company_id
  and sm.user_id is null
  and sm.sender_role = 'user';

-- Drop and recreate RLS policies
drop policy if exists "support_read"   on support_messages;
drop policy if exists "support_insert" on support_messages;
drop policy if exists "support_update" on support_messages;

create policy "support_read" on support_messages
  for select using (
    auth.uid() = '7227a933-56ef-45c4-8cbc-1c8331c74b21'
    or auth.uid() = user_id
    or (company_id is not null and company_id in (
      select company_id from users where id = auth.uid()
    ))
  );

create policy "support_insert" on support_messages
  for insert with check (
    auth.uid() = '7227a933-56ef-45c4-8cbc-1c8331c74b21'
    or (sender_role = 'user' and auth.uid() = user_id)
  );

create policy "support_update" on support_messages
  for update using (
    auth.uid() = '7227a933-56ef-45c4-8cbc-1c8331c74b21'
    or auth.uid() = user_id
    or (company_id is not null and company_id in (
      select company_id from users where id = auth.uid()
    ))
  );
