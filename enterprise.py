"""Workbook-backed corporate registers and transparent operational calculations."""
import json, hashlib, math
from pathlib import Path
from datetime import date, datetime, timedelta
from domain import today, stamp, uid, TZ
REF=json.loads(Path(__file__).with_name('workbook_reference.json').read_text())
FORMS={k:v['headers'][1:] for k,v in REF['forms'].items()}
LABELS=dict(zip(FORMS,['Daily HSE Report','Safety Observation','Incident / Near Miss','Permit Status','High-Risk Activity','Corrective Action','Inspection','Training','Compliance Finding','Environmental','Corporate Feedback']))
FORMS.update({'StopWork':['Date','Project','Activity','Location','Reason','Risk','Responsible','Due Date','Status','Reopening Controls','Verified By','Closure Date','Delay Hours'], 'Audits':['Date','Project','Audit Type','Inspector','Findings','Risk','Responsible','Due Date','Status','Score %'], 'Emergency':['Date','Project','Drill / Equipment','Responsible','Status','Score %','Findings','Due Date'], 'Resources':['Date','Project','HSE Officers','Required Officers','Support Request','Responsible','Due Date','Status']})
LABELS.update({'StopWork':'Stop Work / Suspension','Audits':'Audit','Emergency':'Emergency Readiness','Resources':'HSE Resources / Support'})
# Additional fields required by the conversation, absent from the supplied template.
FORMS['03_DAILY_REPORT'] += ['Inspections Planned','Visitors','Subcontractors','HSE Officers','Tomorrow Activities']
FORMS['05_INCIDENTS'] += ['Lost Workdays','Closure Date','Evidence / Link']
FORMS['07_HIGH_RISK'] += ['Permit ID','Responsible']
FORMS['10_TRAINING'] += ['Evidence / Link']
FORMS['11_COMPLIANCE'] += ['Risk']
FORMS['12_ENVIRONMENT'] += ['Quantity','Unit']
for table in FORMS:
 if 'Closure Date' not in FORMS[table]: FORMS[table].append('Closure Date')
META=['revision','updated_at','actor']
SCHEMAS={k:['id']+v+['Attachment ID','Linked Action ID']+META for k,v in FORMS.items()}
SCHEMAS.update({'Projects':['id','name','client','location','lead','hse_lead','status','target','closed_at','closed_by','closure_notes','closure_context','deleted_at','deleted_by','branding']+META,'Settings':['id','value']+META,'Standards':['id']+list(REF['standards'][0])+['Review Status']+META,'Evidence':['id','project','record_id','filename','mime','chunk','content']+META,'AlertState':['id','project','status','note']+META})
NUMBERS={'Manpower','Man-hours','High-Risk Activities','Toolbox Talks','Inspections','Observations','Permits Active','Incidents','Inspections Planned','Visitors','Subcontractors','HSE Officers','Lost Workdays','Attendance','Actions Raised','Score %','Delay Hours','Required Officers','Quantity'}
DATES={'Date Raised','Date','Due Date','Closure Date','Last Verified','Expiry Date','Issue Date'}
OPTIONS={'Shift':['Day','Night'],'Risk':['Low','Medium','High','Critical'],'Severity':['Low','Medium','High','Critical'],'Priority':['Low','Medium','High','Critical'],'Incident Type':['Near Miss','First Aid','MTC','RWC','LTI','Fatality','Property Damage','Environmental'],'Permit Type':['Hot Work','Cold Work','Confined Space','Excavation','Lifting','Electrical','Work at Height','Radiography','Line Breaking','Other'],'Category':['Unsafe Act','Unsafe Condition','Positive','PPE','Housekeeping','Work at Height','Lifting','Electrical','Excavation','Fire','Traffic','Chemical','Environmental','Other'],'Overall Status':['Green','Amber','Orange','Red'],'Result':['Pending','Pass','Fail'],'Investigation Status':['Open','In Progress','Complete'],'Source':['Observation','Incident','Inspection','Audit','Client','Environment','Corporate','Other']}
YES={'Stop Work','RAMS Verified','Isolation/LOTO','Gas Test','Permit Required','Competency Verified','Controls Confirmed','HSE Monitoring','Competency Required','Applicable','Incident?','Corporate Escalation'}
CLOSED={'Closed','Reopened','Cancelled','Complete'}
def statuses(table):
 return {'06_PERMITS':['Pending','Approved','Active','Expired','Rejected','Suspended','Closed'],'07_HIGH_RISK':['Planned','Active','On Hold','Complete','Cancelled'],'11_COMPLIANCE':['Unverified','Compliant','Gap','Open','Not Applicable'],'StopWork':['Suspended','Awaiting Verification','Reopened'],'10_TRAINING':['Planned','Complete','Expired'],'Emergency':['Planned','Complete','Gap']}.get(table,['Open','In Progress','Closed'])
