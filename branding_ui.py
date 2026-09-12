"""Company administration, project logo previews and report-only contact options."""
import hashlib
import json
import streamlit as st
from branding import (COMPANY_KEY, FIELDS, company_profile, project_profile, profile,
                      validate_profile, upload_logo, logo_bytes, report_profiles)


def preview(profiles, project_name=''):
    for col, level, fallback in zip(st.columns(2), ('company','project'), ('Company',project_name or 'Project')):
        with col:
            st.caption(level.title() + ' branding')
            item = profiles.get(level, {})
            raw = logo_bytes(item)
            if raw: st.image(raw, width=150)
            else: st.caption('No '+level+' logo uploaded')
            st.write(item.get('name') or fallback)
            details = [item.get(k) for k in ('contact_person','email','phone','website') if item.get(k)]
            if details: st.caption(' · '.join(details))


def editor(current, scope, key):
    """Immediate upload preview, with an explicit save at the call site."""
    current = profile(current)
    draft = dict(current)
    upload = st.file_uploader(scope+' logo (PNG/JPEG, up to 1 MB)',type=['png','jpg','jpeg'],key=key+'_upload')
    remove = st.checkbox('Remove '+scope.lower()+' logo',key=key+'_remove',disabled=not current.get('logo'))
    if upload and remove:
        st.error('Choose either a new logo or removal, then save.'); return None
    if upload:
        try: draft['logo'] = upload_logo(upload.getvalue(),upload.name)
        except ValueError as exc: st.error(str(exc)); return None
    elif remove: draft.pop('logo',None)
    raw = logo_bytes(draft)
    if raw: st.image(raw,caption=scope+' logo preview',width=180)
    else: st.caption('No '+scope.lower()+' logo configured.')
    st.caption('Transparent PNG is recommended. Logos retain their proportions and are fitted to the report header.')
    cols=st.columns(2)
    for i,(field,(label,limit)) in enumerate(FIELDS.items()):
        with cols[i%2]:
            title = scope+' '+('display name' if field=='name' and scope=='Project' else 'name' if field=='name' else label.lower())
            func=st.text_area if field in ('address','contact_details') else st.text_input
            draft[field]=func(title,value=current.get(field,''),max_chars=limit,key=key+'_'+field).strip()
    return draft


def company_page(store, role, actor):
    st.title('Company branding')
    st.write('Set the organization logo and default company details used across HSE Pulse and its reports.')
    if role != 'Administrator':
        st.info('Only an administrator can change company branding.'); return
    tables=store.read()
    old=next((r for r in tables['Settings'] if r['id']==COMPANY_KEY),{})
    draft=editor(company_profile(tables),'Company','company_'+old.get('revision','new'))
    if st.button('Save company branding',type='primary',disabled=draft is None):
        try:
            validate_profile(draft)
            store.save('Settings',[{'id':COMPANY_KEY,'value':json.dumps(draft),'actor':actor}],{COMPANY_KEY:old.get('revision','')})
            st.session_state['flash']='Company branding saved.'; st.rerun()
        except ValueError as exc: st.error(str(exc))
    st.caption('Changes apply to the current workspace and new reports. Closed projects retain their closure branding; a report copy can explicitly use current company branding.')


def project_editor(store, tables, project, actor):
    with st.expander('Project branding & report details'):
        st.write('Add this project’s logo and default report contacts. Company branding is managed separately by the administrator.')
        draft=editor(project_profile(project),'Project','project_brand_'+project['id']+'_'+project.get('revision','new'))
        if draft is not None:
            st.subheader('Report header preview')
            preview({'company':company_profile(tables),'project':draft},project['name'])
        if st.button('Save project branding',type='primary',disabled=draft is None):
            try:
                validate_profile(draft)
                store.save('Projects',[{**project,'branding':draft,'actor':actor}],{project['id']:project.get('revision','')})
                st.session_state['flash']='Project branding saved.'; st.rerun()
            except ValueError as exc: st.error(str(exc))


def report_options(tables, project=None, can_brand_project=False, key='report'):
    """Customize a downloaded copy without changing stored/closed project data."""
    profiles=report_profiles(tables,project)
    with st.expander('Report branding & contact details'):
        st.caption('These options apply only to this downloaded report. They do not update company settings or project records.')
        if project and project.get('status')=='Closed':
            st.caption('The default logos and contacts are those saved at closure. Current branding or edited contacts are identified as report-copy customization.')
            if st.checkbox('Use current company branding for this report copy',key=key+'_current_company'):
                profiles['company']=company_profile(tables)
        if project and can_brand_project:
            upload=st.file_uploader('Project logo for this report copy (optional)',type=['png','jpg','jpeg'],key=key+'_report_logo')
            if upload:
                try: profiles['project']['logo']=upload_logo(upload.getvalue(),upload.name)
                except ValueError as exc: st.error(str(exc)); return None
        # Version the widget defaults when the selected saved profile changes.
        version=hashlib.sha256(json.dumps(profiles,sort_keys=True).encode()).hexdigest()[:12]
        for col,level in zip(st.columns(2),('company','project')):
            if level=='project' and not project: continue
            with col:
                st.markdown('**'+level.title()+' report contacts**')
                for field,(label,limit) in FIELDS.items():
                    if field=='name': continue
                    func=st.text_area if field in ('address','contact_details') else st.text_input
                    profiles[level][field]=func(level.title()+' report '+label.lower(),value=profiles[level].get(field,''),max_chars=limit,key=key+'_'+version+'_'+level+'_'+field).strip()
        preview(profiles,project['name'] if project else '')
        try:
            for value in profiles.values(): validate_profile(value)
        except ValueError as exc: st.error(str(exc)); return None
    return {level:{k:v for k,v in value.items() if v} for level,value in profiles.items()}


def workspace_company(tables,container=st.sidebar):
    company=company_profile(tables)
    if not any(company.values()): return
    with container:
        raw=logo_bytes(company)
        if raw: st.image(raw,width=150)
        if company.get('name'): st.caption(company['name'])
