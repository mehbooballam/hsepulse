import base64
import io
import json
import unittest
from copy import deepcopy
from PIL import Image
from pypdf import PdfReader
from branding import (COMPANY_KEY, upload_logo, validate_profile, company_profile,
                      project_profile, report_profiles, html_header)
from storage import MemoryStore, ConflictError
from domain import initial_tables
import enterprise as e
from access_control import SCHEMAS, MembershipService, AuthorizedStore, AccessDenied
from test_access import ADMIN, USER
from project_lifecycle import close_project
from project_report import closure_pdf


def logo(color='blue',size=(240,80)):
    data=io.BytesIO();Image.new('RGBA',size,color).save(data,format='PNG')
    return upload_logo(data.getvalue(),'training.png')


class BrandingTests(unittest.TestCase):
    def setUp(self):
        self.raw=MemoryStore({**initial_tables(),**e.demo(),**{k:[] for k in SCHEMAS}})
        self.members=MembershipService(self.raw);self.members.bootstrap(ADMIN,ADMIN['email'])
        self.admin=AuthorizedStore(self.raw,ADMIN)
        self.company={'name':'Training company','logo':logo(),'website':'https://example.test','contact_person':'Company manager'}

    def save_company(self,value=None):
        old=next((r for r in self.raw.read()['Settings'] if r['id']==COMPANY_KEY),{})
        self.admin.save('Settings',[{'id':COMPANY_KEY,'value':json.dumps(value or self.company)}],{COMPANY_KEY:old.get('revision','')})

    def test_only_admin_changes_company_branding_including_batches(self):
        self.save_company()
        _,token=self.members.invite(ADMIN,USER['email'],'Corporate manager',[])
        self.members.accept(USER,token);manager=AuthorizedStore(self.raw,USER)
        old=next(r for r in self.raw.read()['Settings'] if r['id']==COMPANY_KEY)
        before=self.raw.read()
        with self.assertRaisesRegex(AccessDenied,'administrator'):
            manager.save_many({'Settings':[{**old,'value':json.dumps({'name':'Changed'})}],
                               'Projects':[{**before['Projects'][0],'name':'Should roll back'}]},
                              {'Settings':{COMPANY_KEY:old['revision']},'Projects':{before['Projects'][0]['id']:before['Projects'][0]['revision']}})
        self.assertEqual(before,self.raw.read())
        self.assertEqual(company_profile(manager.read())['name'],'Training company')

    def test_project_branding_scope_revision_and_closure_snapshot(self):
        self.save_company()
        p=self.raw.read()['Projects'][0]
        brand={'name':'West project','logo':logo('red'),'contact_person':'Site lead'}
        self.admin.save('Projects',[{**p,'branding':brand}],{p['id']:p['revision']})
        with self.assertRaises(ConflictError):
            self.admin.save('Projects',[{**p,'branding':{}}],{p['id']:p['revision']})
        t=self.admin.read();p=t['Projects'][0]
        self.assertFalse(project_profile(t['Projects'][1]))
        closed=close_project(p,t,ADMIN['email'],'Handover complete')
        self.admin.save('Projects',[closed],{p['id']:p['revision']})
        self.save_company({'name':'New company','logo':logo('green')})
        t=self.admin.read();closed=t['Projects'][0]
        profiles=report_profiles(t,closed)
        self.assertEqual(profiles['company']['name'],'Training company')
        self.assertEqual(profiles['project']['name'],'West project')
        with self.assertRaisesRegex(ValueError,'read-only'):
            self.admin.save('Projects',[{**closed,'branding':{}}],{closed['id']:closed['revision']})
        _,token=self.members.invite(ADMIN,USER['email'],'Project viewer',['P01'])
        self.members.accept(USER,token);viewer=AuthorizedStore(self.raw,USER)
        self.assertEqual([p['id'] for p in viewer.read()['Projects']],['P01'])
        with self.assertRaises(AccessDenied):
            viewer.save('Projects',[{**t['Projects'][1],'branding':brand}],{'P02':t['Projects'][1]['revision']})

    def test_upload_limits_corrupt_content_and_safe_website(self):
        for content in (b'not an image',b'x'*(1024*1024+1)):
            with self.assertRaises(ValueError):upload_logo(content)
        data=io.BytesIO();Image.new('RGB',(4097,1)).save(data,format='PNG')
        with self.assertRaisesRegex(ValueError,'dimensions'):upload_logo(data.getvalue())
        data=io.BytesIO();Image.new('RGB',(30,15)).save(data,format='JPEG')
        converted=upload_logo(data.getvalue(),'brand.jpg')
        self.assertTrue(base64.b64decode(converted['data']).startswith(b'\x89PNG'))
        validate_profile({'logo':converted})
        for value in ({'website':'javascript:alert(1)'},{'name':'x'*161},{'email':'broken'}, {'logo':{'data':'bad'}}):
            with self.assertRaises(ValueError):validate_profile(value)
        self.admin.save('Projects',[{**self.raw.read()['Projects'][0],'branding':{'logo':logo()}}],{'P01':self.raw.read()['Projects'][0]['revision']})

    def test_pdf_dual_logos_contacts_and_lossless_customization(self):
        self.save_company()
        t=self.raw.read();p={**t['Projects'][0],'branding':{'name':'Sample project','logo':logo('red')}}
        closed=close_project(p,t,'Manager','Complete')
        profiles=report_profiles(t,closed)
        profiles['project']['contact_person']='Report recipient'
        pdf=PdfReader(io.BytesIO(closure_pdf(t,closed,profiles)))
        text='\n'.join(p.extract_text() for p in pdf.pages)
        self.assertIn('Report recipient',text);self.assertIn('Training company',text)
        self.assertIn('Report-copy customization',text)
        self.assertGreaterEqual(len(pdf.pages[0].images),2)
        attached=json.loads(pdf.attachments['project-data.json'][0])
        self.assertEqual(attached['Report branding']['project']['contact_person'],'Report recipient')
        self.assertNotIn('contact_person',attached['Projects'][0]['branding'])
        self.assertEqual(attached['Report branding']['company']['logo']['data'],self.company['logo']['data'])
        self.assertNotIn(self.company['logo']['data'][:80],text)
        self.assertNotIn('Users',attached)

    def test_legacy_closure_and_html_header_escape(self):
        self.save_company()
        p=self.raw.read()['Projects'][0]
        p={**p,'status':'Closed','closure_context':'{"Settings":[],"Standards":[]}'}
        self.assertEqual(report_profiles(self.raw.read(),p),{'company':{},'project':{}})
        profiles={'company':{'name':'<script>bad()</script>','logo':logo()},'project':{'name':'Project & one','contact_details':'Line 1\nLine 2'}}
        header=html_header(profiles,'Project')
        self.assertNotIn('<script>',header);self.assertIn('&lt;script&gt;',header)
        self.assertIn('data:image/png;base64,',header);self.assertIn('Line 1<br/>Line 2',header)


