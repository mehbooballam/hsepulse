# HSE Pulse — organization application

The current rebuild adds verified Google sign-in, email invitations, managed roles,
project assignments, account suspension, access audit history and a master-admin
Google OAuth connection. HSE records stay in Google Sheets. Account metadata and
Google refresh tokens are encrypted in a private PostgreSQL schema. Users never
upload service-account JSON or connect their own spreadsheet.

**Live activation is not complete until the owner configures the platform services.**
Without organization settings the app remains an explicitly labelled, temporary demo.
The previous service-account and static-email configuration below is legacy mode.
Use `.streamlit/organization.secrets.example.toml` for the rebuilt application.

## Master-admin experience

1. Sign in using the bootstrap administrator email configured once by the app owner.
2. Open **Master sheet → Connect Google → Continue to Google**.
3. Authorize Sheets access, then create a new master sheet or select an existing
   Google spreadsheet. Confirm **Set as master sheet**. The app initializes its
   registers and stops if an existing register has incompatible headers. Other tabs
   are preserved. An Excel template must be converted to a native Google spreadsheet;
   its display/dashboard tabs do not become app data without compatible headers.
4. Open **Team & access → Invitations**, enter an email, role and projects, then send.
5. The recipient opens the invitation, signs in with that verified Google email,
   and accepts. If Google's login redirects to the home page, reopening the original
   invitation after sign-in restores the acceptance screen.

Administrators manage users and Google connections. Corporate managers manage HSE
records across projects but cannot grant access or reconnect the master sheet.
Corporate viewers only read; project roles operate within assigned projects.
Authorization is enforced again at the storage boundary, including old record IDs,
exports, writes and dashboard refreshes. Suspended accounts are rejected at the next
request; data already rendered in a browser cannot be recalled. A system cannot
suspend the last active administrator. Invite tokens are random, hashed at rest,
expire in 1–14 days, and can only be used once by the matching verified identity.
Re-inviting invalidates older pending links. No real invitations were sent during development.

## One-time platform setup

Configure the values from `.streamlit/organization.secrets.example.toml` in
Streamlit **Manage app → Settings → Secrets**:

- Google OAuth **Web application** client and a strong OIDC cookie secret.
  Enable Google Sheets API and Google Drive API, configure the OAuth consent screen,
  and register both `https://hsepulse-dashboard.streamlit.app/oauth2callback` (login)
  and `https://hsepulse-dashboard.streamlit.app/` (Google connection). In testing,
  add the relevant Google accounts as test users. Google may require app verification
  for production use of the requested scopes. Test-mode offline grants may expire.
- A persistent PostgreSQL database URL with TLS and a dedicated server-side database
  owner permitted to create `hsepulse_private`. This schema is not for a public REST
  API. The app revokes PUBLIC schema/table access and enables RLS; only the trusted
  server database owner accesses it. Do not expose database credentials to clients.
- A Fernet encryption key generated once with
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
  Keep it in hosting secrets and back it up separately. Losing/changing it without
  migrating ciphertext makes stored connections and memberships unreadable.
- An SMTP provider with TLS and a verified sending address for invitations.
- `bootstrap_admin_email` and the deployed `public_url`.

Google authorization uses state, PKCE, a ten-minute callback deadline, an authenticated
admin binding and one-use state consumption. Offline refresh tokens are encrypted
in PostgreSQL and never placed in the HSE spreadsheet or browser-visible configuration.
The requested scopes permit spreadsheet access and listing spreadsheet metadata;
Google's grant is broader than the selected sheet, while the application limits
operational reads/writes to the configured master sheet. Disconnect removes the app's
stored token; revoke the OAuth grant in Google Account permissions if needed.

## Verification and operational boundaries

