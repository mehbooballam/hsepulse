import unittest
from datetime import timedelta, datetime
from unittest.mock import Mock
import enterprise as e
from domain import today, initial_tables, TZ
from storage import MemoryStore, GoogleSheetsStore, ConflictError
from streamlit.testing.v1 import AppTest

class EnterpriseTests(unittest.TestCase):
 def test_no_fake_green(self):
  m=e.metrics(e.seed(),today(),today()); self.assertIsNone(m['Score']); self.assertEqual(m['Status'],'Gray')
 def test_snapshot_and_rates(self):
  t=e.seed(); t['03_DAILY_REPORT']=[{'id':'x','Project':'P01','Date':str(today()),'Manpower':10,'Man-hours':100,'Shift':'Day'},{'id':'y','Project':'P01','Date':str(today()-timedelta(days=1)),'Manpower':20,'Man-hours':200,'Shift':'Day'}]
  t['05_INCIDENTS']=[{'id':'i','Project':'P01','Date':str(today()),'Incident Type':'LTI','Status':'Closed'}]
  m=e.metrics(t,today()-timedelta(days=1),today()); self.assertEqual(m['Manpower (end date)'],10); self.assertAlmostEqual(m['TRIR'],200000/300)
 def test_closed_clock_and_reopening(self):
  r={'Date Raised':str(today()-timedelta(days=10)),'Due Date':str(today()-timedelta(days=5)),'Closure Date':str(today()-timedelta(days=2)),'Status':'Closed'}
  self.assertEqual(e.days_open(r),8); self.assertFalse(e.overdue(r))
  with self.assertRaises(ValueError): e.validate('StopWork',{'Project':'P01','actor':'a','Status':'Reopened','Closure Date':str(today())},['P01'])
 def test_permissions(self):
  self.assertFalse(e.permitted('Project lead',['P01'],'P02','03_DAILY_REPORT',True))
  self.assertFalse(e.permitted('Project lead',['P01'],'P01','13_CORP_FEEDBACK',True))
  self.assertFalse(e.permitted('Corporate viewer',[],'P01','03_DAILY_REPORT',True))
  self.assertTrue(e.permitted('Project manager',['P01'],'P01','03_DAILY_REPORT',True))
 def test_atomic_conflict(self):
  store=MemoryStore(e.seed()); r={'id':'a','Project':'P01'}; store.save('08_ACTIONS',[r]); before=store.read()
  with self.assertRaises(ConflictError): store.save_many({'03_DAILY_REPORT':[{'id':'d'}],'08_ACTIONS':[r]}, {})
  self.assertEqual(store.read(),before)
 def test_expiry_boundaries(self):
  t=e.seed(); now=datetime.now(TZ)
  t['06_PERMITS']=[{'id':'p','Project':'P01','Status':'Active','Expiry Date':now.isoformat()}]
  self.assertTrue(any(a['Level']=='Red' and a['Record']=='p' for a in e.alerts(t,now)))
 def test_all_pages_forms_and_scopes(self):
  at=AppTest.from_file('app.py',default_timeout=60); at.secrets['application']={'enabled':False}; at.run()
  for page in ['Corporate dashboard','Project dashboards','Field forms','Operational registers','Alerts & decisions','Standards library','Management report','Project settings']:
   at.button(key='nav_'+page).click().run(); self.assertFalse(at.exception,page)
  at.button(key='nav_'+'Field forms').click().run()
  for table in e.FORMS:
   next(x for x in at.selectbox if x.label=='Report type').set_value(table).run(); self.assertFalse(at.exception,table)
  next(x for x in at.selectbox if x.label=='Report type').set_value('04_OBSERVATIONS').run()
  next(x for x in at.text_input if x.label=='Description').set_value('Test observation')
  next(x for x in at.button if x.label=='Save report').click().run(); self.assertFalse(at.exception); self.assertTrue(at.success)
  self.assertEqual(len(at.session_state['demo_store_v2'].read()['04_OBSERVATIONS']),1)
  at.button(key='nav_'+'Corporate dashboard').click().run()
  next(x for x in at.selectbox if x.label=='Role').set_value('Project lead').run()
  self.assertFalse(at.exception)
  at.button(key='nav_'+'Project dashboards').click().run()
  self.assertEqual(next(x for x in at.selectbox if x.label=='Project').options,['Project 01'])

if __name__=='__main__': unittest.main()
