import unittest, json
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from copy import deepcopy
from domain import initial_tables
from enterprise import seed
from storage import MemoryStore
from access_control import *

ADMIN={'email':'admin@example.com','email_verified':True,'sub':'admin-sub','iss':'https://accounts.google.com','name':'Admin'}
USER={'email':'lead@example.com','email_verified':True,'sub':'lead-sub','iss':'https://accounts.google.com','name':'Lead'}
class AccessTests(unittest.TestCase):
 def setUp(self):
  self.raw=MemoryStore({**initial_tables(),**seed(),**{k:[] for k in SCHEMAS}})
  self.service=MembershipService(self.raw); self.service.bootstrap(ADMIN,ADMIN['email'])
 def member(self):
  i,token=self.service.invite(ADMIN,USER['email'],'Project lead',['P01']); self.service.accept(USER,token); return principal(self.raw.read(),USER)
 def test_invite_bound_email_single_use(self):
  i,token=self.service.invite(ADMIN,USER['email'],'Project lead',['P01'])
  self.assertNotIn(token,json.dumps(self.raw.read()))
  with self.assertRaises(AccessDenied): self.service.accept({**USER,'email':'wrong@example.com'},token)
  with self.assertRaises(AccessDenied): self.service.accept({**USER,'email_verified':False},token)
  self.service.accept(USER,token)
  with self.assertRaises(AccessDenied): self.service.accept(USER,token)
 def test_expired_and_revoked(self):
  inv,token=self.service.invite(ADMIN,USER['email'],'Project lead',['P01'])
  stored=self.raw.read()['Invitations'][0]
  self.raw.save('Invitations',[{**stored,'expires_at':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()}],{stored['id']:stored['revision']})
  with self.assertRaises(AccessDenied): self.service.accept(USER,token)
  inv,token=self.service.invite(ADMIN,USER['email'],'Project lead',['P01']); self.service.revoke(ADMIN,inv['id'])
  with self.assertRaises(AccessDenied): self.service.accept(USER,token)
 def test_role_change_and_suspension_are_immediate(self):
  user=self.member(); store=AuthorizedStore(self.raw,USER)
  self.assertEqual([p['id'] for p in store.read()['Projects']],['P01'])
  self.service.change_user(ADMIN,user['id'],'Project viewer',['P02'],'Active')
  self.assertEqual([p['id'] for p in store.read()['Projects']],['P02'])
  with self.assertRaises(AccessDenied): store.save('03_DAILY_REPORT',[{'id':'a','Project':'P02'}])
  self.service.change_user(ADMIN,user['id'],'Project viewer',['P02'],'Suspended')
  with self.assertRaises(AccessDenied): store.read()
 def test_existing_id_cross_project_and_escalation(self):
  self.member(); self.raw.save('03_DAILY_REPORT',[{'id':'other','Project':'P02'}]); store=AuthorizedStore(self.raw,USER)
  with self.assertRaises(AccessDenied): store.save('03_DAILY_REPORT',[{'id':'other','Project':'P01'}])
  with self.assertRaises(AccessDenied): store.save('Users',[{'id':'admin','role':'Administrator'}])
  with self.assertRaises(AccessDenied): self.service.invite(USER,'evil@example.com','Administrator',[])
 def test_last_admin(self):
  user=principal(self.raw.read(),ADMIN)
  with self.assertRaises(ValueError): self.service.change_user(ADMIN,user['id'],'Corporate viewer',[],'Active')
  with self.assertRaises(ValueError): self.service.change_user(ADMIN,user['id'],'Administrator',[],'Suspended')
 def test_principal_requires_subject_issuer_and_verification(self):
  for claims in ({**ADMIN,'sub':'other'},{**ADMIN,'iss':'other'},{k:v for k,v in ADMIN.items() if k!='email_verified'}):
   with self.assertRaises(AccessDenied): principal(self.raw.read(),claims)
 def test_new_invite_invalidates_old(self):
  _,old=self.service.invite(ADMIN,USER['email'],'Project lead',['P01'])
  _,new=self.service.invite(ADMIN,USER['email'],'Project viewer',['P02'])
  with self.assertRaises(AccessDenied): self.service.accept(USER,old)
  self.service.accept(USER,new); self.assertEqual(principal(self.raw.read(),USER)['role'],'Project viewer')
 def test_account_store_encryption_and_conflict(self):
  from account_store import AccountStore
  from cryptography.fernet import Fernet
  from storage import ConflictError
  db=AccountStore('sqlite:///:memory:',Fernet.generate_key())
  db.save('Users',[{'id':'one','email':'private@example.com'}]); row=db.read()['Users'][0]
  with db.engine.connect() as conn:
   payload=conn.execute(db.table.select()).mappings().one()['payload']; self.assertNotIn('private@example.com',payload)
  with self.assertRaises(ConflictError): db.save('Users',[row],{})
 def test_oauth_state_and_master_admin_only(self):
  import google_connection as gc
  from account_store import AccountStore,OrganizationStore
  from cryptography.fernet import Fernet
  db=AccountStore('sqlite:///:memory:',Fernet.generate_key()); svc=MembershipService(OrganizationStore(db)); svc.bootstrap(ADMIN,ADMIN['email'])
  config={'client_id':'client','client_secret':'secret','redirect_uri':'https://app.example.com/'}
  url=gc.begin(db,ADMIN,config); self.assertIn('code_challenge=',url)
  with self.assertRaises(AccessDenied): gc.complete(db,ADMIN,config,'wrong','fake')
  self.assertTrue(db.document()['pending_google'])
 def test_stale_security_snapshot_rejected(self):
  from account_store import AccountStore,OrganizationStore
  from cryptography.fernet import Fernet
  from storage import ConflictError
  db=AccountStore('sqlite:///:memory:',Fernet.generate_key()); raw=OrganizationStore(db)
  service=MembershipService(raw); service.bootstrap(ADMIN,ADMIN['email'])
  stale=raw.read(); service.invite(ADMIN,'one@example.com','Corporate viewer',[])
  with self.assertRaises(ConflictError): service._write({'Invitations':[{'id':'race'}]},stale)
 def test_google_initialization_rejects_incompatible_tab(self):
  from unittest.mock import Mock
  from google_connection import initialize
  book=Mock(); worksheet=Mock(); worksheet.title='Projects'; worksheet.row_values.return_value=['wrong header']; book.worksheets.return_value=[worksheet]
  with self.assertRaises(ValueError): initialize(book)
  book.add_worksheet.assert_not_called(); worksheet.update.assert_not_called()
 def test_google_callback_is_one_use_and_encrypted(self):
  import google_connection as gc
  from account_store import AccountStore,OrganizationStore
  from cryptography.fernet import Fernet
  from unittest.mock import Mock
  from urllib.parse import urlparse,parse_qs
  db=AccountStore('sqlite:///:memory:',Fernet.generate_key()); svc=MembershipService(OrganizationStore(db)); svc.bootstrap(ADMIN,ADMIN['email'])
  config={'client_id':'client','client_secret':'secret','redirect_uri':'https://app.example.com/'}
  state=parse_qs(urlparse(gc.begin(db,ADMIN,config)).query)['state'][0]
  oauth=Mock(); oauth.credentials.refresh_token='private-refresh'; oauth.credentials.to_json.return_value=json.dumps({'refresh_token':'private-refresh'})
  with patch.object(gc,'flow',return_value=oauth): gc.complete(db,ADMIN,config,state,'code')
  self.assertEqual(db.document()['candidate_google']['credentials']['refresh_token'],'private-refresh')
  with self.assertRaises(AccessDenied): gc.complete(db,ADMIN,config,state,'code')
  with db.engine.connect() as c: self.assertNotIn('private-refresh',c.execute(db.table.select()).mappings().one()['payload'])
 def test_admin_pages(self):
  from streamlit.testing.v1 import AppTest
  at=AppTest.from_file('app.py',default_timeout=60).run()
  for page in ['Team & access','Master sheet']:
   at.sidebar.radio[1].set_value(page).run(); self.assertFalse(at.exception,page)

if __name__=='__main__': unittest.main()
