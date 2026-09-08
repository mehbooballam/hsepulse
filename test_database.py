import io,json,re,unittest,zipfile
from types import SimpleNamespace as NS
from unittest.mock import Mock
from cryptography.fernet import Fernet
from database_store import DatabaseStore
from storage import MemoryStore,SCHEMAS,ConflictError
from domain import initial_tables
from enterprise import seed,REF
from export_ui import archive_bytes,display_frame
from account_store import AccountStore

class DatabaseTests(unittest.TestCase):
 def test_every_workbook_input_field_is_registered(self):
  for category,definition in REF['forms'].items():
   self.assertTrue(set(definition['headers'][1:]) <= set(SCHEMAS[category]),category)
 def test_ids_keep_category_sequence_timestamp_and_survive_edit(self):
  db=MemoryStore({**initial_tables(),**seed()})
  db.save('05_INCIDENTS',[{'id':'stable','Description':'A'}])
  first=db.read()['05_INCIDENTS'][0]
  self.assertRegex(first['Record ID'],r'^INCIDENTS-000001-\d{8}T\d{12}Z$')
  db.save('05_INCIDENTS',[{'id':'stable','Description':'B'}],{'stable':first['revision']})
  second=db.read()['05_INCIDENTS'][0]
  self.assertEqual(first['Record ID'],second['Record ID'])
  self.assertEqual(first['Created at'],second['Created at'])
  db.save('05_INCIDENTS',[{'id':'next'}])
  self.assertEqual(db.read()['05_INCIDENTS'][1]['Entry sequence'],2)
 def test_exports_include_empty_headers_and_extra_fields(self):
  rows={'05_INCIDENTS':[{'id':'a','Record ID':'INCIDENTS-000001-TIME','Description':'=1+1','Custom field':'retained'}],'03_DAILY_REPORT':[]}
  with zipfile.ZipFile(io.BytesIO(archive_bytes(rows))) as z:
   self.assertIn('Man-hours',z.read('03_DAILY_REPORT.csv').decode('utf-8-sig'))
   self.assertIn("'=1+1",z.read('05_INCIDENTS.csv').decode('utf-8-sig'))
   self.assertEqual(json.loads(z.read('05_INCIDENTS.json'))[0]['Custom field'],'retained')
 def test_pagination_does_not_truncate_at_api_limit(self):
  accounts=Mock();accounts.read.return_value={}
  query=accounts.api.table.return_value.select.return_value.order.return_value.order.return_value
  query.range.return_value.execute.side_effect=[NS(data=[{'category':'Records','data':{'id':str(i)}} for i in range(500)]),NS(data=[{'category':'Records','data':{'id':'last'}}])]
  self.assertEqual(len(DatabaseStore(accounts).read()['Records']),501)
  self.assertEqual(query.range.call_args.args,(500,999))
 def test_security_change_prevents_operational_rpc(self):
  accounts=AccountStore('sqlite:///:memory:',Fernet.generate_key());accounts.api=Mock()
  accounts._row=lambda:{'version':1,'payload':accounts.encode(accounts.document())}
  with self.assertRaises(ConflictError): DatabaseStore(accounts).save_many({'Records':[{'id':'a'}]},{'_security_snapshot':'stale'})
  accounts.api.rpc.assert_not_called()
if __name__=='__main__': unittest.main()
