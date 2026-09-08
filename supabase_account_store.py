"""Encrypted organization metadata through Supabase's API, server key only.

The version predicate is an atomic compare-and-swap across app processes.
No database password or separate PostgreSQL host is needed by the application.
"""
from cryptography.fernet import Fernet
from postgrest.exceptions import APIError
from account_store import AccountStore
from access_control import SCHEMAS
from supabase_login import client
from storage import ConflictError

class SupabaseAccountStore(AccountStore):
 def __init__(self,config,key):
  self.cipher=Fernet(key.encode() if isinstance(key,str) else key)
  self.api=client(config,admin=True)
  if not self._row():
   try:
    self.api.table('hsepulse_organization').insert({'id':'primary','version':1,'payload':self.encode({'tables':{k:[] for k in SCHEMAS},'connection':{},'pending_google':{}})}).execute()
   except APIError as exc:
    if exc.code!='23505': raise
 def _row(self):
  rows=self.api.table('hsepulse_organization').select('id,version,payload').eq('id','primary').execute().data
  return rows[0] if rows else None
 def document(self):
  row=self._row()
  if not row: raise ValueError('Organization data is missing.')
  return self.decode(row['payload'])
 def mutate(self,fn):
  row=self._row()
  if not row: raise ValueError('Organization data is missing.')
  doc=self.decode(row['payload']); result=fn(doc)
  rows=self.api.table('hsepulse_organization').update({'version':row['version']+1,'payload':self.encode(doc)}).eq('id','primary').eq('version',row['version']).execute().data
  if len(rows)!=1: raise ConflictError('Organization changed. Refresh and retry.')
  return result
