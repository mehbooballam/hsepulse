"""Master-admin Google authorization with server-persisted, one-use PKCE state."""
import hashlib, hmac, secrets, json
from datetime import datetime, timedelta, timezone
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import AuthorizedSession
import gspread
from access_control import principal, AccessDenied, audit
SCOPES=['https://www.googleapis.com/auth/spreadsheets','https://www.googleapis.com/auth/drive.metadata.readonly']

def require_admin(doc,claims):
 u=principal(doc['tables'],claims)
 if u['role']!='Administrator': raise AccessDenied('Only the master administrator can connect Google Sheets.')
 return u

def flow(config,state=None,verifier=None):
 return Flow.from_client_config({'web':{'client_id':config['client_id'],'client_secret':config['client_secret'],'auth_uri':'https://accounts.google.com/o/oauth2/auth','token_uri':'https://oauth2.googleapis.com/token'}},scopes=SCOPES,state=state,code_verifier=verifier,redirect_uri=config['redirect_uri'])

def begin(accounts,claims,config):
 state=secrets.token_urlsafe(32); verifier=secrets.token_urlsafe(64)
 def save(doc):
  u=require_admin(doc,claims)
  doc['pending_google']={'hash':hashlib.sha256(state.encode()).hexdigest(),'verifier':verifier,'user_id':u['id'],'expires':(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat()}
 accounts.mutate(save)
 url,_=flow(config,state,verifier).authorization_url(access_type='offline',prompt='consent',login_hint=claims['email'])
 return url

def complete(accounts,claims,config,state,code):
 def consume(doc):
  u=require_admin(doc,claims); pending=doc.get('pending_google',{})
  if not pending or pending['user_id']!=u['id'] or not hmac.compare_digest(pending['hash'],hashlib.sha256(state.encode()).hexdigest()) or datetime.fromisoformat(pending['expires'])<=datetime.now(timezone.utc): raise AccessDenied('Google connection request expired or is invalid. Start again.')
  doc['pending_google']={}; return pending['verifier']
 verifier=accounts.mutate(consume)
 oauth=flow(config,state,verifier); oauth.fetch_token(code=code)
 if not oauth.credentials.refresh_token: raise ValueError('Offline access was not granted. Reconnect Google and approve the requested access.')
 token=json.loads(oauth.credentials.to_json())
 def save(doc):
  u=require_admin(doc,claims)
  # Stage reconnect until admin chooses and verifies a sheet; old backend stays available.
  doc['candidate_google']={'credentials':token,'connected_by':u['email']}
 accounts.mutate(save)

def authorized(accounts,candidate=False):
 doc=accounts.document(); c=doc.get('candidate_google' if candidate else 'connection',{})
 if not c.get('credentials'): raise ValueError('Connect Google first.')
 return Credentials.from_authorized_user_info(c['credentials'],scopes=SCOPES)

def list_sheets(accounts):
 session=AuthorizedSession(authorized(accounts,True)); files=[]; page=None
 while True:
  params={'q':"mimeType='application/vnd.google-apps.spreadsheet' and trashed=false",'fields':'nextPageToken,files(id,name)','pageSize':100}
  if page: params['pageToken']=page
  response=session.get('https://www.googleapis.com/drive/v3/files',params=params,timeout=20); response.raise_for_status(); payload=response.json(); files+=payload.get('files',[]); page=payload.get('nextPageToken')
  if not page: break
 return files

def initialize(book):
 from domain import SCHEMAS, initial_tables
 from enterprise import seed
 from storage import column_name
 tables={**initial_tables(),**seed()}; existing={w.title:w for w in book.worksheets()}
 # Validate existing tabs before adding anything. Never reinterpret a user workbook silently.
 for name,cols in SCHEMAS.items():
  if name in existing:
   head=existing[name].row_values(1)
   if head and head!=cols: raise ValueError(f'{name} has incompatible headers. Choose a blank spreadsheet or create a new master sheet.')
 for name,cols in SCHEMAS.items():
  w=existing.get(name) or book.add_worksheet(name,1000,max(26,len(cols)))
  if not w.row_values(1):
   rows=[cols]+[[r.get(k,'') if r.get(k) is not None else '' for k in cols] for r in tables.get(name,[])]
   w.update(rows,range_name=f'A1:{column_name(len(cols))}{len(rows)}',value_input_option='RAW'); w.freeze(rows=1)

def choose(accounts,claims,sheet_id=None,title=None):
 require_admin(accounts.document(),claims)
 client=gspread.authorize(authorized(accounts,True))
 book=client.create(title) if title else client.open_by_key(sheet_id)
 initialize(book)
 def save(doc):
  u=require_admin(doc,claims); candidate=doc.get('candidate_google')
  if not candidate: raise ValueError('Reconnect Google before selecting a master sheet.')
  doc['connection']={**candidate,'spreadsheet_id':book.id,'title':book.title,'url':book.url}
  doc.pop('candidate_google',None)
  from domain import uid,stamp
  doc['tables']['AccessAudit'].append({**audit('master_sheet.connected',book.id,u['email'],book.title),'revision':uid(),'updated_at':stamp()})
 accounts.mutate(save); return book

def operational_store(accounts):
 from storage import GoogleSheetsStore
 doc=accounts.document(); connection=doc.get('connection',{})
 if not connection.get('spreadsheet_id'): return None
 result=GoogleSheetsStore.__new__(GoogleSheetsStore)
 result.book=gspread.authorize(authorized(accounts)).open_by_key(connection['spreadsheet_id']); return result

def disconnect(accounts,claims):
 def clear(doc):
  u=require_admin(doc,claims); doc['connection']={}; doc.pop('candidate_google',None); doc['pending_google']={}
  from domain import uid,stamp
  doc['tables']['AccessAudit'].append({**audit('master_sheet.disconnected','primary',u['email']),'revision':uid(),'updated_at':stamp()})
 accounts.mutate(clear)
