"""Project administration and closure report downloads."""
import re
import streamlit as st
from project_lifecycle import close_project, delete_project


def render_projects(store, tables, projects, role, actor):
    can_manage = role in ('Administrator', 'Corporate manager')
    st.title('Projects & access')
    st.dataframe([{k: v for k, v in p.items() if k != 'closure_context'} for p in projects], hide_index=True, width='stretch')
    if projects:
        code = st.selectbox('Manage project', [p['id'] for p in projects],
                            format_func=lambda value: next(p['name'] + ' · ' + p.get('status', 'Active') for p in projects if p['id'] == value))
        old = next(p for p in projects if p['id'] == code)
        def persist(row):
            store.save('Projects', [row], {code: old.get('revision', '')})
            st.rerun()
        if old.get('status') == 'Closed':
            st.success(f"Completed and closed on {old.get('closed_at', '')} by {old.get('closed_by', '')}")
            st.write(old.get('closure_notes', ''))
            st.caption('The closure report includes all saved project records, outstanding items, and uploaded evidence. External evidence links are listed as references.')
            render_closure_download(store, code)
        elif can_manage:
            with st.form('edit_project_' + code):
                row = {**old, 'actor': actor}
                for key, label in [('name', 'Project name'), ('client', 'Client / owner'), ('location', 'Location'), ('lead', 'Project lead'), ('hse_lead', 'HSE lead')]:
                    row[key] = st.text_input(label, old.get(key, ''))
                choices = ['Active', 'Inactive', 'On Hold']
                row['status'] = st.selectbox('Project status', choices, index=choices.index(old.get('status', 'Active')))
                if st.form_submit_button('Save project'):
                    try: persist(row)
                    except ValueError as exc: st.error(str(exc))
            with st.expander('Complete & close project'):
                st.warning('Closing makes this project and its records read-only. Unresolved items remain in the report and must be documented in the handover notes.')
                with st.form('close_project_' + code):
                    notes = st.text_area('Completion and handover notes')
                    confirmation = st.text_input('Type project code to confirm completion')
                    if st.form_submit_button('Complete & close project', type='primary'):
                        try:
                            if confirmation != code: raise ValueError('Enter the exact project code to confirm.')
                            persist(close_project(old, tables, actor, notes))
                        except ValueError as exc: st.error(str(exc))
        if can_manage:
            with st.expander('Delete project'):
                st.warning('This removes the project and its records from normal views. Stored records and audit history are retained; the project code cannot be reused. Download the closure report first if needed.')
                with st.form('delete_project_' + code):
                    confirmation = st.text_input('Type project code to confirm deletion')
                    if st.form_submit_button('Delete project'):
                        try:
                            if confirmation != code: raise ValueError('Enter the exact project code to confirm.')
                            persist(delete_project(old, actor))
                        except ValueError as exc: st.error(str(exc))
    if can_manage:
        with st.expander('Add another project', expanded=not projects):
            with st.form('new_project'):
                code = st.text_input('New project code', placeholder='P16').strip()
                name = st.text_input('New project name').strip()
                if st.form_submit_button('Create project'):
                    try:
                        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', code) or not name:
                            raise ValueError('Enter a name and a code using 1–64 letters, numbers, hyphens or underscores.')
                        store.save('Projects', [{'id': code, 'name': name, 'status': 'Active', 'client': '', 'location': '', 'lead': '', 'hse_lead': '', 'target': 90, 'actor': actor}], {})
                        st.rerun()
                    except ValueError as exc: st.error(str(exc))
    else:
        st.info('Administrators and corporate managers can edit, close or delete projects.')


def render_closure_download(store, code):
    if st.button('Generate closure PDF', type='primary'):
        try:
            from project_report import closure_pdf
            fresh = store.read()
            current = next(p for p in fresh['Projects'] if p['id'] == code)
            with st.spinner('Building complete project report…'):
                pdf = closure_pdf(fresh, current)
            st.download_button('Download closed project report (PDF)', pdf,
                               re.sub(r'[^A-Za-z0-9_-]', '_', code) + '-closure-report.pdf', 'application/pdf')
        except Exception as exc:
            st.error(f'Could not generate report: {exc}')
