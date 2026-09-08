"""Receive Supabase's standard email callback without custom email templates.

Only the same-origin app/hosting shell is inspected. Tokens travel through the
Streamlit session channel, never query parameters, disk or third-party scripts.
"""
import streamlit as st

_JS = """
export default function(component) {
  const locations = [window];
  try { if (window.parent !== window && window.parent.location.origin === window.location.origin) locations.push(window.parent); } catch (_) {}
  for (const w of locations) {
    const h = new URLSearchParams(w.location.hash.slice(1));
    if (!h.has('access_token') || !h.has('refresh_token')) continue;
    const payload = {access_token:h.get('access_token'), refresh_token:h.get('refresh_token'), type:h.get('type')};
    w.history.replaceState(null, '', w.location.pathname + w.location.search);
    component.setTriggerValue('callback', payload);
    break;
  }
}
"""

def receive():
    callback=st.components.v2.component('supabase_email_callback',js=_JS)
    result=callback(key='supabase_email_callback',on_callback_change=lambda:None)
    if result.callback: st.session_state['supabase_pending_callback']=result.callback
    return st.session_state.get('supabase_pending_callback')
