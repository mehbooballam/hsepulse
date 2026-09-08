import unittest
from streamlit.testing.v1 import AppTest
from ui_shell import allowed_pages

class NavigationTests(unittest.TestCase):
 def test_viewer_navigation_omits_write_and_admin_pages(self):
  pages=allowed_pages('Project viewer')
  for page in ['Team & access','Project settings','Field forms','Daily entry']:
   self.assertNotIn(page,pages)
  self.assertIn('Data & export',pages)
 def test_deep_link_and_click_navigation(self):
  at=AppTest.from_file('app.py',default_timeout=60)
  at.secrets['application']={'enabled':False}
  at.query_params['view']='KPI register'
  at.run()
  self.assertFalse(at.exception)
  self.assertEqual(at.button(key='nav_KPI register').proto.type,'primary')
  at.button(key='nav_Data & export').click().run()
  self.assertFalse(at.exception)
  self.assertEqual(at.button(key='nav_Data & export').proto.type,'primary')
  self.assertTrue(any(x.value=='Data & export' for x in at.title))
 def test_reports_backup_with_account_tables(self):
  at=AppTest.from_file('app.py',default_timeout=60)
  at.secrets['application']={'enabled':False}
  at.run()
  at.button(key='nav_Team & access').click().run()
  self.assertIn('Users',at.session_state['demo_store_v2'].read())
  at.button(key='nav_Reports & export').click().run()
  self.assertFalse(at.exception)
  self.assertTrue(any(x.value=='Records and backups' for x in at.subheader))
  self.assertTrue(any(x.label=='Download all current data (ZIP)' for x in at.get('download_button')))

if __name__=='__main__': unittest.main()