Run `.venv/bin/python -m unittest test_app test_enterprise test_access -q`.
Membership changes use database version checks plus a complete security snapshot,
so concurrent changes fail instead of silently overwriting permissions. This build
serves one organization per deployment. PostgreSQL stores the encrypted organization
metadata as one transactional aggregate; high-volume audit retention should be moved
to a dedicated audit store before scaling to many organizations.

Google Sheets operational writes remain subject to Sheets quotas and its lack of
cross-process conditional writes. Keep one application writer process and restrict
manual sheet access to administrators. The database records write intent before a
Sheets mutation and completion afterward; this is not an atomic transaction across
Google and PostgreSQL. A failed completion audit remains a visible write intent.
Live OAuth, SMTP delivery and hosted PostgreSQL require actual provider credentials
for end-to-end verification; local tests use mocks and an encrypted test database.

---

# HSE Pulse

Streamlit dashboard for daily health, safety and environmental performance, with Google Sheets as its only live persistent backend.

## Run

```bash
cd "/Users/mehboobalam/Desktop/HSE Tool"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

Open http://localhost:8501. Without credentials, the app starts in **Demo** mode. Demo changes exist only in that browser session and are not uploaded or persisted to disk.

## Connect Google Sheets

The private workbook connection is configured locally in the git-ignored `backend.json`, through `HSE_SPREADSHEET_ID`, or in Streamlit secrets. Copy `backend.example.json` to `backend.json` and enter your workbook ID and URL.

1. In Google Cloud Console, create/select a project and enable Google Sheets API.
2. Create a service account under IAM & Admin. No project-wide role is needed for this app.
3. Create/download a JSON key and store it outside the repository.
4. Share the workbook with the key's `client_email` as Editor.
5. Set the credential path and restart:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/absolute/path/to/service-account.json"
.venv/bin/streamlit run app.py
```

