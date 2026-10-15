import copy,json,tempfile,unittest,threading,urllib.request,urllib.error
from datetime import datetime,date,timezone
from pathlib import Path
from http.server import ThreadingHTTPServer
from server import Handler
from market_data import Collector,write_json,DataError
from rankings_store import publish,load,csv_export,publish_failure
from universe import validate_master,collection_symbols
from mcp_server import Reader

NOW=datetime(2026,10,2,12,tzinfo=timezone.utc)

def row(status='verified'):
    return dict(market='KR',strategy='value',status=status,title='전체시장 TOP 10',as_of_market_close='2026-10-02',is_full_market_ranking=True,exclude_reasons={},rows=[{'name':'=FORMULA()','symbol':'005930','score':80}])

class RankingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_atomic_failure_preservation_and_stale_history(self):
        publish(self.root,[row()],NOW)
        failed=row('unavailable');failed['rows']=[];failed['exclude_reasons']={'missing':1}
        publish(self.root,[failed],NOW.replace(hour=13))
        r=load(self.root,'KR','value',today=date(2026,10,2));self.assertTrue(r['historical']);self.assertEqual(r['status'],'partial');self.assertEqual(len(r['rows']),1);self.assertEqual(r['latest_attempt_status'],'unavailable')
        r=load(self.root,'KR','value',today=date(2026,10,12));self.assertTrue(r['stale']);self.assertFalse(r['is_full_market_ranking'])
        self.assertEqual(load(self.root,'KR','value','2026-10-01')['status'],'unavailable')
        self.assertEqual(len(list((self.root/'ranking-history').glob('*.json'))),2)
    def test_csv_formula_defense_and_mcp_saved_only(self):
        publish(self.root,[row()],NOW)
        text=csv_export(load(self.root,'KR','value',today=NOW.date())).decode('utf-8-sig');self.assertIn("'=FORMULA()",text)
        write_json(self.root/'data-config.json',{'apiKey':'SECRET-NEVER-EXPORT'})
        reader=Reader(self.root,today=lambda:NOW.date());r=reader.call('atlas_top10',{'market':'KR','strategy':'value'})
        self.assertEqual(r['rows'][0]['symbol'],'005930');self.assertNotIn('SECRET',json.dumps(r));self.assertFalse(r['live_quote'])
    def test_master_dates_types_symbols_and_exclusion(self):
        master={'schemaVersion':1,'markets':{'KR':{'complete':True,'asOf':'2026-10-02','expectedMarketDate':'2026-10-02','source':'Exchange fixture','calendarSource':'Calendar fixture','entries':[{'id':'KR-005930-XKRX','symbol':'005930','mic':'XKRX','status':'active','statusAsOf':'2026-10-02','securityType':'Common Stock','source':'Status fixture'}]}}}
        validate_master(master,'2026-10-02');self.assertEqual(collection_symbols(master,'KR')[0]['symbol'],'005930')
        for key,value in [('status','guessed'),('statusAsOf','2026-10-03'),('id','oops')]:
            d=copy.deepcopy(master);d['markets']['KR']['entries'][0][key]=value
            with self.assertRaises(ValueError):validate_master(d,'2026-10-02')
        d=copy.deepcopy(master);d['markets']['KR']['entries'][0]['status']='managed';self.assertEqual(collection_symbols(d,'KR'),[])
    def test_authenticated_api_and_invalid_queries(self):
        c=Collector(self.root/'research');publish(c.directory,[row()],NOW)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.session='test-session';server.collector=c;server.broker=None
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_port)
        try:
            for fmt in ['', '&format=csv']:
                req=urllib.request.Request(base+'/api/research/rankings?market=KR&strategy=value'+fmt,headers={'X-Atlas-Session':'test-session'})
                with urllib.request.urlopen(req) as response:
                    body=response.read();self.assertEqual(response.status,200);self.assertNotIn(b'apiKey',body)
            for suffix,session,code in [('?market=JP&strategy=value','test-session',400),('?market=KR&strategy=value','',403)]:
                req=urllib.request.Request(base+'/api/research/rankings'+suffix,headers={'X-Atlas-Session':session})
                with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
                self.assertEqual(e.exception.code,code)
        finally:server.shutdown();server.server_close();thread.join();c.close()
    def test_total_failure_marks_saved_success_historical(self):
        publish(self.root,[row()],NOW)
        publish_failure(self.root,{'KR'},NOW.replace(hour=14),'Budget exhausted')
        result=load(self.root,'KR','value',today=NOW.date())
        self.assertTrue(result['historical']);self.assertEqual(result['latest_attempt_note'],'Budget exhausted')
        self.assertEqual(load(self.root,'KR','alpha_filters',today=NOW.date())['status'],'unavailable')
    def test_history_retention(self):
        for i in range(35):publish(self.root,[row()],NOW.replace(microsecond=i))
        self.assertEqual(len(list((self.root/'ranking-history').glob('*.json'))),30)

if __name__=='__main__':unittest.main()
