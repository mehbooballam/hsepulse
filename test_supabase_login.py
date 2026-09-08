import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock,patch
from supabase_login import verified_claims,restore,keep_session,invite,client
from access_control import AccessDenied

URL='https://example.supabase.co'
class SupabaseLoginTests(unittest.TestCase):
 def user(self,**changes):
  return NS(**{'id':'stable-id','email':'Owner@example.com','email_confirmed_at':'2026-09-08','is_anonymous':False,'user_metadata':{'role':'Administrator'},**changes})
 def test_identity_is_verified_remotely_and_metadata_ignored(self):
  auth=Mock(); auth.get_user.return_value=NS(user=self.user())
  claims=verified_claims(auth,'access',URL)
  auth.get_user.assert_called_once_with('access')
  self.assertEqual(claims['email'],'owner@example.com')
  self.assertEqual(claims['iss'],URL+'/auth/v1')
  self.assertNotIn('role',claims)
 def test_unconfirmed_and_anonymous_denied(self):
  for user in [None,self.user(email_confirmed_at=None),self.user(is_anonymous=True)]:
   auth=Mock(); auth.get_user.return_value=NS(user=user)
   with self.assertRaises(AccessDenied): verified_claims(auth,'access',URL)
 def test_refresh_rotates_tokens_then_checks_user(self):
  auth=Mock(); auth.set_session.return_value=NS(session=NS(access_token='new',refresh_token='rotated'))
  auth.get_user.return_value=NS(user=self.user())
  state={'supabase_session':{'access_token':'old','refresh_token':'old-refresh'}}
  self.assertTrue(restore(auth,state,URL))
  self.assertEqual(state['supabase_session']['refresh_token'],'rotated')
  auth.get_user.assert_called_once_with('new')
 def test_failed_remote_verification_clears_session(self):
  auth=Mock(); auth.set_session.return_value=NS(session=NS(access_token='new',refresh_token='new-refresh'))
  auth.get_user.side_effect=RuntimeError('deleted or invalid')
  state={'supabase_session':{'access_token':'old','refresh_token':'refresh'}}
  self.assertIsNone(restore(auth,state,URL)); self.assertNotIn('supabase_session',state)
 def test_no_session_rejected(self):
  with self.assertRaises(AccessDenied): keep_session({},NS(session=None))
 def test_invite_is_addressed_and_does_not_set_roles_in_metadata(self):
  with patch('supabase_login.client') as factory:
   invite({'secret_key':'server-only'},{'email':'invited@example.com'},'one-use','https://app.example.com')
   args=factory.return_value.auth.admin.invite_user_by_email.call_args
   self.assertEqual(args.args,('invited@example.com',))
   self.assertEqual(args.kwargs['options'],{'redirect_to':'https://app.example.com/?invitation=one-use'})
 def test_auth_clients_are_never_shared(self):
  config={'url':URL,'publishable_key':'public','secret_key':'private'}
  with patch('supabase_login.create_client') as create:
   client(config); client(config,admin=True)
   self.assertEqual(create.call_args_list[0].args[1],'public')
   self.assertEqual(create.call_args_list[1].args[1],'private')
   self.assertFalse(create.call_args.kwargs['options'].auto_refresh_token)
 def test_supabase_store_rejects_concurrent_change(self):
  from supabase_account_store import SupabaseAccountStore
  from cryptography.fernet import Fernet
  from storage import ConflictError
  db=object.__new__(SupabaseAccountStore); db.cipher=Fernet(Fernet.generate_key()); db.api=Mock()
  db._row=Mock(return_value={'version':2,'payload':db.encode({'tables':{}})})
  query=db.api.table.return_value.update.return_value
  query.eq.return_value.eq.return_value.execute.return_value=NS(data=[])
  with self.assertRaises(ConflictError): db.mutate(lambda d:d.update(test=True))
  self.assertEqual(query.eq.return_value.eq.call_args.args,('version',2))
 def test_invite_retry_for_existing_identity_uses_new_grant(self):
  from supabase_auth.errors import AuthApiError
  with patch('supabase_login.client') as factory:
   factory.return_value.auth.admin.invite_user_by_email.side_effect=AuthApiError('exists',422,'email_exists')
   invite({}, {'email':'invited@example.com'},'new-token','https://app.example.com')
   factory.return_value.auth.reset_password_email.assert_called_once_with('invited@example.com',{'redirect_to':'https://app.example.com/?invitation=new-token'})
 def test_google_login_preserves_invitation_and_requests_identity_only(self):
  from supabase_login import google_sign_in_url
  auth=Mock(); auth.sign_in_with_oauth.return_value=NS(url='https://provider.example.com')
  settings={'application':{'public_url':'https://app.example.com'}}
  self.assertEqual(google_sign_in_url(auth,settings,'invite-token'),'https://provider.example.com')
  options=auth.sign_in_with_oauth.call_args.args[0]['options']
  self.assertEqual(options['redirect_to'],'https://app.example.com/?invitation=invite-token')
  self.assertEqual(options['scopes'],'openid email profile')
 def test_login_screen_has_no_open_signup(self):
  from streamlit.testing.v1 import AppTest
  at=AppTest.from_string("""import streamlit as st
from supabase_login import authenticate
authenticate({'supabase':{'url':'https://example.supabase.co','publishable_key':'sb_publishable_example'},'application':{'public_url':'https://app.example.com'}})
""").run()
  self.assertFalse(at.exception)
  self.assertEqual([x.label for x in at.button],['Sign in','Send password reset email'])

if __name__=='__main__': unittest.main()
