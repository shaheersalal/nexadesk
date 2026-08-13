-- API keys for NexaDesk public API v1 and MCP server
create table if not exists api_keys (
  id          uuid primary key default gen_random_uuid(),
  company_id  uuid not null references companies(id) on delete cascade,
  name        text not null,
  key_hash    text not null unique,
  key_prefix  text not null,
  scopes      text[] not null default '{"leads:read","appointments:read"}',
  last_used   timestamptz,
  created_at  timestamptz not null default now(),
  revoked_at  timestamptz
);

create index if not exists idx_api_keys_company on api_keys(company_id);
create index if not exists idx_api_keys_hash    on api_keys(key_hash);

alter table api_keys enable row level security;

create policy "company members manage api keys"
  on api_keys for all
  to authenticated
  using  (company_id in (select company_id from users where id = auth.uid()))
  with check (company_id in (select company_id from users where id = auth.uid()));
