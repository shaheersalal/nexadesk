-- Run this entire block in your Supabase SQL Editor

create table if not exists support_messages (
  id            uuid primary key default gen_random_uuid(),
  company_id    uuid references companies(id) on delete cascade not null,
  sender_role   text not null check (sender_role in ('user', 'admin')),
  content       text not null,
  created_at    timestamptz default now() not null,
  read_by_admin boolean default false not null,
  read_by_user  boolean default false not null
);

alter table support_messages enable row level security;

-- Users and admin can read messages for their company; admin sees everything
create policy "support_read" on support_messages
  for select using (
    auth.uid() = '7227a933-56ef-45c4-8cbc-1c8331c74b21'
    or company_id in (select company_id from users where id = auth.uid())
  );

-- Users send as 'user'; admin can send as 'admin' to any company
create policy "support_insert" on support_messages
  for insert with check (
    auth.uid() = '7227a933-56ef-45c4-8cbc-1c8331c74b21'
    or (sender_role = 'user' and company_id in (select company_id from users where id = auth.uid()))
  );

-- Both sides can mark messages as read
create policy "support_update" on support_messages
  for update using (
    auth.uid() = '7227a933-56ef-45c4-8cbc-1c8331c74b21'
    or company_id in (select company_id from users where id = auth.uid())
  );

-- Enable realtime so both sides receive messages instantly
alter publication supabase_realtime add table support_messages;
