"""Corporate / project UI and mobile-friendly operational forms."""
import base64, html, io, json, zipfile
from datetime import datetime, date, timedelta, time
from urllib.parse import urlencode, urlsplit
import pandas as pd
import streamlit as st
import enterprise as e
from domain import today, uid, TZ

PAGES=['Corporate dashboard','Project dashboards','Field forms','Operational registers','Alerts & decisions','Standards library','Management report','Project settings']
COLORS={'Green':'#168563','Amber':'#b88400','Orange':'#e27025','Red':'#dc4255','Gray':'#798596'}

def identity(mode):
 if mode=='Database' and st.session_state.get('authenticated_identity'):
  return st.session_state['authenticated_identity']
 if mode=='Demo':
  with st.sidebar.expander('Preview access roles'):
   role=st.selectbox('Role',['Corporate manager','Corporate viewer','Project manager','HSE officer','Project lead','Project viewer'])
   assigned=st.multiselect('Assigned projects',[f'P{i:02}' for i in range(1,16)],default=['P01'])
  return role,assigned,'Demo user'
 st.error('Sign in through the application to open this workspace.'); st.stop()

def safe_csv(df):
 return df.map(lambda v:"'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v).to_csv(index=False).encode('utf-8-sig')

def render(page,store,mode):
 role,assigned,actor=identity(mode)
 t=store.read()
 allowed=[p for p in t['Projects'] if e.permitted(role,assigned,p['id'])]
 ids=[p['id'] for p in allowed]; names={p['id']:p['name'] for p in allowed}
 if not ids: st.info('No projects have been assigned to this account.'); st.stop()
 # Scope every read, including exports and attachments, before rendering any page.
 for table in e.FORMS: t[table]=[r for r in t[table] if r.get('Project') in ids]
 t['Projects']=allowed
 t['Evidence']=[r for r in t['Evidence'] if r.get('project') in ids]
 t['AlertState']=[r for r in t['AlertState'] if r.get('project') in ids]
 st.sidebar.caption(f'{role} · {len(ids)} accessible projects')
 cfg=e.settings(t)
 def link(view,**params):
  base=cfg.get('base_url','http://localhost:8501/')
  # Default local template links must follow the deployed app's actual URL.
  if urlsplit(base).hostname in ('localhost','127.0.0.1'):
   base=st.context.url or base
  return base.rstrip('/')+'/?'+urlencode({'view':view,**params})
 def nav_button(label,view,container=st,key=None,**params):
  from ui_shell import go
  container.button(label,key=key,on_click=go,args=(view,),kwargs=params,width='stretch')
 def save(table,rows):
  for row in rows:
   if not e.permitted(role,assigned,row.get('Project',row.get('project','')),table,True): raise ValueError('Your role cannot update this area.')
  store.save(table,rows,{r['id']:r.get('revision','') for r in t[table]})
 def pick_project(label='Project'):
  default=st.query_params.get('project',ids[0]); return st.selectbox(label,ids,index=ids.index(default) if default in ids else 0,format_func=lambda p:names[p])
 def download(table,rows):
  from export_ui import export_buttons
  export_buttons(table,rows)
 def frame(rows):
  if rows: st.dataframe(__import__('export_ui').display_frame(rows),hide_index=True,width='stretch')
  else: st.info('No records yet. Use Field forms to add the first record.')
 def project_matrix(start,end):
  return [{'Project':p['name'],'Code':p['id'],**{k:v for k,v in e.metrics(t,start,end,p['id']).items() if k!='controls'}} for p in allowed]
 def dashboard(project=None):
  period=st.segmented_control('Reporting period',['Today','MTD','YTD','Custom'],default='MTD')
  end=today(); start=end if period=='Today' else end.replace(day=1) if period=='MTD' else end.replace(month=1,day=1)
  if period=='Custom':
   c1,c2=st.columns(2); start=c1.date_input('From',end-timedelta(days=30)); end=c2.date_input('To',end)
   if start>end: st.error('From date must precede To date.'); return
  st.caption('Activity KPIs follow the selected period. Permits, open actions, training validity and alerts show current operational status.')
  @st.fragment(run_every='30s')
  def live():
   nonlocal t
   fresh=store.read()
   for table in e.FORMS: t[table]=[r for r in fresh[table] if r.get('Project') in ids]
   t['Settings']=fresh['Settings']
   m=e.metrics(t,start,end,project)
   al=[a for a in e.alerts(t) if not project or a['Project']==project]
   seen=st.session_state.get('seen_alerts')
   current={a['id'] for a in al}
   if seen is not None and current-seen: st.toast(f'{len(current-seen)} new operational alerts',icon='🚨')
   st.session_state['seen_alerts']=current
   st.markdown(f"<div style='padding:18px;border-radius:12px;background:{COLORS[m['Status']]};color:white'><b>{m['Status'].upper()} · {'Corporate portfolio' if not project else html.escape(names[project])}</b> &nbsp; | &nbsp; {len(al)} items need review</div>",unsafe_allow_html=True)
   st.write('')
   keys=['Manpower (end date)','Man-hours','Recordables','Overdue Actions','Active Permits','Stop Work']
   for offset in (0,3):
    for col,k in zip(st.columns(3),keys[offset:offset+3]): col.metric(k,'—' if m[k] is None else f'{m[k]:,.0f}')
   left,right=st.columns([1.5,1])
   with left:
    st.subheader('Control assurance')
    for k,v in m['controls'].items():
     st.progress(min(1,max(0,v/100)) if v is not None else 0,text=f'{k} · '+(f'{v:.0f}%' if v is not None else 'Not reported'))
    st.caption(f"Provisional score: {m['Score']:.1f}% · {m['Coverage']}/5 control areas measured" if m['Score'] is not None else 'No assurance score until records are submitted.')
   with right:
    st.subheader('🚨 Action required')
    for a in al[:6]:
     st.markdown(f"**{a['Level']} · {a['Project']}** — {a['Issue']}")
     nav_button('Review '+e.LABELS.get(a['Register'],'record').lower(),'Operational registers',form=a['Register'],project=a['Project'],key='alert_'+a['id'])
    if not al: st.success('No rules currently triggered. Check data coverage before drawing conclusions.')
   with st.expander('How the score and rates are calculated'):
    st.write('Control assurance is the equal-weight average of available inspection completion, action closure, permit checks, required training validity and verified applicable compliance. It is an internal operational indicator, not an IOSH certification score. Missing areas are excluded and coverage is shown; incomplete coverage cannot be green. Critical alerts override the score.')
    st.write('Inspection = completed / planned × 100. Action closure = closed / all actions × 100. Permit checks = active, unexpired permits with RAMS verified / active, approved or expired permits × 100. Training = passed and unexpired / competency-required records × 100. Compliance = verified compliant / applicable records × 100.')
    st.write('TRIR = recordables × 200,000 / hours; LTIFR = LTI × 1,000,000 / hours; severity = lost workdays × 1,000,000 / hours. Rates are withheld when an incident has no corresponding daily exposure report. Incident register is the rate source; daily incident summary is not added again. Near misses are separate from incidents. Zero reported incidents does not prove complete incident reporting.')
   if not project:
    st.subheader('Project performance • select a project to drill down')
    matrix=pd.DataFrame(project_matrix(start,end))
    st.dataframe(matrix.style.map(lambda v:f'background-color:{COLORS.get(v,"white")};color:white' if v in COLORS else '',subset=['Status']),hide_index=True,width='stretch',column_order=['Project','Status','Score','Coverage','Manpower (end date)','Incidents','Overdue Actions','Active Permits','Stop Work'])
    ranking=matrix.dropna(subset=['Score']).sort_values('Score',ascending=False)
    if not ranking.empty: st.bar_chart(ranking.set_index('Project')['Score'],color='#168563')
    for row in range(0,len(allowed),5):
     for col,p in zip(st.columns(5),allowed[row:row+5]): nav_button(p['name'],'Project dashboards',container=col,project=p['id'],key='project_'+p['id'])
   st.subheader('Leading and lagging indicators')
   for group in (['Incidents','Near Miss','LTI'],['TRIR','LTIFR','Severity Rate']):
    for col,k in zip(st.columns(3),group): col.metric(k,'—' if m[k] is None else f'{m[k]:,.2f}')
   daily=[r for r in t['03_DAILY_REPORT'] if str(start)<=r['Date']<=str(end) and (not project or r['Project']==project)]
   if daily:
    df=pd.DataFrame(daily)
    for k in ['Man-hours','Observations','Inspections','Toolbox Talks']: df[k]=pd.to_numeric(df[k],errors='coerce').fillna(0)
    st.line_chart(df.groupby('Date')[['Observations','Inspections','Toolbox Talks']].sum(),color=['#168563','#497ed9','#e27025'])
   if project:
    st.subheader('Upcoming high-risk work')
    frame([r for r in t['07_HIGH_RISK'] if r['Project']==project and r.get('Status') not in ('Complete','Cancelled')])
    nav_button('New daily report','Field forms',project=project,form='03_DAILY_REPORT')
   st.caption('Updates every 30 seconds while this dashboard is open · '+datetime.now(TZ).strftime('%H:%M:%S Riyadh'))
  live()

 if page=='Corporate dashboard':
  st.title('Corporate HSE dashboard'); st.write('Your projects, operational risks and daily performance in one place.'); dashboard()
 elif page=='Project dashboards':
  project=pick_project(); st.title(names[project]); dashboard(project)
 elif page=='Field forms':
  st.title('Field reporting'); st.write('Choose a project and a form. One submission updates the register and both dashboards.')
  project=pick_project(); choices=list(e.FORMS); selected=st.query_params.get('form',choices[0])
  table=st.selectbox('Report type',choices,index=choices.index(selected) if selected in choices else 0,format_func=e.LABELS.get)
  if not e.permitted(role,assigned,project,table,True): st.info('Your role can view this area but cannot submit this form.'); return
  existing=[r for r in t[table] if r['Project']==project]
  selected_id=st.selectbox('Create or update',['New record']+[r['id'] for r in existing],format_func=lambda value:next((r.get('Record ID',value) for r in existing if r['id']==value),value))
  old=next((r for r in existing if r['id']==selected_id),{})
  st.caption('Record IDs are assigned when saved: CATEGORY–NUMBER–UTC TIMESTAMP. The ID stays unchanged when you edit. Daily reports use one entry per project, date and shift.')
  with st.form('operational_'+table,clear_on_submit=False):
   row={'id':old.get('id',st.session_state.setdefault('draft_'+table,uid())),'Project':project,'actor':actor}
   fields=[f for f in e.FORMS[table] if f not in ('Project','Days Open','Days Overdue')]
   cols=st.columns(2)
   for index,f in enumerate(fields):
    v=old.get(f,''); key=table+selected_id+f
    with cols[index%2]:
     if f in e.NUMBERS: row[f]=st.number_input(f,min_value=0.,value=float(v) if v not in ('',None) else 0.,max_value=100. if f=='Score %' else None,key=key)
     elif f in e.DATES:
      default=date.fromisoformat(str(v)[:10]) if v else today() if f in ('Date','Issue Date') else None
      dv=st.date_input(f,value=default,key=key); row[f]=str(dv) if dv else ''
      if table=='06_PERMITS' and f in ('Issue Date','Expiry Date'):
       tv=st.time_input(f+' time (Riyadh)',value=e.dt(v).time() if v else time(8),key=key+'time'); row[f]=datetime.combine(dv,tv,tzinfo=TZ).isoformat() if dv else ''
     elif f in e.OPTIONS or f in e.YES or f in ('Status','Permit Status','RAMS Status'):
      options=e.OPTIONS.get(f) or (['No','Yes','Not Applicable'] if f in e.YES else ['Pending','Approved','Rejected'] if f=='RAMS Status' else e.statuses('06_PERMITS') if f=='Permit Status' else e.statuses(table))
      row[f]=st.selectbox(f,options,index=options.index(v) if v in options else 0,key=key)
     else: row[f]=st.text_input(f,value=str(v or ''),key=key)
   upload=st.file_uploader('Photo evidence (PNG/JPEG, up to 1 MB)',type=['png','jpg','jpeg'])
   linked=st.checkbox('Create a linked corrective action',value=False,disabled=table=='08_ACTIONS')
   action_text=st.text_input('Linked action instruction')
   action_owner=st.text_input('Linked action owner')
   action_due=st.date_input('Linked action due',today()+timedelta(days=7))
   submitted=st.form_submit_button('Save report',type='primary',width='stretch')
  if submitted:
   try:
    row=e.validate(table,row,ids)
    if old and row['id']!=old['id']: raise ValueError('Project, date and shift identify a daily report. Create a new report to change its identity.')
    changes={table:[row]}
    if old.get('Attachment ID'): row['Attachment ID']=old['Attachment ID']
    if old.get('Linked Action ID'): row['Linked Action ID']=old['Linked Action ID']
    if linked:
     if row.get('Linked Action ID'): raise ValueError('This record already has a linked action; update it in the action register.')
     aid='action-'+row['id']; action=e.validate('08_ACTIONS',{'id':aid,'Project':project,'Date Raised':str(today()),'Source':e.LABELS[table],'Finding / Action':action_text,'Risk':row.get('Risk','Medium'),'Responsible':action_owner,'Due Date':str(action_due),'Status':'Open','actor':actor},ids)
     changes['08_ACTIONS']=[action]; row['Linked Action ID']=aid
    if upload:
     content=upload.getvalue()
     if len(content)>1024*1024: raise ValueError('Photo must be no larger than 1 MB.')
     from PIL import Image
     Image.open(io.BytesIO(content)).verify()
     attachment=uid(); encoded=base64.b64encode(content).decode(); row['Attachment ID']=attachment
     changes['Evidence']=[{'id':attachment+f'-{i//40000:04}','project':project,'record_id':row['id'],'filename':upload.name,'mime':upload.type,'chunk':i//40000,'content':encoded[i:i+40000],'actor':actor} for i in range(0,len(encoded),40000)]
    for tab,rows in changes.items():
     for r in rows:
      if not e.permitted(role,assigned,project,tab,True): raise ValueError('No write access.')
    expected={tab:{r['id']:r.get('revision','') for r in t[tab]} for tab in changes}
    saved_records=store.save_many(changes,expected)
    st.session_state.pop('draft_'+table,None)
    st.success('Saved. The project and corporate dashboards now use this record.')
    if saved_records:
     for saved in saved_records:
      if saved['category']==table: st.code(saved['Record ID'],language=None)
    nav_button('Open project dashboard','Project dashboards',project=project)
   except ValueError as exc: st.error(str(exc))
   except Exception: st.error('Save could not be confirmed. Refresh and check the record ID before retrying. Your entries remain here.')
  st.link_button('Share this form',link('Field forms',project=project,form=table))
 elif page=='Operational registers':
  st.title('Operational registers'); project=pick_project(); options=list(e.FORMS); q=st.query_params.get('form',options[0]); table=st.selectbox('Register',options,index=options.index(q) if q in options else 0,format_func=e.LABELS.get)
  rows=[dict(r) for r in t[table] if r['Project']==project]
  status=st.selectbox('Status filter',['All']+sorted({r.get('Status','') for r in rows if r.get('Status')}))
  if status!='All': rows=[r for r in rows if r.get('Status')==status]
  search=st.text_input('Search records')
  if search: rows=[r for r in rows if search.lower() in json.dumps(r).lower()]
  for r in rows:
   if table=='08_ACTIONS': r['Days Open']=e.days_open(r); r['Days Overdue']=max(0,(today()-date.fromisoformat(r['Due Date'])).days) if e.overdue(r) else 0
  frame(rows); download(table,rows)
  nav_button('Add or update a record','Field forms',form=table,project=project)
  attached=[r for r in rows if r.get('Attachment ID')]
  if attached:
   rid=st.selectbox('View photo evidence',[r['id'] for r in attached]); record=next(r for r in attached if r['id']==rid)
   chunks=sorted([r for r in t['Evidence'] if r['id'].startswith(record['Attachment ID']+'-')],key=lambda r:int(r['chunk']))
   if chunks: st.image(base64.b64decode(''.join(r['content'] for r in chunks)),caption=chunks[0]['filename'],width=500)
 elif page=='Alerts & decisions':
  st.title('Alerts & management decisions'); al=e.alerts(t); states={r['id']:r for r in t['AlertState']}
  st.caption('Acknowledging records review ownership; it does not remove the underlying risk or its dashboard override.')
  frame([{**r,'Acknowledgement':states.get(r['id'],{}).get('status','New')} for r in al])
  if al:
   aid=st.selectbox('Review alert',[r['id'] for r in al]); a=next(r for r in al if r['id']==aid)
   nav_button('Open related register','Operational registers',form=a['Register'],project=a['Project'])
   note=st.text_input('Review note')
   if st.button('Acknowledge alert',disabled=not e.permitted(role,assigned,a['Project'],'AlertState',True)):
    try: save('AlertState',[{'id':aid,'project':a['Project'],'status':'Acknowledged','note':note,'actor':actor}]); st.success('Acknowledgement saved.')
    except Exception as exc: st.error(str(exc))
  st.subheader('Notification preview')
  st.info('External delivery is not connected. Preview messages below; no WhatsApp, email or Teams message is sent.')
  payload=[{'channel':'WhatsApp / Email / Teams','text':f"HSE {a['Level'].upper()} | {a['Project']} | {a['Issue']} | Responsible: {a['Responsible']} | {link('Operational registers',form=a['Register'],project=a['Project'])}",'deduplication_key':a['id']} for a in al if a['Level'] in ('Red','Orange')]
  st.download_button('Download notification preview',json.dumps(payload,indent=2),'notification-preview.json','application/json')
  nav_button('Issue corporate feedback','Field forms',form='13_CORP_FEEDBACK')
 elif page=='Standards library':
  st.title('Standards & client requirements'); st.info('These 17 requirement families came from your workbook. They are unverified templates; record the current clause, revision, applicability and evidence before marking project compliance.')
  frame(t['Standards']); download('Standards',t['Standards'])
  if role=='Corporate manager':
   with st.form('standard'):
    sid=st.selectbox('Requirement family',[r['id'] for r in t['Standards']]); old=next(r for r in t['Standards'] if r['id']==sid)
    reference=st.text_input('Authoritative reference'); revision=st.text_input('Verified revision'); verified=st.date_input('Verification date'); instruction=st.text_input('Verified control / clause'); reviewer=st.text_input('Reviewer')
    if st.form_submit_button('Save verified reference'):
     if not all((reference,revision,instruction,reviewer)): st.error('Complete all verification fields.')
     else:
      save('Standards',[{**old,'Authoritative Source / Reference':reference,'Revision':revision,'Verified Date':str(verified),'Title / Control':instruction,'Review Status':'Reference reviewed; project applicability still required','actor':actor}]); st.success('Reference saved.')
 elif page=='Management report':
  st.title('Management review'); start=st.date_input('Period start',today().replace(day=1)); end=st.date_input('Period end',today())
  if start>end: st.error('Invalid reporting period.'); return
  matrix=project_matrix(start,end); al=e.alerts(t)
  frame(matrix); st.subheader('Top management interventions'); frame(al[:10])
  report=f'<html><head><meta charset="utf-8"><title>HSE Management Review</title><style>body{{font:14px Arial;padding:32px}}table{{border-collapse:collapse;width:100%}}th,td{{padding:8px;border:1px solid #ddd}}th{{background:#164d56;color:white}}@media print{{body{{padding:0}}}}</style></head><body><h1>Corporate HSE management review</h1><p>{start} to {end} · Generated {datetime.now(TZ).isoformat()} · {html.escape(mode)}</p><p>Scores are provisional control assurance; review coverage. Alerts show current status.</p>'+pd.DataFrame(matrix).to_html(index=False,escape=True)+'<h2>Action required</h2>'+pd.DataFrame(al[:10]).to_html(index=False,escape=True)+'<h2>Corporate decisions</h2>'+pd.DataFrame(t['13_CORP_FEEDBACK']).to_html(index=False,escape=True)+'</body></html>'
  st.download_button('Download printable management report',report,'HSE-management-review.html','text/html')
  buff=io.BytesIO()
  with zipfile.ZipFile(buff,'w',zipfile.ZIP_DEFLATED) as z:
   for table in e.FORMS: z.writestr(table+'.csv',safe_csv(pd.DataFrame(t[table])))
  st.download_button('Export accessible project registers',buff.getvalue(),'HSE-registers.zip','application/zip')
 elif page=='Project settings':
  st.title('Projects & access'); frame(allowed); download('Projects',allowed)
  if role!='Corporate manager': st.info('Corporate managers maintain project settings.'); return
  project=pick_project(); old=next(r for r in allowed if r['id']==project)
  with st.form('project_settings'):
   row={**old,'actor':actor}
   for k,label in [('name','Project name'),('client','Client / owner'),('location','Location'),('lead','Project lead'),('hse_lead','HSE lead')]: row[k]=st.text_input(label,old.get(k,''))
   row['status']=st.selectbox('Project status',['Active','Inactive','On Hold'],index=['Active','Inactive','On Hold'].index(old['status']))
   if st.form_submit_button('Save project'):
    if not row['name'].strip(): st.error('Project name is required.')
    else: save('Projects',[row]); st.success('Project saved.')
  with st.expander('Add another project'):
   with st.form('new_project'):
    new_id=st.text_input('New project code',placeholder='P16'); new_name=st.text_input('New project name')
    if st.form_submit_button('Create project'):
     if not new_id.strip() or not new_name.strip() or any(p['id']==new_id.strip() for p in t['Projects']): st.error('Enter a unique code and project name.')
     else:
      save('Projects',[{'id':new_id.strip(),'name':new_name.strip(),'client':'','location':'','lead':'','hse_lead':'','status':'Active','target':90,'actor':actor}]); st.success('Project created. Refresh to open it and assign users in Team & access.')
  with st.form('configuration'):
   url=st.text_input('App URL for shared form links',cfg['base_url']); cutoff=st.time_input('Daily report cutoff (Riyadh)',time.fromisoformat(cfg['report_cutoff']))
   green=st.number_input('Green threshold',0.,100.,float(cfg['green_threshold'])); amber=st.number_input('Amber threshold',0.,100.,float(cfg['amber_threshold'])); orange=st.number_input('Orange threshold',0.,100.,float(cfg['orange_threshold']))
   if st.form_submit_button('Save dashboard settings'):
    if not 0<=orange<amber<green<=100 or not url.startswith(('http://','https://')): st.error('Enter a valid app URL and increasing thresholds.')
    else: save('Settings',[{'id':k,'value':str(v),'actor':actor} for k,v in {'base_url':url,'report_cutoff':cutoff.strftime('%H:%M'),'green_threshold':green,'amber_threshold':amber,'orange_threshold':orange}.items()]); st.success('Settings saved.')
  st.caption('Roles and project access are managed in Team & access. Project selection and URL parameters never grant access. Corporate viewers read all projects; project roles are restricted to assigned projects. Only corporate managers maintain settings, standards and corporate instructions.')