class BrandingUITests(unittest.TestCase):
    def test_company_project_contact_save_and_navigation_permissions(self):
        from streamlit.testing.v1 import AppTest
        from ui_shell import allowed_pages
        self.assertIn('Company branding',allowed_pages('Administrator'))
        for role in ('Corporate manager','Project manager','Corporate viewer','Project viewer'):
            self.assertNotIn('Company branding',allowed_pages(role))
        at=AppTest.from_file('app.py',default_timeout=60);at.secrets['application']={'enabled':False}
        at.query_params['view']='Company branding';at.run()
        next(w for w in at.text_input if w.label=='Company name').set_value('Training company')
        next(w for w in at.text_input if w.label=='Company website').set_value('https://example.test')
        next(w for w in at.button if w.label=='Save company branding').click().run()
        self.assertFalse(at.exception)
        self.assertEqual(company_profile(at.session_state['demo_store_v2'].read())['name'],'Training company')
        at.button(key='nav_Project settings').click().run()
        next(w for w in at.text_input if w.label=='Project contact person').set_value('Site manager')
        next(w for w in at.button if w.label=='Save project branding').click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state['demo_store_v2'].read()['Projects'][0]['branding']['contact_person'],'Site manager')
        at.button(key='nav_Management report').click().run()
        next(w for w in at.selectbox if w.label=='Report project').select('P01').run()
        next(w for w in at.text_input if w.label=='Project report contact person').set_value('Report recipient').run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state['demo_store_v2'].read()['Projects'][0]['branding']['contact_person'],'Site manager')
        self.assertTrue(any(w.label=='Download printable management report' for w in at.get('download_button')))


if __name__=='__main__':unittest.main()
