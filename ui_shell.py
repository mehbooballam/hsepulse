"""Consistent navigation and visual presentation for the HSE workspace."""
import streamlit as st

NAV={
 'Corporate dashboard':('Portfolio overview','dashboard'),
 'Project dashboards':('Project dashboard','domain'),
 'Field forms':('New report','add_circle'),
 'Operational registers':('Records & registers','table_view'),
 'Alerts & decisions':('Alerts & decisions','notifications_active'),
 'Standards library':('Standards library','library_books'),
 'Management report':('Management report','summarize'),
 'Data & export':('Data & exports','download'),
 'Project settings':('Manage projects','settings'),
 'Team & access':('Team & access','group'),
 'Overview':('KPI overview','monitoring'),
 'Daily entry':('Daily KPI entry','edit_calendar'),
 'KPI register':('KPI catalogue','list_alt'),
 'Corrective actions':('KPI action tracker','task_alt'),
 'Reports & export':('KPI reports','assessment'),
}
GROUPS={
 'WORKSPACE':['Corporate dashboard','Project dashboards','Operational registers','Alerts & decisions'],
 'REPORTS & RESOURCES':['Management report','Standards library','Data & export'],
 'ADMINISTRATION':['Project settings','Team & access'],
}
KPI_PAGES=['Overview','Daily entry','KPI register','Corrective actions','Reports & export']

def styles():
 st.markdown('''<style>
 .block-container {padding-top:4.5rem;padding-bottom:3rem;max-width:1480px;}
 [data-testid="stAppViewContainer"] {background:#f6f8fb;}
 [data-testid="stSidebar"] {background:#fff;border-right:1px solid #e3eaf0;}
 [data-testid="stSidebarUserContent"] {padding-top:1.25rem;}
 h1 {font-size:2rem!important;font-weight:750!important;letter-spacing:-.065rem;color:#172c40;}
 h2,h3 {color:#243c50;letter-spacing:-.02rem;}
 [data-testid="stMetric"] {background:#fff;border:1px solid #e3eaf0;border-radius:14px;padding:18px 20px;}
 [data-testid="stMetricLabel"] {color:#52677c;}
 [data-testid="stMetricValue"] {font-size:1.9rem;}
 [data-testid="stForm"] {background:#fff;border:1px solid #dde6ee;border-radius:16px;padding:1.25rem;}
 .stButton button,.stDownloadButton button,.stLinkButton a {min-height:2.65rem;border-radius:9px;font-weight:600;}
 button:focus-visible,a:focus-visible {outline:3px solid #62aeb6!important;outline-offset:3px;}
 [data-testid="stSidebar"] .stButton button {justify-content:flex-start!important;text-align:left;width:100%;font-size:.92rem;}
 [data-testid="stSidebar"] .stButton button > div {width:100%;justify-content:flex-start!important;}
 [data-testid="stSidebar"] .stButton button [data-has-shortcut] {justify-content:flex-start!important;}
 [data-testid="stSidebar"] button[kind="secondary"] {border-color:transparent;background:transparent;color:#40566b;box-shadow:none;}
 [data-testid="stSidebar"] button[kind="secondary"]:hover {background:#edf5f6;color:#086974;}
 [data-testid="stSidebar"] button[kind="primary"] {background:#e4f3f1;border:1px solid #b9dfda;color:#086759;box-shadow:none;}
 [data-testid="stSidebar"] .st-key-new_report button {background:#087f8c;color:white;border-color:#087f8c;}
 [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap:.4rem;}
 [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {font-size:.75rem;line-height:1.5;}
 [data-testid="stTabs"] button[role="tab"] {min-height:2.75rem;padding:0 1rem;font-weight:600;}
 .hse-brand {display:flex;align-items:center;gap:12px;margin:0 0 1.2rem;}
 .hse-brand-icon {background:#087f8c;color:#fff;padding:10px;border-radius:12px;font-size:19px;line-height:1;}
 .hse-brand-name {font-size:22px;font-weight:800;letter-spacing:-.6px;color:#153248;}
 .hse-brand-sub {font-size:11px;color:#688095;letter-spacing:.05em;text-transform:uppercase;}
 @media(max-width:768px){.block-container{padding:3.7rem 1rem 2rem;}h1{font-size:1.6rem!important;}[data-testid="stMetric"]{padding:12px;}[data-testid="stForm"]{padding:1rem;}}
 </style>''',unsafe_allow_html=True)

def brand():
 with st.sidebar:
  st.markdown('<div class="hse-brand"><div class="hse-brand-icon">✚</div><div><div class="hse-brand-name">HSE Pulse</div><div class="hse-brand-sub">Safety management</div></div></div>',unsafe_allow_html=True)

def allowed_pages(role, demo=False):
 pages=[p for values in GROUPS.values() for p in values]
 if not demo and role not in ('Administrator','Corporate manager'): pages.remove('Project settings')
 if not demo and role!='Administrator': pages.remove('Team & access')
 if demo or role in ('Administrator','Corporate manager','Project manager','HSE officer','Project lead'): pages.append('Field forms')
 if demo or role in ('Administrator','Corporate manager'): pages+=KPI_PAGES
 return pages

def go(page, **params):
 st.query_params.update({'view':page, **params})

def navigation(role, demo=False):
 available=allowed_pages(role,demo)
 requested=st.query_params.get('view','Corporate dashboard')
 page=requested if requested in available else 'Corporate dashboard'
 def item(target,key=None):
  label,icon=NAV[target]
  st.button(label,key=key or 'nav_'+target,icon=':material/'+icon+':',
            type='primary' if target==page else 'secondary',width='stretch',
            on_click=go,args=(target,))
 with st.sidebar:
  if 'Field forms' in available:
   with st.container(key='new_report'): item('Field forms')
  for label,targets in GROUPS.items():
   targets=[p for p in targets if p in available]
   if not targets: continue
   st.caption(label)
   for target in targets: item(target)
  if any(p in available for p in KPI_PAGES):
   with st.expander('Advanced KPI tools',expanded=page in KPI_PAGES):
    for target in KPI_PAGES:
     if target in available: item(target)
  st.divider()
  st.caption('Riyadh time · '+('Demo workspace' if demo else 'Organization workspace'))
 st.caption('HSE PULSE  /  '+NAV[page][0].upper())
 return page
