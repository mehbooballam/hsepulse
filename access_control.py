"""Server-side identities, invitations and project authorization.

OIDC proves identity. Invitations authorize membership, never substitute for login.
All access mutations are audited and serialized within the single app process.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib, hmac, json, re, secrets, ssl, smtplib
from email.message import EmailMessage
from urllib.parse import urlencode, urlsplit
from domain import uid, stamp

META=['revision','updated_at','actor']
SCHEMAS={
 'Users':['id','email','name','subject','issuer','role','projects','status']+META,
 'Invitations':['id','email','role','projects','token_hash','expires_at','status','delivery','accepted_by']+META,
 'AccessAudit':['id','event','target','details']+META,
}
ROLES=['Administrator','Corporate manager','Corporate viewer','Project manager','HSE officer','Project lead','Project viewer']
CORPORATE={'Administrator','Corporate manager','Corporate viewer'}
WRITERS={'Administrator','Corporate manager','Project manager','HSE officer','Project lead'}
LEGACY={'Definitions','Records','Actions','Sites'}
GLOBAL={'Settings','Projects','Standards'}
class AccessDenied(ValueError): pass

def canonical_email(value):
 value=str(value).strip().lower()
 if not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+',value) or len(value)>254: raise ValueError('Enter a valid email address.')
 return value

def assignments(user):
 value=user.get('projects','[]')
 return json.loads(value) if isinstance(value,str) else list(value)

def permitted(user,table,project=None,write=False):
 if user.get('status')!='Active' or user.get('role') not in ROLES: return False
 role=user['role']
 if table in SCHEMAS: return role=='Administrator'
 if table in LEGACY: return role in ('Administrator','Corporate manager')
 if table in GLOBAL:
  if write: return role in ('Administrator','Corporate manager')
  return True
 if project is None: return False
 if role not in CORPORATE and project not in assignments(user): return False
 if write:
  if role not in WRITERS: return False
  if table=='13_CORP_FEEDBACK': return role in ('Administrator','Corporate manager')
 return True

def validate_grant(role,projects,tables):
 if role not in ROLES: raise ValueError('Unknown role.')
 projects=sorted(set(projects))
 if set(projects)-{p['id'] for p in tables['Projects']}: raise ValueError('Unknown project assignment.')
 if role not in CORPORATE and not projects: raise ValueError('Select at least one project for a project role.')
 return json.dumps(projects if role not in CORPORATE else [])

def audit(event,target,actor,details=''):
 return {'id':uid(),'event':event,'target':target,'details':details,'actor':actor}

def principal(tables,claims):
 # Missing email verification is a denial, not implicit approval.
 if claims.get('email_verified') is not True or not claims.get('sub') or not claims.get('iss'): raise AccessDenied('Sign in with a verified email identity.')
 email=canonical_email(claims.get('email',''))
 user=next((u for u in tables['Users'] if u['email']==email),None)
 if not user or user.get('status')!='Active': raise AccessDenied('No active membership. Ask an administrator for an invitation.')
 if user.get('subject')!=claims['sub'] or user.get('issuer')!=claims['iss']: raise AccessDenied('This membership belongs to another identity. Contact your administrator.')
 return user

class MembershipService:
 def __init__(self,store): self.store=store
 def _write(self,changes,tables):
  expected={k:{r['id']:r.get('revision','') for r in tables[k]} for k in changes}
  expected['_security_snapshot']=hashlib.sha256(json.dumps({k:tables[k] for k in SCHEMAS},sort_keys=True).encode()).hexdigest()
  self.store.save_many(changes,expected)
 def _admin(self,tables,claims):
  user=principal(tables,claims)
  if user['role']!='Administrator': raise AccessDenied('Administrator access is required.')
  return user
 def bootstrap(self,claims,bootstrap_email):
  from storage import _LOCK
  with _LOCK:
   t=self.store.read()
   if t['Users']: return
   if claims.get('email_verified') is not True or not claims.get('iss') or not claims.get('sub') or canonical_email(claims.get('email',''))!=canonical_email(bootstrap_email): raise AccessDenied('The organization administrator must complete initial setup.')
   u={'id':uid(),'email':canonical_email(claims['email']),'name':claims.get('name',''),'subject':claims['sub'],'issuer':claims['iss'],'role':'Administrator','projects':'[]','status':'Active','actor':claims['email']}
   self._write({'Users':[u],'AccessAudit':[audit('organization.bootstrap',u['id'],u['email'])]},t)
 def invite(self,claims,email,role,projects,days=7):
  from storage import _LOCK
  with _LOCK:
   t=self.store.read(); admin=self._admin(t,claims); email=canonical_email(email)
   if any(u['email']==email for u in t['Users']): raise ValueError('This email already has an account. Manage its existing access instead.')
   if not 1<=int(days)<=14: raise ValueError('Invitation validity must be 1–14 days.')
   token=secrets.token_urlsafe(32)
   invite={'id':uid(),'email':email,'role':role,'projects':validate_grant(role,projects,t),'token_hash':hashlib.sha256(token.encode()).hexdigest(),'expires_at':(datetime.now(timezone.utc)+timedelta(days=days)).isoformat(),'status':'Pending','delivery':'Not sent','accepted_by':'','actor':admin['email']}
   revoked=[{**r,'status':'Revoked','actor':admin['email']} for r in t['Invitations'] if r['email']==email and r['status']=='Pending']
   self._write({'Invitations':revoked+[invite],'AccessAudit':[audit('invitation.created',invite['id'],admin['email'],f'{email}; {role}; {invite["projects"]}')]},t)
   return invite,token
 def accept(self,claims,token):
  from storage import _LOCK
  with _LOCK:
   t=self.store.read()
   if claims.get('email_verified') is not True or not claims.get('iss') or not claims.get('sub'): raise AccessDenied('A verified email identity is required.')
   digest=hashlib.sha256(token.encode()).hexdigest()
   inv=next((r for r in t['Invitations'] if hmac.compare_digest(str(r['token_hash']),digest)),None)
   if not inv or inv['status']!='Pending' or datetime.fromisoformat(inv['expires_at'])<=datetime.now(timezone.utc): raise AccessDenied('This invitation is invalid, expired or already used.')
   email=canonical_email(claims.get('email',''))
   if email!=inv['email']: raise AccessDenied('Sign in with the email address that received this invitation.')
   if any(u['email']==email for u in t['Users']): raise AccessDenied('This account already exists. Ask an administrator to review it.')
   projects=validate_grant(inv['role'],assignments(inv),t)
   user={'id':uid(),'email':email,'name':claims.get('name',''),'subject':claims['sub'],'issuer':claims['iss'],'role':inv['role'],'projects':projects,'status':'Active','actor':email}
   self._write({'Users':[user],'Invitations':[{**inv,'status':'Accepted','accepted_by':user['id'],'token_hash':'','actor':email}],'AccessAudit':[audit('invitation.accepted',inv['id'],email)]},t)
   return user
 def change_user(self,claims,user_id,role,projects,status):
  from storage import _LOCK
  with _LOCK:
   t=self.store.read(); admin=self._admin(t,claims)
   old=next((u for u in t['Users'] if u['id']==user_id),None)
   if not old: raise ValueError('Account not found.')
   if status not in ('Active','Suspended'): raise ValueError('Invalid account status.')
   if old['role']=='Administrator' and old['status']=='Active' and (role!='Administrator' or status!='Active') and sum(u['role']=='Administrator' and u['status']=='Active' for u in t['Users'])<=1: raise ValueError('Keep at least one active administrator.')
   new={**old,'role':role,'projects':validate_grant(role,projects,t),'status':status,'actor':admin['email']}
   detail=json.dumps({'before':{k:old[k] for k in ('role','projects','status')},'after':{k:new[k] for k in ('role','projects','status')}})
   self._write({'Users':[new],'AccessAudit':[audit('user.access_changed',old['id'],admin['email'],detail)]},t)
 def revoke(self,claims,invite_id):
  from storage import _LOCK
  with _LOCK:
   t=self.store.read(); admin=self._admin(t,claims); inv=next(r for r in t['Invitations'] if r['id']==invite_id)
   if inv['status']!='Pending': raise ValueError('Only pending invitations can be revoked.')
   self._write({'Invitations':[{**inv,'status':'Revoked','token_hash':'','actor':admin['email']}],'AccessAudit':[audit('invitation.revoked',invite_id,admin['email'])]},t)
 def delivery(self,claims,invite_id,status):
  t=self.store.read(); admin=self._admin(t,claims); inv=next(r for r in t['Invitations'] if r['id']==invite_id)
  self._write({'Invitations':[{**inv,'delivery':status,'actor':admin['email']}],'AccessAudit':[audit('invitation.delivery',invite_id,admin['email'],status)]},t)

class AuthorizedStore:
 """Fresh membership check on every read and mutation, including fragment refresh."""
 def __init__(self,store,claims): self.raw=store; self.claims=dict(claims)
 def read(self):
  t=self.raw.read(); user=principal(t,self.claims); result={}
  for table,rows in t.items():
   if table in SCHEMAS: result[table]=[]; continue
   result[table]=[r for r in rows if permitted(user,table,r.get('Project',r.get('project')),False)]
   if table=='Projects' and user['role'] not in CORPORATE: result[table]=[r for r in rows if r['id'] in assignments(user)]
  return result
 def save(self,table,rows,expected=None): self.save_many({table:rows},{table:expected or {}})
 def save_many(self,changes,expected):
  from storage import _LOCK
  with _LOCK:
   t=self.raw.read(); user=principal(t,self.claims)
   clean=deepcopy(changes)
   for table,rows in clean.items():
    if table in SCHEMAS: raise AccessDenied('Use membership administration for access changes.')
    old={r['id']:r for r in t[table]}
    for r in rows:
     project=r.get('Project',r.get('project'))
     if not permitted(user,table,project,True): raise AccessDenied('You cannot change this project or area.')
     previous=old.get(r['id'])
     if previous and not permitted(user,table,previous.get('Project',previous.get('project')),True): raise AccessDenied('You cannot replace a record in another project.')
     r['actor']=user['email']
   clean['AccessAudit']=[audit('records.saved',','.join(changes),user['email'],json.dumps({k:[r['id'] for r in rows] for k,rows in changes.items()}))]
   expected={**expected,'AccessAudit':{}}
   self.raw.save_many(clean,expected)

def send_invitation(config,invitation,token,base_url):
 """Called only by the administrator's explicit Send invitation UI action."""
 if urlsplit(base_url).scheme!='https': raise ValueError('Invitation app URL must use HTTPS.')
 message=EmailMessage(); message['Subject']='Your invitation to HSE Pulse'; message['From']=config['from_email']; message['To']=invitation['email']
 link=base_url.rstrip('/')+'/?'+urlencode({'invitation':token})
 message.set_content(f"You have been invited to HSE Pulse as {invitation['role']}.\n\nOpen {link}\n\nSign in using {invitation['email']}. This invitation expires at {invitation['expires_at']}. If you did not expect this invitation, you can ignore this email.")
 mode=config.get('security','starttls'); port=int(config.get('port',587))
 if mode not in ('starttls','ssl'): raise ValueError('SMTP requires TLS.')
 cls=smtplib.SMTP_SSL if mode=='ssl' else smtplib.SMTP
 args={'host':config['host'],'port':port,'timeout':20}
 if mode=='ssl': args['context']=ssl.create_default_context()
 with cls(**args) as client:
  if mode=='starttls': client.starttls(context=ssl.create_default_context())
  client.login(config['username'],config['password']); client.send_message(message)
