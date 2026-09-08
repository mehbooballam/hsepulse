"""Supabase Auth sessions are isolated to each Streamlit browser session."""
from urllib.parse import urlencode, urlsplit
from supabase import create_client, ClientOptions
from access_control import AccessDenied, canonical_email


def client(config, admin=False):
    url=config['url'].rstrip('/')
    if urlsplit(url).scheme!='https':
        raise ValueError('Supabase requires an HTTPS project URL.')
    key=config['secret_key'] if admin else config['publishable_key']
    return create_client(url,key,options=ClientOptions(auto_refresh_token=False,persist_session=True,flow_type='implicit'))


def verified_claims(auth, token, url):
    # Never trust decoded JWTs or editable user_metadata for permissions.
    result=auth.get_user(token)
    user=result.user if result else None
    if not user or not user.id or not user.email_confirmed_at or getattr(user,'is_anonymous',False):
        raise AccessDenied('Sign in with a verified email account.')
    return {'sub':str(user.id),'iss':url.rstrip('/')+'/auth/v1',
            'email':canonical_email(user.email),'email_verified':True,'name':user.email}


def keep_session(state, response):
    if not response.session:
        raise AccessDenied('A valid sign-in session was not returned.')
    state['supabase_session']={'access_token':response.session.access_token,
                               'refresh_token':response.session.refresh_token}


def restore(auth, state, url):
    session=state.get('supabase_session')
    if not session: return None
    try:
        response=auth.set_session(session['access_token'],session['refresh_token'])
        keep_session(state,response)
        return verified_claims(auth,state['supabase_session']['access_token'],url)
    except Exception:
        state.pop('supabase_session',None)
        return None


def invite(config, invitation, token, base_url):
    if urlsplit(base_url).scheme!='https': raise ValueError('The app URL must use HTTPS.')
    redirect=base_url.rstrip('/')+'/?'+urlencode({'invitation':token})
    from supabase_auth.errors import AuthApiError
    try:
        client(config,admin=True).auth.admin.invite_user_by_email(
            invitation['email'],options={'redirect_to':redirect})
    except AuthApiError as exc:
        if exc.code not in ('email_exists','user_already_exists'): raise
        client(config).auth.reset_password_email(invitation['email'],{'redirect_to':redirect})


def sign_out(auth):
    import streamlit as st
    try: auth.sign_out({'scope':'local'})
    except Exception: pass
    st.session_state.clear()
    st.query_params.clear()
    st.rerun()


def authenticate(settings):
    import streamlit as st
    config=dict(settings['supabase']); auth=client(config).auth
    if st.query_params.get('error'):
        for key in ('error','error_code','error_description','state','code'):
            st.query_params.pop(key,None)
        st.info('That sign-in link has expired. Sign in with your email and password below.')
    from auth_callback import receive
    pending=receive()
    if pending:
        try:
            response=auth.set_session(pending['access_token'],pending['refresh_token'])
            checked=verified_claims(auth,response.session.access_token,config['url'])
        except Exception:
            st.session_state.pop('supabase_pending_callback',None)
            st.error('This email session has expired. Request a new invitation or password reset.'); st.stop()
        st.title('Confirm your account')
        st.write('Continue as '+checked['email'])
        if st.button('Continue with this account',type='primary'):
            kind=pending.get('type')
            st.session_state.clear(); keep_session(st.session_state,response)
            st.session_state['set_account_password']=kind in ('invite','recovery')
            st.rerun()
        if st.button('Cancel'): sign_out(auth)
        st.stop()
    token_hash=st.query_params.get('token_hash')
    auth_type=st.query_params.get('auth_type')
    if token_hash:
        st.title('Welcome to HSE Pulse')
        st.write('Confirm your email link to continue securely.')
        if auth_type not in ('invite','recovery','email'):
            st.error('This email link is invalid. Request a new one.'); st.stop()
        if st.button('Continue securely',type='primary'):
            try:
                response=auth.verify_otp({'token_hash':token_hash,'type':auth_type})
                verified_claims(auth,response.session.access_token,config['url'])
                st.session_state.clear()
                keep_session(st.session_state,response)
                st.session_state['set_account_password']=auth_type in ('invite','recovery')
                del st.query_params['token_hash']; del st.query_params['auth_type']
                st.rerun()
            except Exception: st.error('This link has expired or was already used. Request a new email.')
        st.stop()
    claims=restore(auth,st.session_state,config['url'])
    if not claims:
        _,panel,_=st.columns([1,2,1])
        with panel:
            st.title('Welcome to HSE Pulse')
            st.write('Sign in to manage your projects and daily HSE performance.')
            login,recovery=st.tabs(['Sign in','Forgot password'])
            with login:
                with st.form('supabase_login',clear_on_submit=True):
                    email=st.text_input('Work email'); password=st.text_input('Password',type='password')
                    submit=st.form_submit_button('Sign in',type='primary',width='stretch')
                if submit:
                    try:
                        result=auth.sign_in_with_password({'email':canonical_email(email),'password':password})
                        verified_claims(auth,result.session.access_token,config['url'])
                        st.session_state.clear(); keep_session(st.session_state,result); st.rerun()
                    except Exception: st.error('Sign-in failed. Check your email and password, or reset your password.')
            with recovery:
                with st.form('supabase_recover',clear_on_submit=True):
                    email=st.text_input('Account email')
                    send=st.form_submit_button('Send password reset email')
                if send:
                    try:
                        auth.reset_password_email(canonical_email(email),{'redirect_to':settings['application']['public_url'].rstrip('/')+'/?reset=1'})
                    except Exception: pass
                    st.info('If the account is eligible, a password reset email will arrive. Check your inbox and spam folder.')
            st.caption('Access is by invitation. Ask your administrator to invite your work email.')
            st.stop()
    if st.session_state.get('set_account_password'):
        st.title('Set your password')
        st.caption(claims['email'])
        with st.form('set_password',clear_on_submit=True):
            password=st.text_input('New password',type='password')
            confirmation=st.text_input('Confirm password',type='password')
            submit=st.form_submit_button('Save password and continue',type='primary')
        if submit:
            if len(password)<12: st.error('Use at least 12 characters.')
            elif password!=confirmation: st.error('The passwords do not match.')
            else:
                try:
                    auth.update_user({'password':password})
                    st.session_state.pop('set_account_password',None); st.rerun()
                except Exception: st.error('Password could not be updated. Use a stronger password or request a new reset link.')
        if st.button('Cancel and sign out'): sign_out(auth)
        st.stop()
    return claims,auth


def validate_current(settings):
    import streamlit as st
    config=dict(settings['supabase'])
    claims=restore(client(config).auth,st.session_state,config['url'])
    if not claims: raise AccessDenied('Your session expired. Sign in again.')
    return claims
