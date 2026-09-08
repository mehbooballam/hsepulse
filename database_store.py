"""Supabase records, atomic revision checks, category numbering and audit writes."""
from copy import deepcopy
import hashlib
import json
from postgrest.exceptions import APIError
from access_control import SCHEMAS as ACCOUNT_SCHEMAS
from storage import SCHEMAS, ConflictError, check_conflicts
from domain import initial_tables, uid, stamp
from enterprise import seed, LABELS
from record_numbers import numbered

class DatabaseStore:
 def __init__(self, accounts):
  self.accounts = accounts
  self.api = accounts.api

 def read(self):
  tables = {k: [] for k in SCHEMAS}
  offset = 0
  while True:
   rows = self.api.table('hsepulse_records').select('category,data').order('category').order('id').range(offset,offset+499).execute().data
   for row in rows:
    tables.setdefault(row['category'], []).append(row['data'])
   if len(rows) < 500: break
   offset += 500
  return {**tables, **self.accounts.read()}

 def save(self, table, rows, expected=None):
  return self.save_many({table: rows}, {table: expected or {}})

 def save_many(self, changes, expected):
  unknown=set(changes)-set(SCHEMAS)-set(ACCOUNT_SCHEMAS)
  if unknown: raise ValueError('Unknown register: '+', '.join(sorted(unknown)))
  operational = {k: v for k,v in changes.items() if k not in ACCOUNT_SCHEMAS}
  if not operational: return self.accounts.save_many(changes, expected)
  snapshot = self.accounts._row()
  doc = self.accounts.decode(snapshot['payload'])
  security_hash = hashlib.sha256(json.dumps(doc['tables'],sort_keys=True).encode()).hexdigest()
  if expected.get('_security_snapshot') and expected['_security_snapshot'] != security_hash:
   raise ConflictError('Access changed. Refresh and retry.')
  for table, rows in changes.items():
   if table not in ACCOUNT_SCHEMAS: continue
   current = {r['id']: r for r in doc['tables'][table]}
   check_conflicts(current, rows, expected.get(table, {}))
   for row in rows: current[row['id']] = {**numbered(doc,table,deepcopy(row),current.get(row['id'])), 'revision': uid(), 'updated_at': stamp()}
   doc['tables'][table] = list(current.values())
  try:
   return self.api.rpc('hsepulse_save_records', {
    'changes': operational, 'expected': {k:v for k,v in expected.items() if k in operational},
    'organization_version': snapshot['version'], 'organization_payload': self.accounts.encode(doc)
   }).execute().data
  except APIError as exc:
   if exc.code == '40001': raise ConflictError('Records or permissions changed. Refresh and retry.') from exc
   raise

 def initialize(self):
  """Idempotent seed: keep every existing row and populate empty schema fields."""
  categories=[{'category':k, 'label':LABELS.get(k,k), 'fields':v} for k,v in SCHEMAS.items()]
  self.api.table('hsepulse_categories').upsert(categories,on_conflict='category').execute()
  current=self.read()
  defaults={**initial_tables(),**seed()}
  changes={k:[r for r in rows if r['id'] not in {old['id'] for old in current[k]}] for k,rows in defaults.items()}
  changes={k:v for k,v in changes.items() if v}
  if changes: self.save_many(changes,{k:{} for k in changes})