def seed():
 t={k:[] for k in SCHEMAS}
 for i in range(1,16): t['Projects'].append({'id':f'P{i:02}','name':f'Project {i:02}','client':'','location':'Saudi Arabia','lead':'','hse_lead':'','status':'Active','target':90,'revision':uid(),'updated_at':stamp(),'actor':'Workbook template'})
 for k,v in {'report_cutoff':'08:00','green_threshold':'90','amber_threshold':'75','orange_threshold':'60','base_url':'http://localhost:8501/','notification_enabled':'No','summary_time':'08:00'}.items(): t['Settings'].append({'id':k,'value':v,'revision':uid(),'updated_at':stamp(),'actor':'Initial setup'})
 t['Standards']=[{'id':r['Requirement ID'],**r,'Review Status':'Unverified template','revision':uid(),'updated_at':stamp(),'actor':'Workbook template'} for r in REF['standards']]
 return t

def permitted(role,assigned,project,table='',write=False):
 if role in ('Administrator','Corporate manager'): return True
 if table in ('Settings','Projects','Standards') and write: return False
 if role=='Corporate viewer': return not write
 if project not in assigned: return False
 if write and (role=='Project viewer' or table=='13_CORP_FEEDBACK'): return False
 return role in ('Project manager','HSE officer','Project lead','Project viewer')

def validate(table,row,projects):
 r=dict(row)
 if r.get('Project') not in projects: raise ValueError('Select an authorized project.')
 if not r.get('actor','').strip(): raise ValueError('Reporting person is required.')
 for f in FORMS[table]:
  v=r.get(f,'')
  if f in NUMBERS:
   if v in ('',None): continue
   n=float(v)
   if not math.isfinite(n) or n<0 or (f=='Score %' and n>100): raise ValueError(f'{f}: enter a valid nonnegative value.')
   r[f]=n
  if f in DATES and v:
   date.fromisoformat(str(v)[:10])
 if table=='03_DAILY_REPORT':
  if not r.get('Date') or r['Date']>str(today()): raise ValueError('Daily report date cannot be in the future.')
  if r.get('Shift') not in ('Day','Night'): raise ValueError('Select shift.')
  if float(r.get('Inspections',0))>float(r.get('Inspections Planned',0)): raise ValueError('Inspections completed cannot exceed planned; include unplanned completed inspections in the plan total.')
  r['id']='daily-'+hashlib.sha256(f"{r['Project']}|{r['Date']}|{r['Shift']}".encode()).hexdigest()[:20]
 if table=='06_PERMITS':
  if not r.get('Issue Date') or not r.get('Expiry Date'): raise ValueError('Permit issue and expiry date/time are required.')
  if r['Expiry Date']<=r['Issue Date']: raise ValueError('Expiry must be after issue date/time.')
 if table in ('04_OBSERVATIONS','05_INCIDENTS') and not r.get('Description','').strip(): raise ValueError('Description is required.')
 if table=='08_ACTIONS' and (not r.get('Finding / Action','').strip() or not r.get('Responsible','').strip() or not r.get('Due Date')): raise ValueError('Action, responsible person and due date are required.')
 if r.get('Status') in ('Closed','Reopened'):
  if not r.get('Closure Date'): raise ValueError('Closure date is required.')
  if r['Closure Date']>str(today()): raise ValueError('Closure date cannot be in the future.')
  if table in ('08_ACTIONS','StopWork') and not r.get('Verified By','').strip(): raise ValueError('Closure requires a named verifier.')
  if table=='StopWork' and not r.get('Reopening Controls','').strip(): raise ValueError('Document verified reopening controls before reopening work.')
 if table=='11_COMPLIANCE' and r.get('Status')=='Compliant' and not all(r.get(k) for k in ('Evidence / Link','Last Verified','Revision / Reference','Requirement ID')): raise ValueError('Compliance requires evidence, requirement ID, revision and verification date.')
 for f,v in r.items():
  if isinstance(v,str) and len(v)>40000: raise ValueError(f'{f} exceeds the cell size limit.')
 return r

