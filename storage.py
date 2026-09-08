"""Append-only Google Sheets backend. Latest revision for a stable ID is current."""
from copy import deepcopy
import threading
from domain import SCHEMAS, normalize, stamp, uid

_LOCK=threading.RLock()

class ConflictError(ValueError): pass

class MemoryStore:
    def __init__(self,tables): self.tables=deepcopy(tables)
    def read(self): return deepcopy(self.tables)
    def save(self,table,rows,expected=None):
        with _LOCK:
            current={r['id']:r for r in self.tables[table]}
            check_conflicts(current,rows,expected)
            for row in rows:
                row=deepcopy(row); row.update(revision=uid(),updated_at=stamp())
                current[row['id']]=row
            self.tables[table]=list(current.values())

def check_conflicts(current,rows,expected):
    if expected is None: expected={}
    if len({r['id'] for r in rows})!=len(rows): raise ValueError('Duplicate IDs in the same save.')
    for row in rows:
        actual=current.get(row['id'],{}).get('revision','')
        if actual!=expected.get(row['id'],''):
            raise ConflictError('A record changed since this form was opened. Refresh the page and review it before saving again.')

class GoogleSheetsStore:
    def __init__(self,spreadsheet_id,credentials):
        import gspread
        from google.oauth2.service_account import Credentials
        creds=Credentials.from_service_account_info(credentials,scopes=['https://www.googleapis.com/auth/spreadsheets'])
        self.book=gspread.authorize(creds).open_by_key(spreadsheet_id)
    def read(self):
        result={}
        ranges=[f"'{name}'!A:{column_name(len(cols))}" for name,cols in SCHEMAS.items()]
        response=self.book.values_batch_get(ranges,params={'valueRenderOption':'UNFORMATTED_VALUE'})
        for (name,headers),payload in zip(SCHEMAS.items(),response.get('valueRanges',[])):
            values=payload.get('values',[])
            if not values or values[0]!=headers: raise ValueError(f'{name} has unexpected headers. Use the supplied backend workbook.')
            current={}
            for cells in values[1:]:
                if not cells or not str(cells[0]).strip(): continue
                row=normalize(name,dict(zip(headers,cells)))
                current[row['id']]=row
            result[name]=list(current.values())
        if set(result)!=set(SCHEMAS): raise ValueError('The backend workbook is missing required tabs.')
        return result
    def save(self,table,rows,expected=None):
        if not rows: return
        with _LOCK:
            current={r['id']:r for r in self.read()[table]}
            check_conflicts(current,rows,expected)
            payload=[]
            for row in rows:
                row={**row,'revision':uid(),'updated_at':stamp()}
                payload.append(['' if row.get(k) is None else row.get(k,'') for k in SCHEMAS[table]])
            # Append avoids rewriting the table and preserves all prior revisions.
            # One request saves a complete entry batch; RAW prevents formula injection.
            self.book.values_append(f"'{table}'!A1",params={'valueInputOption':'RAW','insertDataOption':'INSERT_ROWS'},body={'values':payload})

# Corporate schemas are registered here to avoid a circular dependency in domain.
from enterprise import SCHEMAS as CORPORATE_SCHEMAS
SCHEMAS.update(CORPORATE_SCHEMAS)

def column_name(index):
    result=''
    while index:
        index,remainder=divmod(index-1,26); result=chr(65+remainder)+result
    return result

def memory_save_many(self,changes,expected):
    with _LOCK:
        for table,rows in changes.items(): check_conflicts({r['id']:r for r in self.tables[table]},rows,expected.get(table,{}))
        backup=deepcopy(self.tables)
        try:
            for table,rows in changes.items(): self.save(table,rows,expected.get(table,{}))
        except Exception:
            self.tables=backup; raise

def sheets_save_many(self,changes,expected):
    with _LOCK:
        tables=self.read()
        for table,rows in changes.items(): check_conflicts({r['id']:r for r in tables[table]},rows,expected.get(table,{}))
        sheet_ids={s.title:s.id for s in self.book.worksheets()}
        requests=[]
        for table,rows in changes.items():
            values=[]
            for r in rows:
                r={**r,'revision':uid(),'updated_at':stamp()}
                # Explicit stringValue prevents user-entered formulas from executing.
                values.append({'values':[{'userEnteredValue':{'stringValue':str(r.get(k,'') or '')}} for k in SCHEMAS[table]]})
            requests.append({'appendCells':{'sheetId':sheet_ids[table],'rows':values,'fields':'userEnteredValue'}})
        if requests: self.book.batch_update({'requests':requests})
MemoryStore.save_many=memory_save_many
GoogleSheetsStore.save_many=sheets_save_many
