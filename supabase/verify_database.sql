-- All test writes are rolled back; no sample incidents remain in production.
begin;
do $$
declare v bigint; p text; saved_id text; saved_rev text; amount bigint;
begin
 select version,payload into v,p from public.hsepulse_organization where id='primary';
 perform public.hsepulse_save_records('{"05_INCIDENTS":[{"id":"__transaction_test__","Project":"P01","Description":"transaction check","Custom field":"preserved"}]}'::jsonb,'{}',v,p);
 select record_id,revision into saved_id,saved_rev from public.hsepulse_records where category='05_INCIDENTS' and id='__transaction_test__';
 if saved_id !~ '^INCIDENTS-[0-9]{6,}-[0-9]{8}T[0-9]{12}Z$' then raise exception 'Invalid generated ID %',saved_id; end if;
 select version,payload into v,p from public.hsepulse_organization where id='primary';
 perform public.hsepulse_save_records('{"05_INCIDENTS":[{"id":"__transaction_test__","Description":"updated"}]}'::jsonb,jsonb_build_object('05_INCIDENTS',jsonb_build_object('__transaction_test__',saved_rev)),v,p);
 if not exists(select 1 from public.hsepulse_records where id='__transaction_test__' and record_id=saved_id and data->>'Custom field'='preserved') then raise exception 'ID or field was lost on edit'; end if;
 select version,payload into v,p from public.hsepulse_organization where id='primary';
 begin
  perform public.hsepulse_save_records('{"05_INCIDENTS":[{"id":"__atomic_first__"},{"id":"__transaction_test__","Description":"stale"}]}'::jsonb,'{}',v,p);
  raise exception 'Expected stale edit rejection';
 exception when serialization_failure then null;
 end;
 if exists(select 1 from public.hsepulse_records where id='__atomic_first__') then raise exception 'Partial batch was committed'; end if;
 select count(*) into amount from public.hsepulse_record_history where category='05_INCIDENTS' and id='__transaction_test__';
 if amount<>2 then raise exception 'History missing revisions'; end if;
 if has_table_privilege('anon','public.hsepulse_records','SELECT') or has_function_privilege('authenticated','public.hsepulse_save_records(jsonb,jsonb,bigint,text)','EXECUTE') then raise exception 'Public access unexpectedly allowed'; end if;
end $$;
rollback;
select 'PASS: generated IDs, stable edits, retained fields, atomic rollback, history and denied public access' as result;