def n(r,k): return float(r.get(k) or 0)
def pct(a,b): return 100*a/b if b else None
def days_open(r,now=None):
 now=now or today(); end=date.fromisoformat(r['Closure Date']) if r.get('Status') in CLOSED and r.get('Closure Date') else now
 return max(0,(end-date.fromisoformat(r.get('Date Raised') or r.get('Date') or str(now))).days)
def overdue(r,now=None):
 return bool(r.get('Due Date') and r.get('Status') not in CLOSED and r['Due Date']<str(now or today()))
def settings(t): return {r['id']:r['value'] for r in t['Settings']}
def dt(s):
 d=datetime.fromisoformat(s); return d.replace(tzinfo=TZ) if not d.tzinfo else d.astimezone(TZ)
def alerts(t,now=None):
 now=now or datetime.now(TZ); result=[]
 def add(table,r,level,issue): result.append({'id':f"{table}:{r['id']}:{issue}",'Project':r.get('Project',r['id']),'Level':level,'Issue':issue,'Register':table,'Record':r['id'],'Responsible':r.get('Responsible','')})
 for p in t['Projects']:
  if p['status']=='Active' and now.strftime('%H:%M')>=settings(t).get('report_cutoff','08:00') and not any(r['Project']==p['id'] and r['Date']==str(now.date()) for r in t['03_DAILY_REPORT']): add('03_DAILY_REPORT',p,'Amber','Daily report missing')
 for table in FORMS:
  for r in t[table]:
   status=r.get('Status','')
   if table=='06_PERMITS' and status in ('Active','Approved','Expired') and r.get('Expiry Date'):
    h=(dt(r['Expiry Date'])-now).total_seconds()/3600
    if h<=24: add(table,r,'Red' if h<=0 else 'Orange' if h<=4 else 'Amber','Permit expired' if h<=0 else 'Permit expiring within 4h' if h<=4 else 'Permit expiring within 24h')
   if table=='StopWork' and status!='Reopened': add(table,r,'Red','Stop work remains suspended')
   if table=='05_INCIDENTS' and status not in CLOSED and (r.get('Incident Type') in ('Fatality','LTI') or r.get('Severity')=='Critical'): add(table,r,'Red','Critical incident requires intervention')
   if overdue(r,now.date()): add(table,r,'Red' if r.get('Risk',r.get('Priority')) in ('High','Critical') else 'Orange','Overdue action / finding')
   if table=='07_HIGH_RISK' and status in ('Active','Planned','On Hold') and r.get('Date','')<=str(now.date()+timedelta(days=1)):
    control=any(r.get(k)!='Yes' for k in ('Competency Verified','Controls Confirmed','HSE Monitoring')) or r.get('RAMS Status')!='Approved'
    if r.get('Permit Required')=='Yes':
     permit=next((p for p in t['06_PERMITS'] if p['id']==r.get('Permit ID') and p['Project']==r['Project']),None)
     control=control or not permit or permit.get('Status')!='Active' or dt(permit['Expiry Date'])<=now
    if control: add(table,r,'Red','High-risk work controls incomplete — hold work')
   if table=='11_COMPLIANCE' and status in ('Gap','Open') and r.get('Applicable')=='Yes': add(table,r,'Red' if r.get('Risk')=='Critical' else 'Orange','Applicable compliance gap')
   if table=='10_TRAINING' and r.get('Expiry Date') and r['Expiry Date']<=str(now.date()+timedelta(days=30)): add(table,r,'Orange' if r['Expiry Date']<str(now.date()) else 'Amber','Training expired' if r['Expiry Date']<str(now.date()) else 'Training expires within 30 days')
   if table=='Resources' and r.get('Date')==str(now.date()) and n(r,'HSE Officers')<n(r,'Required Officers'): add(table,r,'Orange','HSE staffing below project requirement')
   if table=='03_DAILY_REPORT' and r.get('Date')==str(now.date()) and r.get('Stop Work')=='Yes': add(table,r,'Red','Daily report indicates stop work — review suspension register')
 order={'Red':0,'Orange':1,'Amber':2}; return sorted(result,key=lambda r:order[r['Level']])

