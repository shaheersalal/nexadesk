-- CRM OAuth consumer connections: NexaDesk → external CRM
create table if not exists crm_connections (
  id            uuid primary key default gen_random_uuid(),
  company_id    uuid not null references companies(id) on delete cascade,
  provider      text not null,
  access_token  text not null,
  refresh_token text,
  expires_at    timestamptz,
  scope         text,
  account_id    text,
  account_name  text,
  meta          jsonb not null default '{}',
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique(company_id, provider)
);

create index if not exists idx_crm_connections_company on crm_connections(company_id);

alter table crm_connections enable row level security;

create policy "company members manage crm connections"
  on crm_connections for all
  to authenticated
  using  (company_id in (select company_id from users where id = auth.uid()))
  with check (company_id in (select company_id from users where id = auth.uid()));
