"""Public IDs for server-encrypted account records; operational IDs are allocated in SQL."""
import re
from datetime import datetime,timezone

def numbered(doc,table,row,previous=None):
 previous=previous or {}
 row={**previous,**row}
 if previous.get('Record ID'):
  for key in ('Record ID','Entry sequence','Created at'): row[key]=previous[key]
 elif not row.get('Record ID'):
  counts=doc.setdefault('account_counters',{})
  counts[table]=counts.get(table,0)+1
  now=datetime.now(timezone.utc)
  row.update({'Record ID':f"{re.sub(r'^[0-9]+_', '', table).upper()}-{counts[table]:06}-{now.strftime('%Y%m%dT%H%M%S%fZ')}",'Entry sequence':counts[table],'Created at':now.isoformat()})
 return row
