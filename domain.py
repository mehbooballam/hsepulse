from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import hashlib
import math
import random
import uuid
import pandas as pd
from catalog import seed_catalog, RATES

TZ = ZoneInfo('Asia/Riyadh')
def today(): return datetime.now(TZ).date()
def stamp(): return datetime.now(timezone.utc).isoformat()
def uid(): return uuid.uuid4().hex

def initial_tables():
    definitions=[]
    for i,item in enumerate(seed_catalog(),1):
        definitions.append({'id':f'K{i:03}',**item,'revision':uid(),'updated_at':stamp(),'actor':'Initial catalogue'})
    return {'Definitions':definitions,'Records':[],'Actions':[],
            'Sites':[{'id':'SITE-001','name':'Main site','revision':uid(),'updated_at':stamp(),'actor':'Initial setup'}]}

SCHEMAS = {
'Definitions':['id','name','category','kind','unit','numerator_label','denominator_label','ready','daily','direction','target','owner','definition','revision','updated_at','actor'],
'Records':['id','date','site','shift','kpi_id','numerator','denominator','na','notes','revision','updated_at','actor'],
'Actions':['id','site','title','priority','owner','due_date','status','closed_date','notes','revision','updated_at','actor'],
'Sites':['id','name','revision','updated_at','actor'],
}

def number(value):
    if value is None or value == '': return None
    val=float(value)
    if not math.isfinite(val): raise ValueError('Numbers must be finite.')
    return val

def normalize(table, row):
    row={key:row.get(key,'') for key in SCHEMAS[table]}
    if table=='Definitions':
        for k in ('ready','daily'): row[k]=int(float(row[k] or 0))
        row['target']=number(row['target'])
    elif table=='Records':
        for k in ('numerator','denominator'): row[k]=number(row[k])
        row['na']=int(float(row['na'] or 0))
    return row

def record_id(day,site,shift,kpi):
    return hashlib.sha256(f'{day}|{site}|{shift}|{kpi}'.encode()).hexdigest()[:24]

def validate_record(row, definitions, sites):
    row=normalize('Records',row)
    d=definitions.get(row['kpi_id'])
    if not d or not d['ready'] or d['kind']=='derived': raise ValueError('Select an active, directly recorded KPI.')
    if row['site'] not in sites: raise ValueError('Unknown site.')
    if row['shift'] not in ('Day','Night'): raise ValueError('Shift must be Day or Night.')
    parsed=date.fromisoformat(row['date'])
    if parsed > today(): raise ValueError('Actual records cannot be future dated.')
    if not row['actor'].strip(): raise ValueError('Enter the reporting person.')
    if row['na'] not in (0,1): raise ValueError('N/A must be 0 or 1.')
    n,z=row['numerator'],row['denominator']
    if row['na']:
        if not row['notes'].strip(): raise ValueError('Explain why this KPI is not applicable.')
        if n is not None or z is not None: raise ValueError('Clear numeric values when marking N/A.')
    else:
        if n is None: raise ValueError('Enter a numerator/value or mark N/A.')
        if n<0: raise ValueError('Values cannot be negative.')
        if d['kind'] in ('percentage','ratio'):
            if z is None or z<0: raise ValueError('Enter a nonnegative denominator.')
            if z==0 and n!=0: raise ValueError('A zero denominator requires a zero numerator.')
            if d['kind']=='percentage' and n>z: raise ValueError('Compliant/completed count cannot exceed the applicable total.')
        elif z is not None: raise ValueError('This KPI does not use a denominator.')
    row['id']=record_id(row['date'],row['site'],row['shift'],row['kpi_id'])
    return row

