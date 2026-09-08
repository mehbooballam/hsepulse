"""Organization onboarding, team invitations and master sheet connection screens."""
import json
import streamlit as st
import pandas as pd
from access_control import MembershipService, principal, ROLES, assignments, send_invitation, AccessDenied

def production_context(settings):
 from account_store import OrganizationStore
 from supabase_account_store import SupabaseAccountStore
 from google_connection import operational_store, complete
 from supabase_login import authenticate, sign_out
 app=dict(settings.get('application',{}))
 if not app.get('encryption_key') or not all(settings.get('supabase',{}).get(k) for k in ('url','publishable_key','secret_key')):
  st.title('Organization setup'); st.info('The application owner must configure the Supabase Auth, Supabase database connection and encryption key in hosting secrets.'); st.stop()
 claims,auth=authenticate(settings)
 @st.cache_resource
 def account_db(config,key): return SupabaseAccountStore(config,key)
 accounts=account_db(dict(settings['supabase']),app['encryption_key'])
 raw=OrganizationStore(accounts)
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
 if st.query_params.get('error'):
  st.warning('Google connection was not approved. You can try again from Master sheet.'); st.query_params.clear()
 if st.query_params.get('code') and st.query_params.get('state'):
  try: complete(accounts,claims,dict(settings['google_connection']),st.query_params['state'],st.query_params['code']); st.query_params.clear(); st.session_state['open_connection']=True; st.rerun()
  except ValueError as exc: st.error(str(exc)); st.stop()
  except Exception: st.error('Google authorization could not be completed. Return to Master sheet and reconnect.'); st.query_params.clear(); st.stop()
 if st.sidebar.button('Sign out'): sign_out(auth)
 st.sidebar.caption(user['email']+' · '+user['role'])
 # Connection failures still permit administrator repair screens.
 try: sheets=operational_store(accounts)
 except Exception: sheets=None; st.warning('The master Google connection needs attention. Ask the master administrator to reconnect.')
 raw=OrganizationStore(accounts,sheets)
 return accounts,raw,claims,user

def team_page(raw,claims,settings,demo=False):
 service=MembershipService(raw); t=raw.read(); admin=principal(t,claims)
 st.title('Team & access'); st.write('Invite colleagues, assign project access and manage membership.')
 if admin['role']!='Administrator': st.info('Only administrators can manage membership.'); return
 members,invites,roles,history=st.tabs(['Members','Invitations','Role permissions','Audit history'])
 with members:
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
   {'Role':'Administrator','Scope':'All projects','Manage team':'Yes','Connect master sheet':'Yes','Submit/edit':'All areas'},
   {'Role':'Corporate manager','Scope':'All projects','Manage team':'No','Connect master sheet':'No','Submit/edit':'All HSE areas'},
   {'Role':'Corporate viewer','Scope':'All projects','Manage team':'No','Connect master sheet':'No','Submit/edit':'Read only'},
   *[{'Role':r,'Scope':'Assigned projects','Manage team':'No','Connect master sheet':'No','Submit/edit':'Read only' if r=='Project viewer' else 'Project HSE records'} for r in ROLES[3:]]]),hide_index=True,width='stretch')
 with history:
  st.dataframe(pd.DataFrame(t['AccessAudit']),hide_index=True,width='stretch')
  st.caption('Access changes and operational write attempts are recorded. Never edit the private account database manually.')

def connection_page(accounts,raw,claims,settings,demo=False):
 import google_connection as gc
 st.title('Master sheet'); st.write('Connect your Google account, then choose the sheet that will power this organization.')
 if principal(raw.read(),claims)['role']!='Administrator': st.info('Only the master administrator can manage this connection.'); return
 if demo:
  st.info('Preview only. Configure the application’s Google OAuth client and account database to activate this connection.')
  st.button('Connect Google',disabled=True,type='primary'); return
 doc=accounts.document(); connection=doc.get('connection',{}); config=dict(settings.get('google_connection',{}))
 if connection.get('spreadsheet_id'):
  st.success('Connected · '+connection['title']); st.link_button('Open master sheet',connection['url'])
  st.caption('Project records are read and saved through this connection. Team members do not need direct spreadsheet access.')
 else: st.info('No master sheet connected yet.')
 if not all(config.get(k) for k in ('client_id','client_secret','redirect_uri')):
  st.warning('The application owner must configure Google OAuth once in hosting secrets. No service-account JSON is needed.'); return
 if st.button('Reconnect Google' if connection else 'Connect Google',type='primary'):
  st.session_state['google_auth_url']=gc.begin(accounts,claims,config)
 if st.session_state.get('google_auth_url'): st.link_button('Continue to Google',st.session_state['google_auth_url'],type='primary')
 if doc.get('candidate_google'):
  st.subheader('Choose your master sheet')
  choice=st.radio('Sheet source',['Create a new master sheet','Choose an existing spreadsheet'])
  if choice=='Create a new master sheet':
   title=st.text_input('Sheet name','HSE Pulse — Master Database')
   selected=None
  else:
   try:
    available=gc.list_sheets(accounts)
    selected=st.selectbox('Google spreadsheet',available,format_func=lambda f:f['name']) if available else None
   except Exception: selected=None; st.error('Could not list spreadsheets. Reconnect Google and approve the requested permissions.')
   title=None
  st.caption('The app adds its required register tabs. Existing compatible records are preserved. An incompatible tab stops setup without replacing it.')
  confirm=st.checkbox('Use this sheet as the organization’s master database'+(' (replaces the current connection)' if connection else ''))
  if st.button('Set as master sheet',disabled=not confirm):
   try:
    if not title and not selected: raise ValueError('Select a spreadsheet first.')
    gc.choose(accounts,claims,sheet_id=selected['id'] if selected else None,title=title)
    st.session_state.pop('google_auth_url',None); st.success('Master sheet connected.'); st.rerun()
   except ValueError as exc: st.error(str(exc))
   except Exception: st.error('Sheet setup could not be confirmed. Check Google permissions and retry; existing records were not overwritten.')
 if connection:
  with st.expander('Disconnect master sheet'):
   confirm=st.checkbox('Disconnect this organization from Google Sheets. The spreadsheet itself will remain in Google Drive.')
   if st.button('Disconnect',disabled=not confirm): gc.disconnect(accounts,claims); st.rerun()
