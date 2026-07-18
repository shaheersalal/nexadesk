-- Webhook endpoints per company
create table if not exists webhook_endpoints (
  id         uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  url        text not null,
  events     text[] not null default '{}',
  secret     text not null,
  active     boolean not null default true,
  created_at timestamptz not null default now()
);

-- Delivery log (one row per attempt)
create table if not exists webhook_logs (
  id            uuid primary key default gen_random_uuid(),
  endpoint_id   uuid not null references webhook_endpoints(id) on delete cascade,
  event         text not null,
  payload       jsonb not null,
  status_code   int,
  attempts      int not null default 0,
  next_retry_at timestamptz,
  delivered_at  timestamptz,
  error         text,
  created_at    timestamptz not null default now()
);

-- Indexes for fast lookups
create index if not exists idx_webhook_endpoints_company on webhook_endpoints(company_id);
create index if not exists idx_webhook_logs_endpoint    on webhook_logs(endpoint_id);
create index if not exists idx_webhook_logs_retry       on webhook_logs(next_retry_at) where delivered_at is null and attempts < 5;

-- RLS
alter table webhook_endpoints enable row level security;
alter table webhook_logs       enable row level security;

-- Endpoint policies: company members manage their own
create policy "company members manage webhooks"
  on webhook_endpoints for all
  using  (company_id in (select company_id from users where id = auth.uid()))
  with check (company_id in (select company_id from users where id = auth.uid()));

-- Log policies: read-only for company members
create policy "company members read webhook logs"
  on webhook_logs for select
  using (endpoint_id in (
    select id from webhook_endpoints
    where company_id in (select company_id from users where id = auth.uid())
  ));
