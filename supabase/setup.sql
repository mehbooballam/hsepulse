-- Run once in the HSE Pulse project's SQL Editor.
-- Server-only encrypted account data. HSE records remain in Google Sheets.
begin;
create table if not exists public.hsepulse_organization (
  id text primary key check (id = 'primary'),
  version bigint not null check (version > 0),
  payload text not null
);
alter table public.hsepulse_organization enable row level security;
revoke all on public.hsepulse_organization from public, anon, authenticated;
grant select, insert, update on public.hsepulse_organization to service_role;
comment on table public.hsepulse_organization is
  'Encrypted HSE Pulse memberships, invitation hashes, audit history and Google credentials. Server only; no client policies.';
commit;
select relrowsecurity as rls_enabled,
 has_table_privilege('anon','public.hsepulse_organization','SELECT') as anon_can_read,
 has_table_privilege('authenticated','public.hsepulse_organization','UPDATE') as user_can_write
from pg_class where oid='public.hsepulse_organization'::regclass;
