"""Administrator-managed spreadsheet links using a server service account."""
import re
from urllib.parse import urlsplit
import gspread
from access_control import principal, AccessDenied, audit

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def require_admin(doc, claims):
 u = principal(doc['tables'], claims)
 if u['role'] != 'Administrator':
  raise AccessDenied('Only the master administrator can connect Google Sheets.')
 return u

def spreadsheet_id(link):
 value = link.strip()
 parsed = urlsplit(value)
 if parsed.scheme != 'https' or parsed.netloc != 'docs.google.com':
  raise ValueError('Paste a Google Sheets link starting with https://docs.google.com/spreadsheets/d/.')
 match = re.fullmatch(r'/spreadsheets/d/([A-Za-z0-9_-]+)(?:/.*)?', parsed.path)
 if not match or match.group(1) == 'e':
  raise ValueError('Use the spreadsheet edit link, not a published CSV or website link.')
 return match.group(1)

def sheet_client(settings):
 config = dict(settings.get('gcp_service_account', {}))
 if not all(config.get(k) for k in ('client_email', 'private_key', 'token_uri')):
  raise ValueError('The application owner must configure the Sheets service account in hosting secrets once.')
 return gspread.service_account_from_dict(config, scopes=SCOPES)

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

def choose(accounts, claims, settings, link):
 require_admin(accounts.document(), claims)
 key = spreadsheet_id(link)
 book = sheet_client(settings).open_by_key(key)
 # Writing the current title back checks edit access without changing cell data.
 book.batch_update({'requests': [{'updateSpreadsheetProperties': {
  'properties': {'title': book.title}, 'fields': 'title'}}]})
 initialize(book)
 def save(doc):
  u = require_admin(doc, claims)
  doc['connection'] = {'spreadsheet_id': book.id, 'title': book.title,
                       'url': book.url, 'connected_by': u['email'], 'mode': 'service_account'}
  doc.pop('candidate_google', None)
  doc.pop('pending_google', None)
  from domain import uid, stamp
  doc['tables']['AccessAudit'].append({**audit('master_sheet.connected', book.id, u['email'], book.title), 'revision': uid(), 'updated_at': stamp()})
 accounts.mutate(save)
 return book

def operational_store(accounts, settings):
 from storage import GoogleSheetsStore
 connection = accounts.document().get('connection', {})
 if not connection.get('spreadsheet_id'): return None
 result = GoogleSheetsStore.__new__(GoogleSheetsStore)
 result.book = sheet_client(settings).open_by_key(connection['spreadsheet_id'])
 return result

def disconnect(accounts,claims):
 def clear(doc):
  u=require_admin(doc,claims); doc['connection']={}; doc.pop('candidate_google',None); doc['pending_google']={}
  from domain import uid,stamp
  doc['tables']['AccessAudit'].append({**audit('master_sheet.disconnected','primary',u['email']),'revision':uid(),'updated_at':stamp()})
 accounts.mutate(clear)