def evaluate(definition,records,definitions=None):
    """Returns value, data status, sample size. Never substitutes missing with zero."""
    if definition['kind']=='derived':
        num_name,den_name,factor=RATES[definition['name']]
        names={d['name']:d['id'] for d in definitions}
        a={ (r['date'],r['site'],r['shift']):r for r in records if r['kpi_id']==names[num_name] }
        b={ (r['date'],r['site'],r['shift']):r for r in records if r['kpi_id']==names[den_name] }
        keys=set(a)|set(b)
        if not keys: return None,'No data',0
        if set(a)!=set(b) or any(a[k]['na'] or b[k]['na'] for k in keys): return None,'Incomplete inputs',len(keys)
        n=sum(a[k]['numerator'] for k in keys); z=sum(b[k]['numerator'] for k in keys)
        return (n/z*factor,'Recorded',len(keys)) if z else (None,'N/A',len(keys))
    rows=[r for r in records if r['kpi_id']==definition['id']]
    if not rows: return None,'No data',0
    if definition['kind']=='snapshot':
        # A snapshot is not additive across dates or shifts: display the sum
        # of the most recent recorded shift values across selected sites.
        latest={}
        for r in sorted(rows,key=lambda x:(x['date'],x['shift']=='Night')): latest[r['site']]=r
        rows=list(latest.values())
        if any(r['na'] for r in rows): return None,'N/A',len(rows)
        return sum(r['numerator'] for r in rows),'Latest per site',len(rows)
    applicable=[r for r in rows if not r['na']]
    if not applicable: return None,'N/A',len(rows)
    if definition['kind'] in ('percentage','ratio'):
        n=sum(r['numerator'] for r in applicable); z=sum(r['denominator'] for r in applicable)
        return (n/z*(100 if definition['kind']=='percentage' else 1),'Recorded',len(rows)) if z else (None,'N/A',len(rows))
    return sum(r['numerator'] for r in applicable),'Recorded',len(rows)

def display(value,unit=''):
    if value is None: return '—'
    return f'{value:,.1f}%' if unit=='%' else f'{value:,.2f}'.rstrip('0').rstrip('.')

def performance(d,value,status):
    if value is None: return status
    if d['target'] is None or d['direction']=='context': return 'Context only'
    meets=value>=d['target'] if d['direction']=='higher' else value<=d['target']
    return 'On target' if meets else 'Needs attention'

def make_demo():
    tables=initial_tables(); rng=random.Random(27)
    tables['Sites']=[{'id':f'SITE-00{i}','name':n,'revision':uid(),'updated_at':stamp(),'actor':'Demo'} for i,n in enumerate(['North construction site','Central operations'],1)]
    for d in tables['Definitions']:
        if d['kind']=='percentage' and d['ready']: d['target']=95
    for offset in range(29,-1,-1):
        day=(today()-timedelta(days=offset)).isoformat()
        for site in tables['Sites']:
            for d in tables['Definitions']:
                if not d['daily'] or d['kind']=='derived': continue
                z=None
                if d['kind']=='percentage':
                    z=rng.randint(8,30); n=z-rng.choice([0,0,0,1,2])
                elif d['name']=='Hours worked': n=rng.randint(65,95)*10
                elif d['name']=='Workforce on site': n=rng.randint(65,95)
                elif d['name'] in ('Hazards reported','Near misses reported','Stop-work interventions'): n=rng.randint(0,8)
                elif d['name']=='Critical-control failures identified': n=rng.choice([0,0,0,1])
                elif d['name']=='Overdue high-risk actions': n=rng.randint(0,3)
                elif d['name']=='First-aid cases': n=rng.choice([0,0,0,1])
                else: n=0
                tables['Records'].append(dict(id=record_id(day,site['id'],'Day',d['id']),date=day,site=site['id'],shift='Day',kpi_id=d['id'],numerator=n,denominator=z,na=0,notes='Synthetic demonstration data',revision=uid(),updated_at=stamp(),actor='Demo'))
    for i,(title,priority,delta,status) in enumerate([('Restore excavation edge protection','High',-2,'Open'),('Replace damaged lifting sling','High',0,'In progress'),('Refresh confined-space rescue briefing','Medium',2,'Open'),('Clear emergency access route','High',-1,'Closed')]):
        tables['Actions'].append(dict(id=uid(),site=tables['Sites'][i%2]['id'],title=title,priority=priority,owner='Demo supervisor',due_date=(today()+timedelta(days=delta)).isoformat(),status=status,closed_date=today().isoformat() if status=='Closed' else '',notes='Synthetic example',revision=uid(),updated_at=stamp(),actor='Demo'))
    return tables
