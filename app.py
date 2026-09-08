from datetime import date, timedelta
from pathlib import Path
import io
import json
import os
import zipfile
import pandas as pd
import streamlit as st
from catalog import RATES
from domain import (SCHEMAS, today, uid, stamp, make_demo, evaluate, display,
                    performance, validate_record, record_id)
from storage import MemoryStore
import enterprise
import enterprise_ui
import account_ui
from access_control import AuthorizedStore, SCHEMAS as ACCOUNT_SCHEMAS

ROOT=Path(__file__).parent
st.set_page_config(page_title='HSE Pulse',page_icon='🛡️',layout='wide')
import ui_shell
ui_shell.styles()
ui_shell.brand()

try: application_settings=dict(st.secrets)
except (FileNotFoundError,st.errors.StreamlitSecretNotFoundError): application_settings={}
production=bool(application_settings.get('application',{}).get('enabled',False))
production_context=None
if production:
    try: production_context=account_ui.production_context(application_settings)
    except ValueError as exc: st.error(str(exc)); st.stop()
    except Exception: st.error('Organization services are unavailable. Contact the application administrator.'); st.stop()
    accounts,organization,claims,member=production_context
    st.session_state['authenticated_identity']=(
        'Corporate manager' if member['role']=='Administrator' else member['role'],
        __import__('access_control').assignments(member),member['email'])

mode='Database' if production else 'Demo'
page=ui_shell.navigation(member['role'] if production else 'Administrator',demo=not production)
key='demo_store_v2' if mode=='Demo' else 'database_store_v3'
try:
    if production:
        st.session_state[key]=AuthorizedStore(organization,claims,lambda:__import__('supabase_login').validate_current(application_settings))
        st.session_state.pop(key+'_data',None)
    if key not in st.session_state:
        st.session_state[key]=MemoryStore({**make_demo(),**enterprise.demo()})
    store=st.session_state[key]
    data_key=key+'_data'
    if data_key not in st.session_state:
        st.session_state[data_key]=store.read(); st.session_state[key+'_sync']=stamp()
    if st.sidebar.button('Refresh data',icon=':material/refresh:',width='stretch'):
        st.session_state[data_key]=store.read(); st.session_state[key+'_sync']=stamp()
        st.rerun()
    tables=st.session_state[data_key]
except Exception as exc:
    st.error(f'Database unavailable ({type(exc).__name__}). Refresh or contact the administrator. No data was saved.')
    st.stop()

if mode=='Demo': st.caption('Preview workspace · Sample records · Changes are saved only for this session.')
if 'flash' in st.session_state: st.success(st.session_state.pop('flash'))
st.sidebar.caption('Last loaded: '+st.session_state[key+'_sync'][:19].replace('T',' ')+' UTC')
if page=='Team & access':
    if production:
        raw,who=organization,claims
    else:
        from access_control import MembershipService
        who={'email':'admin@example.test','email_verified':True,'sub':'demo-admin','iss':'demo','name':'Demo administrator'}
        for table in ACCOUNT_SCHEMAS: store.tables.setdefault(table,[])
        MembershipService(store).bootstrap(who,'admin@example.test')
        raw=store
    account_ui.team_page(raw,who,application_settings,demo=not production)
    st.stop()
if page=='Data & export':
    from export_ui import render_exports
    render_exports(store); st.stop()
if page in enterprise_ui.PAGES:
    enterprise_ui.render(page,store,mode); st.stop()
# Legacy KPI workspace is corporate-only when live, to prevent unscoped exports.
if mode=='Database':
    role,assigned,actor=enterprise_ui.identity(mode)
    if role!='Corporate manager':
        st.info('The advanced KPI workspace is restricted to corporate managers. Use your project workspace.'); st.stop()
defs=tables['Definitions']; defmap={d['id']:d for d in defs}; namemap={d['name']:d for d in defs}
sites={r['id']:r['name'] for r in tables['Sites']}

def commit(table,rows):
    expected={r['id']:r['revision'] for r in tables[table]}
    try:
        store.save(table,rows,expected)
    except Exception as exc:
        if isinstance(exc,ValueError): st.error(str(exc))
        else: st.error('Save could not be confirmed. Refresh and check the latest data before retrying. Your entries remain in the form.')
        return False
    # A readback failure must not make a successful write look like a failed save.
    st.session_state.pop(data_key,None)
    st.session_state['flash']=f'Saved {len(rows)} record(s) to '+('the demo session.' if mode=='Demo' else 'the database.')
    st.rerun()