def metrics(t,start,end,project=None,now=None):
 now=now or datetime.now(TZ)
 scope=lambda table:[r for r in t[table] if not project or r.get('Project')==project]
 period=lambda table:[r for r in scope(table) if str(start)<=str(r.get('Date',r.get('Date Raised','')))[:10]<=str(end)]
 daily=period('03_DAILY_REPORT'); inc=period('05_INCIDENTS'); actions=scope('08_ACTIONS')
 # Latest submitted shift per project on end date; never sum workforce across historical days.
 workforce={}
 for r in sorted(daily,key=lambda r:(r['Date'],r.get('Shift',''))):
  if r['Date']==str(end): workforce[r['Project']]=n(r,'Manpower')
 hrs=sum(n(r,'Man-hours') for r in daily)
 counts={kind:sum(r.get('Incident Type')==kind for r in inc) for kind in OPTIONS['Incident Type']}
 rec=sum(counts[k] for k in ('Fatality','LTI','RWC','MTC'))
 controls={}
 controls['Inspection']=pct(sum(n(r,'Inspections') for r in daily),sum(n(r,'Inspections Planned') for r in daily))
 controls['Actions']=pct(sum(r.get('Status')=='Closed' for r in actions),len(actions))
 permits=[r for r in scope('06_PERMITS') if r.get('Status') in ('Active','Expired','Approved')]
 controls['Permit']=pct(sum(r.get('Status')=='Active' and dt(r['Expiry Date'])>now and r.get('RAMS Verified')=='Yes' for r in permits),len(permits))
 train=[r for r in scope('10_TRAINING') if r.get('Competency Required')=='Yes']
 controls['Training']=pct(sum(r.get('Result')=='Pass' and (not r.get('Expiry Date') or r['Expiry Date']>=str(now.date())) for r in train),len(train))
 compliance=[r for r in scope('11_COMPLIANCE') if r.get('Applicable')=='Yes']
 controls['Compliance']=pct(sum(r.get('Status')=='Compliant' for r in compliance),len(compliance))
 known=[v for v in controls.values() if v is not None]
 # Equal-weight control assurance is explicit, provisional; incidents independently override RAG.
 score=sum(known)/len(known) if known else None
 al=[a for a in alerts(t,now) if not project or a['Project']==project]
 cfg=settings(t)
 rag='Red' if any(a['Level']=='Red' for a in al) else 'Gray' if not known else 'Orange' if any(a['Level']=='Orange' for a in al) else 'Amber' if len(known)<5 or any(a['Level']=='Amber' for a in al) else 'Green' if score>=float(cfg['green_threshold']) else 'Amber' if score>=float(cfg['amber_threshold']) else 'Orange' if score>=float(cfg['orange_threshold']) else 'Red'
 # Rates only when every incident date/project has a daily exposure report in selected range.
 coverage=all(any(d['Project']==r['Project'] and d['Date']==r['Date'] for d in daily) for r in inc)
 return {'Manpower (end date)':sum(workforce.values()) if workforce else None,'Man-hours':hrs if daily else None,'Incidents':sum(counts.values())-counts['Near Miss'],'Near Miss':counts['Near Miss'],'Recordables':rec,'Fatalities':counts['Fatality'],'LTI':counts['LTI'],'First Aid':counts['First Aid'],'Open Actions':sum(r.get('Status')!='Closed' for r in actions),'Overdue Actions':sum(overdue(r,now.date()) for r in actions),'Active Permits':sum(r.get('Status')=='Active' and dt(r['Expiry Date'])>now for r in permits),'Stop Work':sum(r.get('Status')!='Reopened' for r in scope('StopWork')),'TRIR':pct(rec*2000,hrs) if coverage else None,'LTIFR':pct(counts['LTI']*10000,hrs) if coverage else None,'Severity Rate':pct(sum(n(r,'Lost Workdays') for r in inc)*10000,hrs) if coverage else None,'Score':score,'Coverage':len(known),'Status':rag,'controls':controls}

