# HSE Pulse

A multi-project Streamlit HSE application backed entirely by Supabase. Supabase
Auth provides invited-user email/password sign-in; the database stores all
operational records, evidence, project configuration, memberships and audit history.
There is no Google Sheets setup or Google sign-in in the application.

## Platform setup

1. Run `supabase/setup.sql`, then `supabase/database.sql` in the Supabase SQL Editor.
2. Set the Supabase URL, publishable key, server secret key and application encryption
   key using `.streamlit/organization.secrets.example.toml`. Keep real keys out of Git.
3. Run `.venv/bin/python bootstrap_database.py` with the ignored local secrets file.
   This registers every category and initializes missing template records. Existing
   data is preserved. The initializer must finish before deploying the application.
4. Configure Supabase's Site URL and redirect allowlist for your app. Keep public
   signup and anonymous access disabled. Invite the configured bootstrap administrator.
5. Open the invitation or password recovery email and choose a password. The verified
   bootstrap email becomes the first administrator once. Invite colleagues in
   **Team & access**, assigning their roles and project scope.

The hosted entry point is `app.py`. Dependencies are pinned in `requirements.lock`.
Run locally with `.venv/bin/streamlit run app.py`. Without organization mode the app
uses an isolated demonstration session; live deployments require Supabase configuration.

## Data coverage

`storage.SCHEMAS` includes all fields in `domain.SCHEMAS` and `enterprise.SCHEMAS`:
288 KPI definitions, daily KPI inputs, sites, corrective actions, projects, settings,
standards, evidence, alert acknowledgements, and all 15 operational register types.
The 11 original workbook input registers retain every source input field. Their
first ID column is represented by the system-generated **Record ID**. Additional
stop-work, audit, emergency and resource registers are included.

Each operational row is stored independently in `hsepulse_records`. Its `data` JSONB
retains complete field names, values and additional fields without truncation;
`hsepulse_categories.fields` records the full field dictionary. Project, category,
sequence, ID and timestamps have separate indexed/typed database columns. Evidence
bytes are stored as the existing base64 chunks in database records and included in
JSON exports. `hsepulse_record_history` retains each saved revision.

## Record identifiers

The database generates a unique public ID at first save, for example:
`INCIDENTS-000001-20260908T193012123456Z`.

This encodes the register category, a per-category sequence and creation time in
UTC (including microseconds). Sequence allocation is transactional across app
instances. The ID and creation time never change on edits. Internal keys remain
stable for project codes, daily-report uniqueness and linked actions/evidence;
exports label them **Internal key** separately from the public **Record ID**.
Historical keys are not destructively renumbered. Imported or template records
receive a public ID when first inserted into this database; their source timestamps
remain in the source data where available.

## Exports

**Data & export** provides CSV and JSON for every accessible operational category,
plus a ZIP of all accessible categories. Empty categories retain their column
headers. Register pages include direct exports. Team administration exports members,
invitation status (without token hashes) and audit history for administrators only.
CSV exports escape spreadsheet formula prefixes. JSON preserves original values.

Permissions are checked server-side on every read, mutation and export. Project
roles receive only assigned projects; corporate viewers can read the portfolio.
Only administrators manage accounts. Viewer roles cannot write. A verified Supabase
identity alone does not grant workspace membership. Role grants never come from
editable user metadata. Account suspensions and role changes are rechecked on access.

## Consistency and security

All database tables enable RLS and deny `anon` and `authenticated` direct access.
Only the server credential can use record tables and the save function. Application
RBAC scopes the server results. Do not embed the server key in a browser client.

Operational batches, linked actions/evidence and encrypted audit updates commit in
one database transaction. Revision predicates reject stale edits. The organization
version lock also prevents an access change from racing a pending save. Account
metadata is encrypted with Fernet; back up that encryption key separately.

One organization is supported per deployment. Current reads paginate all records
before role filtering; very large datasets will need query-level filtering and
pagination in the UI. The Supabase default email service has recipient and rate
limits; configure custom SMTP in Supabase for wider-team delivery.

## Verification

Run `.venv/bin/python -m unittest discover -q`. Tests cover KPI calculations, form
validation, workbook field coverage, ID stability, exports, pagination, auth, RBAC
and revision conflicts. Live deployment checks must also verify transactional
writes, rollback on conflicts and denied direct public access.

Legacy workbook/Sheets utilities are retained for historical reference only; the
application neither reads Google credentials nor connects to a spreadsheet.

## Project editing, completion and deletion

Administrators and corporate managers use **Manage projects** to edit project
name, client, location, leads and status. **Complete & close project** requires
completion/handover notes and the exact project code. Closure records who closed
it and when, freezes the settings and standards used by its report, and makes
project details and all linked operational records read-only. Outstanding actions
are retained and reported, not automatically marked complete.

Closed projects offer **Generate closure PDF** in Manage projects and the project
dashboard (including for assigned viewers). The report contains closure details,
all KPI summaries, vector charts, alert and inventory tables, every field in all
15 registers, acknowledgements, standards, settings and uploaded evidence images.
An embedded `project-data.json` attachment preserves original field values and
base64 evidence chunks. External evidence URLs are listed; their remote contents
are not fetched. Time-sensitive metrics use the recorded closure time.

**Delete project** requires the exact code. This is a soft deletion: the project
and its records disappear from normal views and exports, while database records
and revision/audit history remain. Deleted codes cannot be reused. Download any
required closure PDF before deletion. Deleting the last project still allows a
corporate manager or administrator to create another project.

### Upgrade an existing deployment

1. Install the updated `requirements.txt` with Python 3.12 or later.
2. Reapply `supabase/database.sql` in the Supabase SQL Editor **before deploying
   the updated app**. It safely replaces the transactional save function and adds
   database-side closure/deletion guards without dropping data.
3. Run `bootstrap_database.py` to register the additional project fields.
4. Restart the Streamlit app and verify closure plus rejected stale writes against
   a test project in your Supabase deployment.

Local checks include lifecycle permissions, stale edits, atomic batch rejection,
closed-record immutability, deletion visibility, closure-time calculations, PDF
pagination of long values, and lossless project-scoped embedded data.
