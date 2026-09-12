-- Run after database.sql. All test records, counters and audit-envelope updates roll back.
begin;
do $$
declare
 project_key text := 'lifecycle-qa-' || gen_random_uuid()::text;
 record_key text := 'lifecycle-record-' || gen_random_uuid()::text;
 v bigint; payload text; project_revision text; record_revision text;
 rejected boolean;
begin
 select version, h.payload into v,payload from public.hsepulse_organization h where id='primary';
 perform public.hsepulse_save_records(
   jsonb_build_object('Projects',jsonb_build_array(jsonb_build_object('id',project_key,'name','Temporary lifecycle verification','status','Active'))),
   '{}'::jsonb,v,payload);
 select revision into project_revision from public.hsepulse_records where category='Projects' and id=project_key;
 select version into v from public.hsepulse_organization where id='primary';
 perform public.hsepulse_save_records(
   jsonb_build_object('03_DAILY_REPORT',jsonb_build_array(jsonb_build_object('id',record_key,'Project',project_key,'Date',current_date::text))),
   '{}'::jsonb,v,payload);
 select revision into record_revision from public.hsepulse_records where category='03_DAILY_REPORT' and id=record_key;
 select version into v from public.hsepulse_organization where id='primary';
 rejected=false;
 begin
  perform public.hsepulse_save_records(
    jsonb_build_object('03_DAILY_REPORT',jsonb_build_array(jsonb_build_object('id',record_key,'Project',project_key))),
    '{}'::jsonb,v,payload);
 exception when sqlstate '40001' then rejected=true;
 end;
 if not rejected then raise exception 'FAILED: stale write accepted'; end if;
 perform public.hsepulse_save_records(
   jsonb_build_object('Projects',jsonb_build_array(jsonb_build_object('id',project_key,'status','Closed','closed_at',now()::text,'closed_by','Migration verification','closure_notes','Disposable transaction test','closure_context','{}'))),
   jsonb_build_object('Projects',jsonb_build_object(project_key,project_revision)),v,payload);
 select revision into project_revision from public.hsepulse_records where category='Projects' and id=project_key;
 select version into v from public.hsepulse_organization where id='primary';
 rejected=false;
 begin
  perform public.hsepulse_save_records(
    jsonb_build_object('03_DAILY_REPORT',jsonb_build_array(jsonb_build_object('id',record_key,'Project',project_key,'Man-hours',100))),
    jsonb_build_object('03_DAILY_REPORT',jsonb_build_object(record_key,record_revision)),v,payload);
 exception when raise_exception then
  if sqlerrm <> 'Closed or deleted projects are read-only' then raise; end if;
  rejected=true;
 end;
 if not rejected then raise exception 'FAILED: closed project write accepted'; end if;
 rejected=false;
 begin
  perform public.hsepulse_save_records(
    jsonb_build_object('Evidence',jsonb_build_array(jsonb_build_object('id',record_key,'project',project_key))),
    '{}'::jsonb,v,payload);
 exception when raise_exception then
  if sqlerrm <> 'Closed or deleted projects are read-only' then raise; end if;
  rejected=true;
 end;
 if not rejected then raise exception 'FAILED: closed project evidence accepted'; end if;
 perform public.hsepulse_save_records(
   jsonb_build_object('Projects',jsonb_build_array(jsonb_build_object('id',project_key,'status','Deleted','deleted_at',now()::text,'deleted_by','Migration verification'))),
   jsonb_build_object('Projects',jsonb_build_object(project_key,project_revision)),v,payload);
 select revision into project_revision from public.hsepulse_records where category='Projects' and id=project_key;
 select version into v from public.hsepulse_organization where id='primary';
 rejected=false;
 begin
  perform public.hsepulse_save_records(
    jsonb_build_object('Projects',jsonb_build_array(jsonb_build_object('id',project_key,'status','Active'))),
    jsonb_build_object('Projects',jsonb_build_object(project_key,project_revision)),v,payload);
 exception when raise_exception then
  if sqlerrm <> 'Closed or deleted projects are read-only' then raise; end if;
  rejected=true;
 end;
 if not rejected then raise exception 'FAILED: deleted project restored'; end if;
end $$;
rollback;
select 'PASS: stale writes, closed records, evidence and deleted project guards; test data rolled back' as result;
