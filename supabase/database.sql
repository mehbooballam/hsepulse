-- Supabase-only operational storage. Apply once through the SQL Editor.
begin;
create table if not exists public.hsepulse_categories (
 category text primary key,
 label text not null,
 fields jsonb not null check (jsonb_typeof(fields) = 'array')
);
create table if not exists public.hsepulse_counters (
 category text primary key references public.hsepulse_categories(category),
 value bigint not null check (value > 0)
);
create table if not exists public.hsepulse_records (
 category text not null references public.hsepulse_categories(category),
 id text not null,
 record_id text not null unique,
 sequence_number bigint not null,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 revision text not null,
 project text,
 data jsonb not null check (jsonb_typeof(data) = 'object'),
 primary key (category,id),
 unique (category,sequence_number)
);
create index if not exists hsepulse_records_project_idx on public.hsepulse_records(project,category);
create table if not exists public.hsepulse_record_history (
 category text not null,
 id text not null,
 revision text not null,
 saved_at timestamptz not null default now(),
 data jsonb not null,
 primary key (category,id,revision),
 foreign key (category,id) references public.hsepulse_records(category,id)
);
alter table public.hsepulse_categories enable row level security;
alter table public.hsepulse_counters enable row level security;
alter table public.hsepulse_records enable row level security;
alter table public.hsepulse_record_history enable row level security;
revoke all on public.hsepulse_categories,public.hsepulse_counters,public.hsepulse_records,public.hsepulse_record_history from public,anon,authenticated;
grant select,insert,update on public.hsepulse_categories,public.hsepulse_counters,public.hsepulse_records,public.hsepulse_record_history to service_role;

-- The app verifies a Supabase session and fresh membership before calling.
-- All operational writes and the encrypted audit commit in one transaction.
create or replace function public.hsepulse_save_records(
 changes jsonb, expected jsonb, organization_version bigint, organization_payload text
) returns jsonb language plpgsql security invoker set search_path = '' as $$
declare
 current_version bigint; cat text; rows jsonb; r jsonb;
 old public.hsepulse_records%rowtype; seq bigint; public_id text;
 entry_time timestamptz; rev text; saved jsonb; result jsonb := '[]'::jsonb;
begin
 select version into current_version from public.hsepulse_organization where id='primary' for update;
 if current_version is distinct from organization_version then
  raise exception 'Organization permissions or records changed. Refresh and retry.' using errcode='40001';
 end if;
 for cat,rows in select * from jsonb_each(changes) loop
  if not exists(select 1 from public.hsepulse_categories where category=cat) then
   raise exception 'Unknown register %',cat;
  end if;
  if jsonb_array_length(rows) <> (select count(distinct item->>'id') from jsonb_array_elements(rows) item) then
   raise exception 'Duplicate or missing record ID';
  end if;
  for r in select * from jsonb_array_elements(rows) loop
   if coalesce(r->>'id','')='' then raise exception 'Record key is required'; end if;
   select * into old from public.hsepulse_records where category=cat and id=r->>'id' for update;
   if coalesce(old.revision,'') <> coalesce(expected->cat->>(r->>'id'),'') then
    raise exception 'A record changed. Refresh and retry.' using errcode='40001';
   end if;
   -- Enforce lifecycle under the organization lock, including stale form saves.
   saved=coalesce(old.data,'{}'::jsonb) || r;
   if cat='Projects' then
    if old.data->>'status'='Deleted' or
       (old.data->>'status'='Closed' and saved->>'status' <> 'Deleted') then
     raise exception 'Closed or deleted projects are read-only';
    end if;
    if coalesce(trim(saved->>'name'),'')='' or coalesce(saved->>'status','') not in ('Active','Inactive','On Hold','Closed','Deleted') then
     raise exception 'Enter a project name and valid status';
    end if;
    if saved->>'status' in ('Closed','Deleted') and old.id is null then
     raise exception 'Create the project before closing or deleting it';
    end if;
    if saved->>'status'='Closed' and
       (coalesce(saved->>'closed_at','')='' or coalesce(saved->>'closed_by','')='' or
        coalesce(trim(saved->>'closure_notes'),'')='' or coalesce(saved->>'closure_context','')='') then
     raise exception 'Completion requires closure details';
    end if;
    if saved->>'status'='Deleted' and
       (coalesce(saved->>'deleted_at','')='' or coalesce(saved->>'deleted_by','')='') then
     raise exception 'Deletion requires recorded confirmation';
    end if;
   elsif exists(select 1 from public.hsepulse_records p where p.category='Projects'
       and p.id in (coalesce(saved->>'Project',saved->>'project'), old.project)
       and p.data->>'status' in ('Closed','Deleted'))
     or exists(select 1 from jsonb_array_elements(coalesce(changes->'Projects','[]'::jsonb)) p
       where p->>'id' in (coalesce(saved->>'Project',saved->>'project'), old.project)
       and p->>'status' in ('Closed','Deleted')) then
    raise exception 'Closed or deleted projects are read-only';
   end if;
   if old.id is null then
    insert into public.hsepulse_counters(category,value) values(cat,1)
    on conflict(category) do update set value=public.hsepulse_counters.value+1 returning value into seq;
    entry_time=clock_timestamp();
    public_id=upper(regexp_replace(cat,'^[0-9]+_','')) || '-' || lpad(seq::text,greatest(6,length(seq::text)),'0') || '-' || to_char(entry_time at time zone 'UTC','YYYYMMDD"T"HH24MISSUS"Z"');
   else
    seq=old.sequence_number; entry_time=old.created_at; public_id=old.record_id;
   end if;
   rev=gen_random_uuid()::text;
   saved=coalesce(old.data,'{}'::jsonb) || r || jsonb_build_object('Record ID',public_id,'Entry sequence',seq,'Created at',entry_time,'revision',rev,'updated_at',clock_timestamp());
   insert into public.hsepulse_records(category,id,record_id,sequence_number,created_at,revision,project,data)
   values(cat,r->>'id',public_id,seq,entry_time,rev,coalesce(saved->>'Project',saved->>'project'),saved)
   on conflict(category,id) do update set revision=excluded.revision,updated_at=clock_timestamp(),project=excluded.project,data=excluded.data;
   insert into public.hsepulse_record_history(category,id,revision,data) values(cat,r->>'id',rev,saved);
   result=result || jsonb_build_array(jsonb_build_object('category',cat,'id',r->>'id','Record ID',public_id));
  end loop;
 end loop;
 update public.hsepulse_organization set version=version+1,payload=organization_payload where id='primary';
 return result;
end $$;
revoke all on function public.hsepulse_save_records(jsonb,jsonb,bigint,text) from public,anon,authenticated;
grant execute on function public.hsepulse_save_records(jsonb,jsonb,bigint,text) to service_role;
-- Register lifecycle fields without altering existing records or field order.
update public.hsepulse_categories c
set fields = c.fields || coalesce((
 select jsonb_agg(f) from unnest(array['closed_at','closed_by','closure_notes','closure_context','deleted_at','deleted_by']) f
 where not (c.fields ? f)
), '[]'::jsonb)
where category='Projects';
commit;
select relname,relrowsecurity,has_table_privilege('anon',oid,'SELECT') as public_read,
 has_table_privilege('authenticated',oid,'UPDATE') as user_write
from pg_class where relname in ('hsepulse_records','hsepulse_record_history','hsepulse_categories','hsepulse_counters');