def demo():
 t=seed(); now=today()
 def put(table,p,**values):
  r={k:'' for k in SCHEMAS[table]}; r.update(id=uid(),Project=p,Date=str(now),actor='Demo HSE lead',revision=uid(),updated_at=stamp(),**values); t[table].append(r)
 for i in range(1,16):
  p=f'P{i:02}'
  for d in range(21):
   if d==0 and i in (8,14): continue
   put('03_DAILY_REPORT',p,**{'Shift':'Day','Manpower':80+i*12,'Man-hours':(80+i*12)*8,'Inspections':3+i%3,'Inspections Planned':6,'Toolbox Talks':2,'Observations':5,'Stop Work':'No'})
   t['03_DAILY_REPORT'][-1]['Date']=str(now-timedelta(days=d))
  put('08_ACTIONS',p,**{'Date Raised':str(now-timedelta(days=5)),'Finding / Action':'Verify access and edge protection','Responsible':f'Project {i:02} lead','Due Date':str(now+timedelta(days=2 if i%3 else -2)),'Status':'Open','Risk':'High'})
  put('06_PERMITS',p,**{'Permit Type':'Hot Work','Activity':'Workshop fabrication','Issue Date':(datetime.now(TZ)-timedelta(hours=2)).isoformat(),'Expiry Date':(datetime.now(TZ)+timedelta(hours=-1 if i==3 else 36)).isoformat(),'Status':'Active','RAMS Verified':'Yes'})
  put('10_TRAINING',p,**{'Topic':'Working at height','Employee / Group':'Access team','Competency Required':'Yes','Result':'Pass','Status':'Complete','Expiry Date':str(now+timedelta(days=60))})
  put('11_COMPLIANCE',p,**{'Source / Standard':'Project requirements','Requirement ID':'DEMO-01','Applicable':'Yes','Status':'Compliant','Evidence / Link':'Demo evidence only','Last Verified':str(now),'Revision / Reference':'Demo','Risk':'Low'})
 put('StopWork','P03',**{'Activity':'Excavation access','Reason':'Unsafe access','Status':'Suspended','Risk':'Critical','Responsible':'P03 lead'})
 put('05_INCIDENTS','P06',**{'Incident Type':'Near Miss','Severity':'High','Description':'Dropped hand tool in exclusion zone','Status':'In Progress'})
 return t
