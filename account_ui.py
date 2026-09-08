"""Organization onboarding, invitations and access administration."""
import json
import streamlit as st
import pandas as pd
from access_control import MembershipService, principal, ROLES, assignments, send_invitation, AccessDenied

def production_context(settings):
 from supabase_account_store import SupabaseAccountStore
 from database_store import DatabaseStore
 from supabase_login import authenticate, sign_out
 app=dict(settings.get('application',{}))
 if not app.get('encryption_key') or not all(settings.get('supabase',{}).get(k) for k in ('url','publishable_key','secret_key')):
  st.title('Organization setup'); st.info('The application owner must configure the Supabase Auth, Supabase database connection and encryption key in hosting secrets.'); st.stop()
 claims,auth=authenticate(settings)
 @st.cache_resource
 def account_db(config,key): return SupabaseAccountStore(config,key)
 accounts=account_db(dict(settings['supabase']),app['encryption_key'])
 raw=DatabaseStore(accounts)
 service=MembershipService(raw)
 if not accounts.read()['Users']:
  service.bootstrap(claims,app.get('bootstrap_admin_email',''))
 token=st.query_params.get('invitation')
 if token:
  st.title('Join your HSE workspace')
  st.write('Signed in as '+claims.get('email',''))
  if st.button('Accept invitation',type='primary'):
   try: service.accept(claims,token); st.query_params.clear(); st.rerun()
   except ValueError as exc: st.error(str(exc))
  if st.button('Use another account'): sign_out(auth)
  st.stop()
 try: user=principal(accounts.read(),claims)
 except AccessDenied as exc:
  st.title('Access pending'); st.info(str(exc))
  if st.button('Sign out'): sign_out(auth)
  st.stop()
 with st.sidebar.expander('Your account'):
  st.write(user['email'])
  st.caption(user['role'])
  if st.button('Sign out',icon=':material/logout:',width='stretch'): sign_out(auth)
 return accounts,raw,claims,user

def team_page(raw,claims,settings,demo=False):
 service=MembershipService(raw); t=raw.read(); admin=principal(t,claims)
 st.title('Team & access'); st.write('Invite colleagues, assign project access and manage membership.')
 if admin['role']!='Administrator': st.info('Only administrators can manage membership.'); return
 members,invites,roles,history=st.tabs(['Members','Invitations','Role permissions','Audit history'])
 with members:
  from export_ui import export_buttons
  export_buttons('Members',[{k:v for k,v in r.items() if k not in ('subject','issuer')} for r in t['Users']])
  st.dataframe(pd.DataFrame([{k:u.get(k) for k in ('id','name','email','role','projects','status')} for u in t['Users']]),hide_index=True,width='stretch')
  target=st.selectbox('Manage member',[u['id'] for u in t['Users']],format_func=lambda x:next(u['email'] for u in t['Users'] if u['id']==x))
  old=next(u for u in t['Users'] if u['id']==target)
  with st.form('membership_'+target):
   role=st.selectbox('Assigned role',ROLES,index=ROLES.index(old['role']))
   projects=st.multiselect('Project access',[p['id'] for p in t['Projects']],default=assignments(old))
   status=st.selectbox('Account status',['Active','Suspended'],index=0 if old['status']=='Active' else 1)
   if st.form_submit_button('Save access changes'):
    try: service.change_user(claims,target,role,projects,status); st.success('Access updated. It is checked again on every request and dashboard refresh.'); st.rerun()
    except ValueError as exc: st.error(str(exc))
 with invites:
  export_buttons('Invitations',[{k:v for k,v in r.items() if k!='token_hash'} for r in t['Invitations']])
  supabase=dict(settings.get('supabase',{})); ready=bool(supabase.get('secret_key')) and not demo
  if not ready: st.info('Email delivery is not configured. You can preview invitation creation; no email will be sent.')
  with st.form('invite_member'):
   email=st.text_input('Email address'); role=st.selectbox('Invitation role',ROLES,index=ROLES.index('Project viewer'))
   projects=st.multiselect('Invited projects',[p['id'] for p in t['Projects']]); days=st.slider('Valid for days',1,14,7)
   submitted=st.form_submit_button('Send invitation' if ready else 'Create invitation preview',type='primary')
  if submitted:
   try:
    inv,token=service.invite(claims,email,role,projects,days)
    if ready:
     try:
      from supabase_login import invite
      invite(supabase,inv,token,settings['application']['public_url'])
     except Exception:
      service.delivery(claims,inv['id'],'Unconfirmed'); st.error('Email delivery could not be confirmed. Re-invite to issue a new link; the old link will be revoked.')
     else: service.delivery(claims,inv['id'],'Sent'); st.success('Invitation email sent.')
    else: st.success('Invitation preview created. Configure email and re-invite to send a usable link.')
   except ValueError as exc: st.error(str(exc))
  rows=raw.read()['Invitations']
  st.dataframe(pd.DataFrame([{k:r.get(k) for k in ('id','email','role','projects','expires_at','status','delivery')} for r in rows]),hide_index=True,width='stretch')
  pending=[r for r in rows if r['status']=='Pending']
  if pending:
   selected=st.selectbox('Pending invitation',[r['id'] for r in pending],format_func=lambda x:next(r['email'] for r in pending if r['id']==x))
   if st.button('Revoke invitation'): service.revoke(claims,selected); st.rerun()
  st.caption('Re-inviting the same email revokes its earlier pending links. Invitation links expire and require the matching verified Supabase account.')
 with roles:
  st.dataframe(pd.DataFrame([
   {'Role':'Administrator','Scope':'All projects','Manage team':'Yes','Manage database':'Yes','Submit/edit':'All areas'},
   {'Role':'Corporate manager','Scope':'All projects','Manage team':'No','Manage database':'No','Submit/edit':'All HSE areas'},
   {'Role':'Corporate viewer','Scope':'All projects','Manage team':'No','Manage database':'No','Submit/edit':'Read only'},
   *[{'Role':r,'Scope':'Assigned projects','Manage team':'No','Manage database':'No','Submit/edit':'Read only' if r=='Project viewer' else 'Project HSE records'} for r in ROLES[3:]]]),hide_index=True,width='stretch')
 with history:
  export_buttons('Access audit',t['AccessAudit'])
  st.dataframe(pd.DataFrame(t['AccessAudit']),hide_index=True,width='stretch')
  st.caption('Access changes and operational write attempts are recorded. Never edit the private account database manually.')
