-- Metadata-only migration. Branding is stored in existing JSONB records.
-- No project or operational record is changed.
begin;
update public.hsepulse_categories
set fields = fields || '["branding"]'::jsonb
where category = 'Projects' and not (fields ? 'branding');
commit;
select category, fields ? 'branding' as branding_field_registered
from public.hsepulse_categories where category = 'Projects';