def scoped_records(start,end,site_ids,shift):
    return [r for r in tables['Records'] if str(start)<=r['date']<=str(end) and r['site'] in site_ids and (shift=='All shifts' or r['shift']==shift)]

def summary(records,selected):
    result=[]
    for d in selected:
        value,status,count=evaluate(d,records,defs)
        result.append({'KPI':d['name'],'Category':d['category'],'Value':value,'Unit':d['unit'],'Target':d['target'],
                       'Status':performance(d,value,status),'Data status':status,'Records':count,'Owner':d['owner']})
    return pd.DataFrame(result)

def csv_bytes(frame):
    # Neutralise spreadsheet formulas in text fields in downloadable CSVs.
    safe=frame.copy()
    for c in safe.select_dtypes(include=['object','string']).columns:
        safe[c]=safe[c].map(lambda v: "'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v)
    return safe.to_csv(index=False).encode('utf-8-sig')

if page in ('Overview','Reports & export'):
    st.caption('OPERATIONS / PERFORMANCE')
    st.title('Daily HSE overview' if page=='Overview' else 'Reports & export')
    st.write('Track the work, verify the controls, and follow up where it matters.')
    a,b,c=st.columns([2,2,1])
    with a:
        period=st.date_input('Reporting period',value=(today()-timedelta(days=6),today()),max_value=today())
    with b: site_ids=st.multiselect('Sites',list(sites),default=list(sites),format_func=sites.get)
    with c: shift=st.selectbox('Shift',['All shifts','Day','Night'])
    if len(period)!=2: st.info('Select the start and end dates.'); st.stop()
    start,end=period
    records=scoped_records(start,end,site_ids,shift)
    daily=[d for d in defs if d['ready'] and d['daily'] and d['kind']!='derived']
    report=summary(records,[d for d in defs if d['ready']])
    cols=st.columns(4)
    for col,name in zip(cols,['Hours worked','Total recordable injury and illness cases','Hazards reported','Critical controls verified as effective']):
        d=namemap[name]; val,status,count=evaluate(d,records,defs)
        with col:
            st.metric({'Total recordable injury and illness cases':'Recordable cases','Critical controls verified as effective':'Effective critical controls'}.get(name,name),display(val,d['unit']))
            st.caption(f'{status} · {count} entries')
    if not records: st.info('No records in this period. Start with Daily entry or change the filters.')
    else:
        days=sorted({r['date'] for r in records})
        left,right=st.columns([1.6,1])
        with left:
            st.subheader('Control effectiveness')
            names=['Critical controls verified as effective','Permit-to-work audit compliance','PPE compliance']
            points=[]
            for day in days:
                for name in names:
                    value,_,_=evaluate(namemap[name],[r for r in records if r['date']==day],defs)
                    points.append({'Date':pd.Timestamp(day),'KPI':name,'Compliance (%)':value})
            st.line_chart(pd.DataFrame(points),x='Date',y='Compliance (%)',color='KPI',height=280)
        with right:
            st.subheader('Hazards & near misses')
            points=[]
            for day in days:
                for name in ['Hazards reported','Near misses reported']:
                    value,_,_=evaluate(namemap[name],[r for r in records if r['date']==day],defs)
                    points.append({'Date':pd.Timestamp(day),'Indicator':name,'Reports':value})
            st.bar_chart(pd.DataFrame(points),x='Date',y='Reports',color='Indicator',height=280)
    st.caption('Percentages are calculated from summed counts. Reporting volume is context, not a safety score. Snapshot KPIs use the latest selected shift per site, then sum across sites.')
    left,right=st.columns([1.5,1])
    with left:
        st.subheader('Daily KPI scorecard')
        score=summary(records,daily)
        status_filter=st.selectbox('Show',['All indicators','Needs attention','No data'])
        if status_filter!='All indicators': score=score[score['Status']==status_filter]
        st.dataframe(score,hide_index=True,width='stretch',column_config={'Value':st.column_config.NumberColumn(format='%.2f'),'Target':st.column_config.NumberColumn(format='%.2f')})
    with right:
        st.subheader('Actions needing attention')
        st.caption('Current action status, independent of the report date range.')
        due=[a for a in tables['Actions'] if a['site'] in site_ids and a['status']!='Closed' and a['due_date']<=str(today())]
        if due:
            st.dataframe(pd.DataFrame(due)[['title','priority','owner','due_date','status']],hide_index=True,width='stretch')
        else: st.success('No open actions due today or overdue in the selected sites.')
        st.subheader('Entry coverage')
        slots={(r['date'],r['site'],r['shift']) for r in records}
        expected=len(slots)*len(daily)
        actual=sum(r['kpi_id'] in {d['id'] for d in daily} for r in records)
        st.metric('Daily fields recorded',f'{actual} / {expected}' if expected else '—')
        st.caption('Coverage within shifts that have at least one record. Unreported shifts are not counted; this is not full attendance coverage.')
    st.subheader('Period injury rates')
    st.caption('Calculated only when numerator and hours cover exactly the same site/date/shift records. These are period rates, not single-day performance scores.')
    ratecols=st.columns(4)
    for col,name in zip(ratecols,RATES):
        d=namemap[name]; value,status,_=evaluate(d,records,defs)
        with col:
            st.metric(name,display(value)); st.caption(status)
    st.download_button('Download KPI summary CSV',csv_bytes(report),f'hse-summary-{start}-{end}.csv','text/csv')
    if page=='Reports & export':
        st.subheader('Records and backups')
        from export_ui import archive_bytes
        st.download_button('Download all current data (ZIP)',archive_bytes(tables),'hse-backup.zip','application/zip')
        st.caption('Backup includes all accessible operational categories as CSV and JSON. Account data is exported separately from Team & access. Prior revisions remain in the database.')
        st.dataframe(pd.DataFrame(records,columns=SCHEMAS['Records']),hide_index=True)
        st.download_button('Download filtered records CSV',csv_bytes(pd.DataFrame(records,columns=SCHEMAS['Records'])),'hse-records.csv','text/csv')
        st.subheader('Import daily records')
        columns=['date','site','shift','kpi_id','numerator','denominator','na','notes','actor']
        st.download_button('Download import template',pd.DataFrame(columns=columns).to_csv(index=False),'record-template.csv','text/csv')
        st.caption('Use IDs from the register and Sites list. Existing date/site/shift/KPI combinations create a new revision. No deletion occurs.')
        upload=st.file_uploader('Records CSV',type='csv')
        if upload:
            try:
                incoming=pd.read_csv(upload,dtype=str,keep_default_na=False)
                if set(columns)-set(incoming.columns): raise ValueError('Missing columns: '+', '.join(sorted(set(columns)-set(incoming.columns))))
                if len(incoming)>2000: raise ValueError('Import at most 2,000 rows per batch.')
                validated=[validate_record(r,defmap,sites) for r in incoming.to_dict('records')]
                if len({r['id'] for r in validated})!=len(validated): raise ValueError('The file contains duplicate date/site/shift/KPI records.')
                st.dataframe(incoming.head(30),hide_index=True)
                st.write(f'{len(validated)} valid records ready to import.')
                if st.button('Import validated records',disabled=not validated): commit('Records',validated)
            except (ValueError,KeyError,pd.errors.ParserError) as exc: st.error(str(exc))

elif page=='Daily entry':
    st.caption('OPERATIONS / SHIFT REPORT')
    st.title('Record today’s performance')
    st.write('Enter actual values and counts. Leave unmeasured fields blank; explain items marked not applicable.')
    a,b,c=st.columns([1,2,1])
    with a: day=st.date_input('Report date',today(),max_value=today())
    with b: site=st.selectbox('Site',list(sites),format_func=sites.get)
    with c: shift=st.selectbox('Shift',['Day','Night'])
    group=st.selectbox('Entry group',['Daily essentials']+sorted({d['category'] for d in defs if d['ready']}))
    chosen=[d for d in defs if d['ready'] and d['kind']!='derived' and (d['daily'] if group=='Daily essentials' else d['category']==group)]
    previous={r['kpi_id']:r for r in tables['Records'] if r['date']==str(day) and r['site']==site and r['shift']==shift}
    rows=[]
    for d in chosen:
        r=previous.get(d['id'],{})
        rows.append({'KPI ID':d['id'],'KPI':d['name'],'Value / numerator':r.get('numerator'),'Denominator':r.get('denominator'),
                     'N/A':bool(r.get('na',False)),'Notes':r.get('notes',''),'Count this':d['numerator_label'],'Out of':d['denominator_label']})
    if not rows: st.info('No active entry fields in this category. Configure an indicator in the KPI register.'); st.stop()
    with st.form(f'entry-{mode}-{day}-{site}-{shift}-{group}'):
        actor=st.text_input('Reporting person',placeholder='Name or staff ID')
        edited=st.data_editor(pd.DataFrame(rows),hide_index=True,width='stretch',height=560,
            disabled=['KPI ID','KPI','Count this','Out of'],column_config={
                'Value / numerator':st.column_config.NumberColumn(min_value=0.0),
                'Denominator':st.column_config.NumberColumn(min_value=0.0),
                'N/A':st.column_config.CheckboxColumn(), 'KPI':st.column_config.TextColumn(width='large')})
        st.caption('For ratios, enter the underlying counts—not the percentage. 0/0 produces N/A. Saving updates entered rows; blank fields do not delete previous records.')
        submitted=st.form_submit_button('Save shift report',type='primary')
    if submitted:
        try:
            pending=[]
            for r in edited.to_dict('records'):
                n=None if pd.isna(r['Value / numerator']) else r['Value / numerator']
                z=None if pd.isna(r['Denominator']) else r['Denominator']
                if n is None and z is None and not r['N/A']: continue
                pending.append(validate_record(dict(date=str(day),site=site,shift=shift,kpi_id=r['KPI ID'],numerator=n,denominator=z,na=int(r['N/A']),notes=r['Notes'],actor=actor),defmap,sites))
            if pending: commit('Records',pending)
            else: st.warning('Enter at least one value or an explained N/A.')
        except ValueError as exc: st.error(str(exc))

elif page=='KPI register':
    st.caption('MANAGEMENT / INDICATOR LIBRARY')
    st.title('KPI register')
    st.write(f'{len(defs)} indicators across {len(set(d["category"] for d in defs))} categories. Configure measurement rules and targets to match your operations.')
    st.info('Daily measures and four injury rates are configured. Broader catalogue entries start as drafts until you define their unit and counting rule. This is a configurable HSE register, not an official IOSH/OTHM checklist.')
    a,b=st.columns([2,1])
    with a: query=st.text_input('Search indicators',placeholder='Search by name or category')
    with b: category=st.selectbox('Category',['All categories']+sorted({d['category'] for d in defs}))
    matches=[d for d in defs if (category=='All categories' or d['category']==category) and query.lower() in (d['name']+' '+d['category']).lower()]
    df=pd.DataFrame(matches)
    if not df.empty:
        st.dataframe(df[['id','name','category','ready','daily','kind','unit','target','owner']],hide_index=True,width='stretch')
    st.download_button('Download complete KPI register',csv_bytes(pd.DataFrame(defs)),'kpi-register.csv','text/csv')
    st.subheader('Configure an indicator')
    if matches:
        kid=st.selectbox('Indicator',[d['id'] for d in matches],format_func=lambda k:defmap[k]['name'])
        d=defmap[kid]
        used=any(r['kpi_id']==kid for r in tables['Records'])
        locked=used or d['kind']=='derived'
        if locked: st.caption('Measurement rules are locked after recording data. Create a new indicator for a different definition. Targets and ownership can still change; targets apply to all displayed periods.')
        with st.form('definition-'+kid):
            a,b,c=st.columns(3)
            kinds=['sum','percentage','ratio','snapshot','derived']
            with a: kind=st.selectbox('Calculation',kinds,index=kinds.index(d['kind']),disabled=locked)
            with b: unit=st.text_input('Unit',d['unit'],disabled=locked)
            with c: owner=st.text_input('Owner',d['owner'])
            st.caption('sum = total across records; percentage = Σnumerator / Σdenominator × 100; ratio = Σnumerator / Σdenominator; snapshot = latest shift per site, summed across sites.')
            num=st.text_input('Numerator / value definition',d['numerator_label'],disabled=locked)
            den=st.text_input('Denominator definition',d['denominator_label'],disabled=locked)
            definition=st.text_area('Measurement rule and scope',d['definition'],disabled=locked)
            a,b,c=st.columns(3)
            with a: direction=st.selectbox('Target direction',['context','higher','lower'],index=['context','higher','lower'].index(d['direction']))
            with b: target=st.number_input('Target (optional)',value=d['target'],min_value=0.0)
            with c:
                ready=st.checkbox('Definition reviewed / active',bool(d['ready']))
                daily=st.checkbox('Show in daily entry',bool(d['daily']))
            if st.form_submit_button('Save indicator',type='primary'):
                if kind=='derived' and d['name'] not in RATES: st.error('Derived is reserved for the four built-in injury rates. Use ratio for a custom rate.')
                elif ready and (not unit.strip() or not num.strip() or not definition.strip() or (kind in ('ratio','percentage') and not den.strip())): st.error('Complete the unit, measurement rule and required input definitions.')
                elif kind=='percentage' and target is not None and target>100: st.error('A percentage target cannot exceed 100.')
                else: commit('Definitions',[{**d,'kind':kind,'unit':'%' if kind=='percentage' else unit,'owner':owner,'numerator_label':num,'denominator_label':den,'definition':definition,'direction':direction,'target':target,'ready':int(ready),'daily':int(daily),'actor':'Register editor'}])
    with st.expander('Add a custom indicator'):
        with st.form('custom'):
            name=st.text_input('New indicator name')
            cat=st.text_input('New indicator category','Custom indicators')
            if st.form_submit_button('Add draft indicator'):
                if not name.strip() or not cat.strip(): st.error('Enter a name and category.')
                elif name.strip().casefold() in {d['name'].casefold() for d in defs}: st.error('That indicator already exists.')
                else:
                    commit('Definitions',[dict(id='K-'+uid()[:10],name=name.strip(),category=cat.strip(),kind='sum',unit='count',numerator_label='',denominator_label='',ready=0,daily=0,direction='context',target=None,owner='',definition='',actor='Register editor')])
    with st.expander('Sites'):
        st.dataframe(pd.DataFrame(tables['Sites'])[['id','name']],hide_index=True)
        with st.form('site-add'):
            site_name=st.text_input('New site name')
            if st.form_submit_button('Add site'):
                if not site_name.strip(): st.error('Enter a site name.')
                elif site_name.strip().casefold() in {s.casefold() for s in sites.values()}: st.error('Site already exists.')
                else: commit('Sites',[{'id':'SITE-'+uid()[:8],'name':site_name.strip(),'actor':'Site administrator'}])

elif page=='Corrective actions':
    st.caption('MANAGEMENT / FOLLOW-UP')
    st.title('Corrective actions')
    a,b=st.columns(2)
    with a: site_filter=st.selectbox('Site filter',['All sites']+list(sites),format_func=lambda s:sites.get(s,s))
    with b: status_filter=st.selectbox('Status filter',['All','Open','In progress','Closed','Overdue'])
    actions=[a for a in tables['Actions'] if (site_filter=='All sites' or a['site']==site_filter) and
             (status_filter=='All' or a['status']==status_filter or (status_filter=='Overdue' and a['status']!='Closed' and a['due_date']<str(today())))]
    if actions: st.dataframe(pd.DataFrame(actions)[['id','title','priority','owner','due_date','status','closed_date','site']],hide_index=True,width='stretch')
    else: st.info('No actions match these filters.')
    choice=st.selectbox('Create or update an action',['New action']+[a['id'] for a in actions],format_func=lambda k:next((a['title'] for a in actions if a['id']==k),k))
    old=next((a for a in actions if a['id']==choice),{})
    with st.form('action-'+choice):
        title=st.text_input('Action',old.get('title',''))
        a,b,c=st.columns(3)
        with a:
            site=st.selectbox('Action site',list(sites),index=list(sites).index(old.get('site',next(iter(sites)))),format_func=sites.get)
            owner=st.text_input('Responsible person',old.get('owner',''))
        with b:
            priority=st.selectbox('Priority',['High','Medium','Low'],index=['High','Medium','Low'].index(old.get('priority','Medium')))
            due=st.date_input('Due date',date.fromisoformat(old['due_date']) if old else today())
        with c:
            status=st.selectbox('Action status',['Open','In progress','Closed'],index=['Open','In progress','Closed'].index(old.get('status','Open')))
            closed=st.date_input('Completion date (used when closed)',date.fromisoformat(old['closed_date']) if old.get('closed_date') else today(),max_value=today())
        notes=st.text_area('Progress / closure evidence',old.get('notes',''))
        if st.form_submit_button('Save action',type='primary'):
            if not title.strip() or not owner.strip(): st.error('Enter an action and responsible person.')
            elif status=='Closed' and not notes.strip(): st.error('Add closure evidence before closing the action.')
            else: commit('Actions',[dict(id=old.get('id',uid()),site=site,title=title.strip(),priority=priority,owner=owner.strip(),due_date=str(due),status=status,closed_date=str(closed) if status=='Closed' else '',notes=notes,actor=owner.strip())])
    st.caption('Action records are managed here. Daily action KPI entries are reported separately, so existing site-wide action totals are not silently replaced by this register.')
