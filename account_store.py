"""Encrypted server-only organization metadata; PostgreSQL for hosted deployments."""
import json, hashlib
from copy import deepcopy
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, Text, select, update, insert, text
from sqlalchemy.exc import IntegrityError
from domain import uid, stamp
from access_control import SCHEMAS

class AccountStore:
 def __init__(self,url,key):
  self.cipher=Fernet(key.encode() if isinstance(key,str) else key)
  if url.startswith('postgresql://'): url=url.replace('postgresql://','postgresql+psycopg://',1)
  self.engine=create_engine(url,pool_pre_ping=True)
  schema='hsepulse_private' if self.engine.dialect.name=='postgresql' else None
  if schema:
   with self.engine.begin() as c:
    c.execute(text('CREATE SCHEMA IF NOT EXISTS hsepulse_private'))
    c.execute(text('REVOKE ALL ON SCHEMA hsepulse_private FROM PUBLIC'))
  self.table=Table('organization',MetaData(),Column('id',String(64),primary_key=True),Column('version',Integer,nullable=False),Column('payload',Text,nullable=False),schema=schema)
  self.table.metadata.create_all(self.engine)
  if schema:
   with self.engine.begin() as c:
    c.execute(text('ALTER TABLE hsepulse_private.organization ENABLE ROW LEVEL SECURITY'))
    c.execute(text('REVOKE ALL ON hsepulse_private.organization FROM PUBLIC'))
  try:
   with self.engine.begin() as c: c.execute(insert(self.table).values(id='primary',version=1,payload=self.encode({'tables':{k:[] for k in SCHEMAS},'connection':{},'pending_google':{}})))
  except IntegrityError: pass
 def encode(self,value): return self.cipher.encrypt(json.dumps(value).encode()).decode()
 def decode(self,value): return json.loads(self.cipher.decrypt(value.encode()))
 def document(self):
  with self.engine.connect() as c: return self.decode(c.execute(select(self.table.c.payload).where(self.table.c.id=='primary')).scalar_one())
 def mutate(self,fn):
  from storage import ConflictError
  with self.engine.begin() as c:
   row=c.execute(select(self.table).where(self.table.c.id=='primary').with_for_update()).mappings().one()
   doc=self.decode(row['payload']); result=fn(doc)
   changed=c.execute(update(self.table).where(self.table.c.id=='primary',self.table.c.version==row['version']).values(version=row['version']+1,payload=self.encode(doc)))
   if changed.rowcount!=1: raise ConflictError('Organization changed. Refresh and retry.')
   return result
 def read(self): return self.document()['tables']
 def save_many(self,changes,expected):
  from storage import check_conflicts
  def apply(doc):
   if expected.get('_security_snapshot') and expected['_security_snapshot']!=hashlib.sha256(json.dumps(doc['tables'],sort_keys=True).encode()).hexdigest():
    from storage import ConflictError
    raise ConflictError('Account permissions changed. Refresh and retry.')
   for table,rows in changes.items():
    current={r['id']:r for r in doc['tables'][table]}; check_conflicts(current,rows,expected.get(table,{}))
    for row in rows: current[row['id']]={**deepcopy(row),'revision':uid(),'updated_at':stamp()}
    doc['tables'][table]=list(current.values())
  self.mutate(apply)
 def save(self,table,rows,expected=None): self.save_many({table:rows},{table:expected or {}})

class OrganizationStore:
 """Compose protected memberships with operational Google Sheets records."""
 def __init__(self,accounts,sheets=None): self.accounts=accounts; self.sheets=sheets
 def read(self):
  from domain import initial_tables
  from enterprise import seed
  ops=self.sheets.read() if self.sheets else {**initial_tables(),**seed()}
  return {**ops,**self.accounts.read()}
 def save_many(self,changes,expected):
  security={k:v for k,v in changes.items() if k in SCHEMAS}
  operational={k:v for k,v in changes.items() if k not in SCHEMAS}
  if operational:
   if not self.sheets: raise ValueError('The master administrator must connect a master sheet first.')
   # Audit intent before the external write; no claim of a cross-service transaction.
   if security:
    intent={k:[{**r,'event':'records.save_requested'} for r in rows] if k=='AccessAudit' else rows for k,rows in security.items()}
    self.accounts.save_many(intent,expected)
   self.sheets.save_many(operational,expected)
  if security and not operational:
   self.accounts.save_many(security,expected)
  elif security:
   current=self.accounts.read()
   self.accounts.save_many(security,{k:{r['id']:r.get('revision','') for r in current[k]} for k in security})
 def save(self,table,rows,expected=None): self.save_many({table:rows},{table:expected or {}})
