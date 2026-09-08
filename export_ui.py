"""Permission-scoped CSV, JSON and ZIP exports for every operational category."""
import io
import json
import zipfile
import pandas as pd
import streamlit as st
from storage import SCHEMAS
from enterprise import LABELS
from enterprise_ui import safe_csv

META=['Record ID','Entry sequence','Created at']

def display_frame(rows, table=None):
 columns=list(dict.fromkeys(META + (SCHEMAS.get(table,[]) if table else []) + [k for r in rows for k in r]))
 df=pd.DataFrame(rows).reindex(columns=columns)
 # Business record number is prominent; stable relation keys remain exportable.
 return df.rename(columns={'id':'Internal key'})

def export_buttons(table, rows, key=None):
 frame=display_frame(rows,table)
 left,right=st.columns(2)
 left.download_button('Export CSV',safe_csv(frame),table+'.csv','text/csv',key=(key or table)+'_csv')
 right.download_button('Export JSON',json.dumps(rows,ensure_ascii=False,indent=2).encode(),table+'.json','application/json',key=(key or table)+'_json')

def archive_bytes(tables):
 result=io.BytesIO()
 with zipfile.ZipFile(result,'w',zipfile.ZIP_DEFLATED) as z:
  for name,rows in tables.items():
   if name not in SCHEMAS: continue
   z.writestr(name+'.csv',safe_csv(display_frame(rows,name)))
   z.writestr(name+'.json',json.dumps(rows,ensure_ascii=False,indent=2))
 return result.getvalue()

def render_exports(store):
 st.title('Data & export')
 st.write('Browse and export the records available to your role and assigned projects.')
 tables=store.read()
 categories=[k for k in SCHEMAS if k in tables]
 table=st.selectbox('Data category',categories,format_func=lambda k:LABELS.get(k,k))
 rows=tables[table]
 query=st.text_input('Search this category')
 if query: rows=[r for r in rows if query.casefold() in json.dumps(r,ensure_ascii=False).casefold()]
 st.caption(f'{len(rows)} records · Dates in generated IDs are UTC · IDs remain unchanged after editing')
 st.dataframe(display_frame(rows,table),hide_index=True,width='stretch')
 export_buttons(table,rows,'data_export')
 st.divider()
 st.download_button('Export all accessible data (ZIP)',archive_bytes(tables),'HSE-data.zip','application/zip')
 st.caption('The ZIP contains CSV and JSON for every operational category, including empty register headers and evidence data. Account secrets and invitation tokens are excluded.')
