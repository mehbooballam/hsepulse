import io
import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from domain import initial_tables, TZ
import enterprise as e
from storage import MemoryStore, ConflictError
from project_lifecycle import close_project, delete_project, visible_tables
from project_report import closure_pdf


class ProjectLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore({**initial_tables(), **e.demo()})
        self.project = self.store.read()['Projects'][0]

    def close(self):
        p = close_project(self.project, self.store.read(), 'manager@example.com', 'Completed. Remaining actions transferred to client.')
        self.store.save('Projects', [p], {p['id']: self.project['revision']})
        return self.store.read()['Projects'][0]

    def test_edit_preserves_id_and_rejects_stale_changes(self):
        p = self.project
        self.store.save('Projects', [{**p, 'name': 'Updated'}], {p['id']: p['revision']})
        self.assertEqual(self.store.read()['Projects'][0]['name'], 'Updated')
        with self.assertRaises(ConflictError):
            self.store.save('Projects', [p], {p['id']: p['revision']})

    def test_closure_locks_existing_new_and_moved_records(self):
        p = self.close()
        for row in [{'id': 'new', 'Project': p['id']}, self.store.read()['03_DAILY_REPORT'][0]]:
            with self.assertRaisesRegex(ValueError, 'read-only'):
                self.store.save('03_DAILY_REPORT', [row])
        old = self.store.read()['03_DAILY_REPORT'][0]
        with self.assertRaisesRegex(ValueError, 'read-only'):
            self.store.save('03_DAILY_REPORT', [{**old, 'Project': 'P02'}], {old['id']: old['revision']})
        with self.assertRaisesRegex(ValueError, 'read-only'):
            self.store.save('Projects', [{**p, 'status': 'Active'}], {p['id']: p['revision']})

    def test_close_and_record_batch_is_atomic(self):
        p = close_project(self.project, self.store.read(), 'Manager', 'Complete')
        before = self.store.read()
        with self.assertRaises(ValueError):
            self.store.save_many({'Projects': [p], 'Evidence': [{'id': 'new', 'project': p['id']}]}, {'Projects': {p['id']: p['revision']}})
        self.assertEqual(before, self.store.read())

    def test_delete_retains_data_but_hides_project_and_all_linked_records(self):
        p = self.close()
        self.store.save('Projects', [delete_project(p, 'Manager')], {p['id']: p['revision']})
        self.assertTrue(self.store.tables['03_DAILY_REPORT'])
        visible = visible_tables(self.store.read())
        self.assertNotIn(p['id'], [r['id'] for r in visible['Projects']])
        self.assertFalse(any(r['Project'] == p['id'] for r in visible['03_DAILY_REPORT']))
        with self.assertRaises(ValueError):
            self.store.save('Projects', [{'id': p['id'], 'name': 'Reused', 'status': 'Active'}])

    def test_closure_requires_notes(self):
        with self.assertRaises(ValueError): close_project(self.project, self.store.read(), 'Manager', '')

    def test_pdf_has_all_registers_and_lossless_scoped_attachment(self):
        from pypdf import PdfReader
        p = self.close()
        tables = self.store.read()
        tables['05_INCIDENTS'].append({'id': 'long', 'Project': p['id'], 'Date': '2026-01-01', 'Description': 'Long field <safe> & text ' * 1200, 'Custom value': 'preserved'})
        reader = PdfReader(io.BytesIO(closure_pdf(tables, p)))
        text = '\n'.join(page.extract_text() for page in reader.pages)
        self.assertIn('Control assurance', text)
        self.assertIn('Custom value', text)
        for label in e.LABELS.values(): self.assertIn(label, text)
        attached = json.loads(reader.attachments['project-data.json'][0])
        self.assertEqual(attached['Projects'][0]['id'], p['id'])
        self.assertTrue(all(r['Project'] == p['id'] for name in e.FORMS for r in attached[name]))
        self.assertNotIn('Users', attached)
        self.assertEqual(attached['05_INCIDENTS'][-1]['Custom value'], 'preserved')

    def test_metrics_use_explicit_closure_time(self):
        tables = self.store.read()
        now = datetime.now(TZ)
        before = e.metrics(tables, now.date() - timedelta(days=30), now.date(), 'P01', now=now)
        with patch('enterprise.today', return_value=now.date() + timedelta(days=1000)):
            after = e.metrics(tables, now.date() - timedelta(days=30), now.date(), 'P01', now=now)
        self.assertEqual(before, after)



class ProjectUITests(unittest.TestCase):
    def test_edit_close_download_and_delete_through_ui(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file('app.py', default_timeout=60)
        at.secrets['application'] = {'enabled': False}
        at.query_params['view'] = 'Project settings'
        at.run()
        self.assertFalse(at.exception)
        def text_input(label, value):
            next(w for w in at.text_input if w.label == label).set_value(value)
        def click(label):
            next(w for w in at.button if w.label == label).click().run()
            self.assertFalse(at.exception)
        text_input('Project name', 'Lifecycle QA project')
        click('Save project')
        next(w for w in at.text_area if w.label == 'Completion and handover notes').set_value('Handover complete; remaining items listed.')
        text_input('Type project code to confirm completion', 'P01')
        click('Complete & close project')
        self.assertTrue(at.success)
        click('Generate closure PDF')
        self.assertTrue(any(w.label == 'Download closed project report (PDF)' for w in at.get('download_button')))
        text_input('Type project code to confirm deletion', 'P01')
        click('Delete project')
        self.assertNotIn('P01', [p['id'] for p in at.session_state['demo_store_v2'].read()['Projects']])


class LifecycleAccessTests(unittest.TestCase):
    def test_only_corporate_managers_and_admins_can_manage_projects(self):
        from access_control import SCHEMAS, MembershipService, AuthorizedStore, AccessDenied
        from test_access import ADMIN, USER
        for role in ['Project lead', 'Project viewer', 'Project manager', 'Corporate viewer', 'Corporate manager']:
            raw = MemoryStore({**initial_tables(), **e.seed(), **{k: [] for k in SCHEMAS}})
            service = MembershipService(raw); service.bootstrap(ADMIN, ADMIN['email'])
            _, token = service.invite(ADMIN, USER['email'], role, ['P01'])
            service.accept(USER, token)
            store = AuthorizedStore(raw, USER)
            old = store.read()['Projects'][0]
            closed = close_project(old, store.read(), USER['email'], 'Complete')
            if role == 'Corporate manager':
                store.save('Projects', [closed], {old['id']: old['revision']})
                self.assertEqual(store.read()['Projects'][0]['status'], 'Closed')
                self.assertEqual(raw.read()['AccessAudit'][-1]['event'], 'records.saved')
            else:
                with self.assertRaises(AccessDenied):
                    store.save('Projects', [closed], {old['id']: old['revision']})

if __name__ == '__main__': unittest.main()
