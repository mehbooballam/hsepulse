"""Run locally after supabase/database.sql. Reads ignored secrets; never prints keys."""
import tomllib
from pathlib import Path
from supabase_account_store import SupabaseAccountStore
from database_store import DatabaseStore

def configured_store():
 settings=tomllib.loads(Path('.streamlit/secrets.toml').read_text())
 accounts=SupabaseAccountStore(dict(settings['supabase']),settings['application']['encryption_key'])
 return DatabaseStore(accounts)

if __name__=='__main__':
 db=configured_store()
 db.initialize()
 from record_numbers import numbered
 def finish_metadata(doc):
  for table,rows in doc['tables'].items():
   doc['tables'][table]=[numbered(doc,table,r,r) for r in rows]
  if not doc.get('connection',{}).get('spreadsheet_id'):
   for key in ('connection','candidate_google','pending_google'): doc.pop(key,None)
 db.accounts.mutate(finish_metadata)
 tables=db.read()
 print('Database initialized:',sum(len(v) for k,v in tables.items() if k not in ('Users','Invitations','AccessAudit')),'records')
 print('Operational categories:',len(__import__('storage').SCHEMAS))
 print('Existing membership count:',len(tables['Users']))
