import unittest
from copy import deepcopy
from unittest.mock import Mock
from domain import initial_tables, validate_record, evaluate, record_id, today, SCHEMAS
from storage import MemoryStore, GoogleSheetsStore, ConflictError

class DomainTests(unittest.TestCase):
    def setUp(self):
        from enterprise import seed
        self.tables={**initial_tables(),**seed()}; self.defs=self.tables['Definitions']
        self.names={d['name']:d for d in self.defs}; self.map={d['id']:d for d in self.defs}
    def row(self,name,n,z=None,day=None,site='SITE-001'):
        return validate_record(dict(date=str(day or today()),site=site,shift='Day',kpi_id=self.names[name]['id'],numerator=n,denominator=z,na=0,notes='',actor='Tester'),self.map,{'SITE-001','SITE-002'})
    def test_weighted_percentage(self):
        d=self.names['PPE compliance']
        rows=[self.row(d['name'],1,1),self.row(d['name'],1,9,site='SITE-002')]
        self.assertEqual(evaluate(d,rows)[0],20)
    def test_missing_zero_and_na_distinct(self):
        d=self.names['PPE compliance']
        self.assertEqual(evaluate(d,[])[1],'No data')
        self.assertEqual(evaluate(d,[self.row(d['name'],0,0)])[1],'N/A')
        self.assertEqual(evaluate(d,[self.row(d['name'],0,10)])[0],0)
    def test_invalid_inputs(self):
        for n,z in [(11,10),(-1,10),(1,0),(float('nan'),10),(1,None)]:
            with self.subTest(n=n,z=z),self.assertRaises(ValueError): self.row('PPE compliance',n,z)
    def test_rate_requires_matching_coverage(self):
        rows=[self.row('Total recordable injury and illness cases',1),self.row('Hours worked',1000)]
        self.assertEqual(evaluate(self.names['TRIR / TCIR'],rows,self.defs)[0],200)
        rows.append(self.row('Hours worked',1000,site='SITE-002'))
        self.assertEqual(evaluate(self.names['TRIR / TCIR'],rows,self.defs)[1],'Incomplete inputs')
    def test_snapshot_uses_latest_site_value(self):
        from datetime import timedelta
        rows=[self.row('Workforce on site',50,day=today()-timedelta(days=1)),self.row('Workforce on site',60),self.row('Workforce on site',30,site='SITE-002')]
        self.assertEqual(evaluate(self.names['Workforce on site'],rows)[0],90)
    def test_upsert_and_conflict(self):
        store=MemoryStore(self.tables); r=self.row('Hours worked',500)
        store.save('Records',[r]); old=store.read()['Records'][0]
        store.save('Records',[{**r,'numerator':600}],{r['id']:old['revision']})
        self.assertEqual(len(store.read()['Records']),1)
        with self.assertRaises(ConflictError): store.save('Records',[r],{r['id']:old['revision']})
    def test_google_raw_append_and_revision_read(self):
        store=GoogleSheetsStore.__new__(GoogleSheetsStore); store.book=Mock()
        original=self.row('Hours worked',500); original.update(revision='one',updated_at='now')
        revised={**original,'numerator':600,'revision':'two'}
        grids=[]
        for name,cols in SCHEMAS.items():
            rows=[original,revised] if name=='Records' else self.tables[name]
            grids.append({'values':[cols]+[['' if r.get(k) is None else r.get(k,'') for k in cols] for r in rows]})
        store.book.values_batch_get.return_value={'valueRanges':grids}
        self.assertEqual(store.read()['Records'][0]['numerator'],600)
        store.save('Records',[{**revised,'notes':'=1+1'}],{original['id']:'two'})
        args,kwargs=store.book.values_append.call_args
        self.assertEqual(kwargs['params']['valueInputOption'],'RAW')
        self.assertIn('=1+1',kwargs['body']['values'][0])
    def test_unique_catalogue(self):
        self.assertEqual(len(self.defs),288)
        self.assertEqual(len({d['id'] for d in self.defs}),288)
        self.assertEqual(len({d['name'] for d in self.defs}),288)

class UITests(unittest.TestCase):
    def test_pages_and_action_save(self):
        from streamlit.testing.v1 import AppTest
        at=AppTest.from_file('app.py',default_timeout=60); at.secrets['application']={'enabled':False}; at.run()
        self.assertFalse(at.exception)
        next(x for x in at.selectbox if x.label=='Application area').set_value('Advanced KPI workspace').run()
        for page in ['Daily entry','KPI register','Corrective actions','Reports & export','Data & export']:
            at.sidebar.radio[0].set_value(page).run()
            self.assertFalse(at.exception,page)
        at.sidebar.radio[0].set_value('Corrective actions').run()
        next(x for x in at.text_input if x.label=='Action').set_value('Test guard repair')
        next(x for x in at.text_input if x.label=='Responsible person').set_value('Test supervisor')
        next(x for x in at.button if x.label=='Save action').click().run()
        self.assertFalse(at.exception)
        self.assertTrue(any(r['title']=='Test guard repair' for r in at.session_state['demo_store_v2'].read()['Actions']))
        at.sidebar.radio[0].set_value('Daily entry').run()
        next(x for x in at.text_input if x.label=='Reporting person').set_value('Tester')
        next(x for x in at.button if x.label=='Save shift report').click().run()
        self.assertFalse(at.exception)
        self.assertTrue(at.success)

if __name__=='__main__': unittest.main()
