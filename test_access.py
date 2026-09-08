import unittest, json
from datetime import datetime,timedelta,timezone
from unittest.mock import patch, Mock
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
 def test_stale_security_snapshot_rejected(self):
  from account_store import AccountStore,OrganizationStore
  from cryptography.fernet import Fernet
  from storage import ConflictError
  db=AccountStore('sqlite:///:memory:',Fernet.generate_key()); raw=OrganizationStore(db)
  service=MembershipService(raw); service.bootstrap(ADMIN,ADMIN['email'])
  stale=raw.read(); service.invite(ADMIN,'one@example.com','Corporate viewer',[])
  with self.assertRaises(ConflictError): service._write({'Invitations':[{'id':'race'}]},stale)
 def test_storage_revalidates_session_during_refresh(self):
  self.member()
  check=Mock(side_effect=AccessDenied('expired'))
  store=AuthorizedStore(self.raw,USER,check)
  with self.assertRaises(AccessDenied): store.read()
  with self.assertRaises(AccessDenied): store.save('03_DAILY_REPORT',[{'id':'x','Project':'P01'}])
 def test_admin_pages(self):
  from streamlit.testing.v1 import AppTest
  at=AppTest.from_file('app.py',default_timeout=60); at.secrets['application']={'enabled':False}; at.run()
  for page in ['Team & access']:
   at.sidebar.radio[0].set_value(page).run(); self.assertFalse(at.exception,page)

if __name__=='__main__': unittest.main()