The workbook ID is already configured. To use another prepared workbook, set `HSE_SPREADSHEET_ID`.
Alternatively, copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` and enter the matching fields. Secrets and common credential filenames are git-ignored. Never commit private keys.

Select **Google Sheets** in the sidebar. The setup page contains the same steps. Codex connector authentication is separate from runtime app authentication.

## Features

- 288 catalogue entries: the 280 discussed KPIs plus 8 operational input/coverage measures.
- 36 daily entry measures and four calculated injury rates configured initially.
- Broader indicators remain clearly marked as draft until their measurement rules are configured.
- Date, site and Day/Night shift filters; trend charts and target status.
- Daily reporting grid, with numerator/denominator definitions beside each field.
- Custom KPI creation, definition activation, ownership, targets and site creation.
- Corrective actions with owner, priority, due date, progress and closure evidence.
- Validated CSV imports; filtered reports and complete current-data ZIP export.
- Missing, zero and not-applicable values distinguished.
- Google Sheets revisions retained for records, definitions, sites and actions.

## Workbook contract

`Definitions`, `Records`, `Actions` and `Sites` store rows with stable IDs and revision metadata. Column names and order are defined in `domain.SCHEMAS`; do not rename tabs or columns. Rows are an **append-only revision log**, not an editable sorted report. The last appended row for an ID is its current state. Do not physically sort or delete log rows; use filter views or the app for reporting. Corrections in the app append a new revision, preserving earlier values.

The workbook starts with definitions and one Main site. Actual records/actions are intentionally empty. Synthetic demo observations are never seeded into it.

The runtime uses the Sheets API only, with spreadsheet scope. Writes use RAW values, preventing user notes from becoming formulas. All rows in an import are validated before one append request. If a save cannot be confirmed, refresh and verify before retrying. A successful write followed by a failed read does not automatically repeat the write.

All sessions served by one Python process share a write lock, and stale row revisions are rejected. Google Sheets has no cross-process compare-and-swap transaction: simultaneous edits from another application/server or direct spreadsheet editing are not covered by the in-process lock. Use one app process for this local workflow. The app reloads data on explicit Refresh or after its own saves; other users' changes are not pushed automatically.

This local build binds to 127.0.0.1 and has no end-user authentication. Before public/team deployment add authentication and access controls. The entered reporter/owner names are labels, not verified identities. The workbook retains all revisions but the downloaded backup contains current rows only. Large histories require archiving or a more scalable storage design.

## Calculation rules

- Sum: total of applicable recorded values. Missing shifts are not silently included as zeros.
- Percentage: sum of numerators / sum of denominators × 100, not an average of percentages.
- Ratio: sum of numerators / sum of denominators.
- Snapshot: latest selected date/shift for each site, then sum across sites. Day precedes Night on the report date. This is not a unique-worker total over a period.
- Explicit N/A requires a reason and blank numeric cells. A 0/0 ratio also displays N/A.
- TRIR / TCIR: recordable injury and illness cases × 200,000 / actual hours.
- DART: unique days-away/restricted/transferred cases × 200,000 / actual hours.
- LTIFR: lost-time injuries × 1,000,000 / actual hours (selected convention).
- Severity: days lost × 1,000,000 / actual hours (selected convention).
- Built-in injury rates are unavailable when numerator and hours do not cover exactly the same site/date/shift keys.
- Daily counts must be incremental shift counts, not cumulative totals. Avoid double-counting a case across shifts. Case classification follows your selected reporting framework.
- Entry coverage is against daily fields within shifts having at least one record. It cannot establish that every expected shift was reported.
- Targets start unset in the live workbook. Demo percentage targets of 95% are illustrative only. Target changes apply retrospectively to displayed periods.
- Calculation rules lock after recording data; create a new indicator when the definition changes.
- Action-register records and daily action KPI reports are separate. A site can report totals covering actions managed outside this app.
- Negative inputs are currently unsupported. For emissions reduction, use a nonnegative decrease measure or track actual emissions separately; negative growth/reduction needs a future signed-value measure.

## Validation

```bash
.venv/bin/python -m unittest test_app -v
```

Tests cover weighted aggregation, N/A vs zero, invalid inputs, matching rate coverage, snapshot aggregation, revision conflict handling, RAW Sheets writes through a mocked adapter, catalogue uniqueness, page rendering, and demo action/daily-entry saves. Live service-account authentication/read/write cannot be verified until credentials are configured. The actual workbook content, headers, all 288 names and header formatting were verified independently through the Google Drive connector. Native Sheets browser verification was blocked at Google account sign-in by automatic approval review.

## Sources

These are configurable company measures, not an official IOSH/OTHM mandatory KPI list.

- OSHA leading indicators: https://www.osha.gov/leading-indicators
- OSHA incidence-rate formula: https://www.osha.gov/laws-regs/standardinterpretations/2016-08-23
- HSE process safety indicators: https://www.hse.gov.uk/pubns/books/hsg254.htm
- gspread authentication: https://docs.gspread.org/en/master/oauth2.html
- Google Sheets RAW values: https://developers.google.com/workspace/sheets/api/guides/values

## Corporate multi-project system (workbook replacement)

Open http://localhost:8501/. The default workspace is now the corporate dashboard, with 15 project dashboards and 15 operational forms. The supplied workbook's 11 registers are preserved, supplemented by stop work, audit, emergency readiness and HSE resource registers. The original Downloads workbook was read without modification. `workbook_reference.json` preserves its field definitions and standards templates.

The actual Google Sheets backend has 24 tabs, including the earlier KPI catalogue. Corporate records live in their own named register tabs. The previous advanced KPI workspace remains separate: its legacy records are not silently merged with corporate register data. Corporate injury rates use the incident register and corporate daily reports. Photo evidence is stored as small base64 chunks in Google Sheets (1 MB maximum per image). Linked actions, photos and a submission save in one Sheets batch. Revisions remain append-only. Run one app process for optimistic concurrency protection; Google Sheets does not provide a cross-process compare-and-swap transaction. Keep backend sheet editing restricted to administrators.

### First use

1. Start with `./start.sh` and explore the clearly labelled temporary demo.
2. Open **Project settings** to rename projects and assign client, location and leads. All 15 original project names are placeholders; operational live registers start empty.
3. Follow **Google Sheets setup** to create a service account, enable Sheets API, share the backend and configure credentials. Credentials have not been supplied, so live runtime storage is not yet connected.
4. Configure OIDC sign-in and the `[access."email"]` sections in `.streamlit/secrets.toml` using the example. Install requirements, which include Streamlit's authentication extra. See [Streamlit authentication](https://docs.streamlit.io/develop/api-reference/user/st.login). Live corporate access fails closed without approved user configuration. Use Corporate manager, Corporate viewer, Project manager, HSE officer, Project lead, or Project viewer. Project roles only read/export/write assigned projects; viewers cannot submit. Corporate feedback creation and administrative settings require Corporate manager.
5. Set the app URL under **Project settings** after hosting on your organization's approved HTTPS server. Each form provides a real project-specific link. Localhost links only work on the machine running the app; they are not public links.
6. Leads submit via **Field forms**; managers use **Operational registers** to review/filter/export and select existing IDs for updates. Daily reports have a stable ID per project/date/shift; submitting that combination revises the report.
7. Managers use **Alerts & decisions** for acknowledgement and corporate instructions, and **Management report** for a printable HTML report and scoped register exports.

### Calculation decisions

The workbook's hardcoded 90% project scores and 100% permit compliance have been removed. The app explicitly labels an internal *control assurance* score: equal weighting across available inspection completion, action closure, permit checks, required-training validity and verified applicable compliance. This is a provisional alternative because the shared conversation's example weighted score does not define normalization rules. Coverage is always displayed, incomplete coverage cannot be green, and critical alerts override score color. This is not an IOSH-endorsed scoring system. Corporate thresholds are configurable. All formulas are explained in the dashboard.

Historical manpower is not summed; the dashboard shows the last shift snapshot per project on the period end date. Hours sum over the selected period. Near misses are separate from incident totals. Daily incident summaries are not added to incident-register cases. Rates require positive hours and an exposure report on each incident's project/date. Closed actions stop ageing and stop being overdue. Reopening suspended work requires recorded controls, closure date and verifier. Permit alerts use Riyadh date/time: 24 hours amber, 4 hours orange, expired red. Current operational controls and alerts are explicitly distinguished from period activity KPIs.

The 17 standards entries are unverified requirement families copied from the source template, not a verified legal compliance catalogue. Reference review and project applicability/evidence must be completed separately.

### Notifications and refresh

Dashboards refresh every 30 seconds while open and show a toast for newly triggered alerts. Acknowledgement persists in Sheets and does not suppress an active safety condition. External WhatsApp, email and Teams delivery is **not enabled**: the Alerts page exports a message preview with stable deduplication keys. Credentials, recipients, delivery authorization and a hosted scheduler are still required for unattended notifications or daily summaries. No external messages have been sent.

### Verification

Run `.venv/bin/python -m unittest test_app test_enterprise -q`. Tests cover all workspace pages and forms, saved submissions, role scope, weighted legacy KPIs, corporate exposure rates, missing-data states, closure clocks, permit expiry, atomic conflict handling and literal Google Sheets input handling.

## Streamlit Community Cloud deployment

Deploy repository `mehbooballam/hsepulse`, branch `main`, main file **`app.py`**. Select Python 3.11 under Advanced settings. `start.sh` is only the local launch script and must not be selected as the cloud entry point. Without secrets the deployed app opens in temporary demo mode. Configure the Google service account and OIDC access settings in Streamlit's Secrets interface to enable live project records.

The shared theme configuration leaves network binding to the hosting platform. The local `start.sh` explicitly binds to 127.0.0.1. Default dashboard links automatically follow the deployed app URL.
