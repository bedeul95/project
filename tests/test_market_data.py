import copy,json,sys,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from datetime import datetime,timedelta,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from market_data import Collector,DataError,normalize,completed_date,ttm_snapshots
from server import Handler
from http.server import ThreadingHTTPServer
NOW=datetime(2026,10,6,10,tzinfo=timezone.utc)

def fixture(symbol='005930',mic='XKRX',market='KR'):
 currency='KRW' if market=='KR' else 'USD';price=10000 if market=='KR' else 100
 meta=dict(symbol=symbol,mic_code=mic,currency=currency,period='Quarterly',name='Fixture Corp')
 dates=['2024-09-30','2024-12-31','2025-03-31','2025-06-30','2025-09-30','2025-12-31','2026-03-31','2026-06-30']
 income=[];balances=[];cash=[]
 for i,d in enumerate(dates):
  income.append(dict(fiscal_date=d,sales=100000000+i*1000000,operating_income=20000000+i*100000,net_income=10000000,minority_interests=0,preferred_stock_dividends=0,pretax_income=13000000,income_tax=3000000,basic_shares_outstanding=100000,non_operating_interest=dict(expense=100000)))
  balances.append(dict(fiscal_date=d,assets=dict(current_assets=dict(cash_and_cash_equivalents=10000000)),liabilities=dict(current_liabilities=dict(short_term_debt=2000000),non_current_liabilities=dict(long_term_debt=3000000)),shareholders_equity=dict(total_shareholders_equity=100000000)))
  cash.append(dict(fiscal_date=d,operating_activities=dict(operating_cash_flow=25000000),investing_activities=dict(capital_expenditures=-3000000)))
 values=[];start=datetime(2025,4,1)
 for i in range(554):
  day=start+timedelta(days=i)
  if day.weekday()<5:values.append(dict(datetime=day.date().isoformat(),open=price,high=price*1.01,low=price*.99,close=price,volume=1000000))
 return dict(time_series=dict(meta=meta,values=values),profile=dict(name='Fixture Corp',sector='Technology'),splits=dict(splits=[]),statistics=dict(statistics=dict(stock_statistics=dict(shares_outstanding=100000),financials=dict(most_recent_quarter=dates[-1],income_statement=dict(net_income_to_common_ttm=40000000)))),income_statement=dict(meta=meta,income_statement=income),balance_sheet=dict(meta=meta,balance_sheet=balances),cash_flow=dict(meta=meta,cash_flow=cash))

class MarketTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.calls=[];self.failureMode=None;self.when=NOW
  self.c=Collector(self.tmp.name,transport=self.transport,clock=lambda:self.when)
  self.c.save_config(dict(apiKey='PRIVATE-TEST-KEY',creditsPerMinute=10000))
 def tearDown(self):self.c.close();self.tmp.cleanup()
 def transport(self,endpoint,params):
  self.calls.append((endpoint,params))
  if self.failureMode=='all':raise DataError('test failure')
  if self.failureMode=='one' and params['symbol']=='AAPL':raise DataError('test symbol failure')
  market='KR' if params['mic_code']=='XKRX' else 'US'
  return fixture(params['symbol'],params['mic_code'],market)[endpoint]
 def runjob(self,market='ALL'):
  result=self.c.start(market);self.c.worker.join(10);self.assertFalse(self.c.worker.is_alive());return result
 def test_completed_sessions_dst_and_future_bar_removal(self):
  morning=datetime(2026,10,6,0,tzinfo=timezone.utc)
  self.assertEqual(completed_date('US',morning),'2026-10-05');self.assertEqual(completed_date('KR',morning),'2026-10-05')
  raw=fixture('AAPL','XNAS','US');raw['_financialFetchedAt']='2026-10-05T23:30:00+00:00'
  observed=normalize(dict(symbol='AAPL',mic='XNAS',market='US'),raw,datetime(2026,10,5,23,30,tzinfo=timezone.utc))
  self.assertEqual(observed['snapshots'][-1]['availableAt'],'2026-10-06')
  winter=datetime(2026,12,8,0,tzinfo=timezone.utc);self.assertEqual(completed_date('US',winter),'2026-12-07')
  stock=normalize(dict(symbol='005930',mic='XKRX',market='KR'),fixture(),NOW)
  self.assertEqual(stock['bars'][-1]['date'],'2026-10-06');self.assertFalse(any(b['date']>'2026-10-06' for b in stock['bars']))
 def test_ttm_sums_capex_debt_and_observed_only(self):
  snapshots=ttm_snapshots(fixture(),'KRW','2026-10-06');f=snapshots[-1]
  self.assertEqual(f['revenue'],422000000);self.assertEqual(f['cfo'],100000000);self.assertEqual(f['capex'],12000000)
  self.assertEqual(f['debt'],5000000);self.assertEqual(f['previousRevenue'],406000000)
  self.assertEqual(f['availableAt'],'2026-10-06');self.assertTrue(f['observedOnly'])
 def test_missing_quarter_and_currency_do_not_fake_fundamentals(self):
  raw=fixture();raw['cash_flow']['cash_flow'].pop(-1)
  stock=normalize(dict(symbol='005930',mic='XKRX',market='KR'),raw,NOW)
  self.assertLess(stock['snapshots'][-1]['periodEnd'],'2026-06-30')
  raw=fixture();raw['balance_sheet']['meta']=dict(currency='USD',period='quarterly')
  stock=normalize(dict(symbol='005930',mic='XKRX',market='KR'),raw,NOW)
  self.assertTrue(stock['dataIssues']);self.assertIsNone(stock['snapshots'][0]['revenue'])
 def test_split_trims_history_and_bad_metadata_rejected(self):
  raw=fixture();raw['splits']['splits']=[dict(date='2026-08-03',from_factor=2,to_factor=1)]
  stock=normalize(dict(symbol='005930',mic='XKRX',market='KR'),raw,NOW)
  self.assertGreaterEqual(stock['bars'][0]['date'],'2026-08-03');self.assertIsNone(stock['snapshots'][-1]['dilution'])
  raw['time_series']['meta']['mic_code']='XNAS'
  with self.assertRaises(DataError):normalize(dict(symbol='005930',mic='XKRX',market='KR'),raw,NOW)
 def test_cache_credits_same_engine_and_no_secret_exports(self):
  self.runjob();latest=self.c.latest();self.assertEqual(latest['count'],2);self.assertEqual(latest['analysis']['engineVersion'],'1.3.0')
  for row in latest['analysis']['rows']:
   self.assertAlmostEqual(row['total'],row['fundamental']+row['technical']);self.assertLessEqual(row['fundamental'],70);self.assertLessEqual(row['technical'],30)
  self.assertEqual(self.c.status()['creditsToday'],762);self.assertNotIn('PRIVATE-TEST-KEY',json.dumps(latest))
  self.calls=[];self.runjob();self.assertEqual([c[0] for c in self.calls],['time_series','time_series']);self.assertEqual(self.c.status()['creditsToday'],764)
 def test_failure_preserves_result_and_partial_explicit(self):
  self.runjob();old=self.c.latest();self.failureMode='all';self.runjob();self.assertEqual(self.c.latest(),old)
  self.assertEqual(self.c.status()['jobs'][0]['phase'],'FAILED')
  self.failureMode='one';self.runjob();self.assertEqual(self.c.latest()['count'],1);self.assertEqual(self.c.status()['jobs'][0]['phase'],'PARTIAL')
 def test_budget_and_no_duplicate_scheduler_claim(self):
  self.c.save_config(dict(maxCreditsPerRun=1));self.runjob();self.assertLessEqual(self.c.status()['creditsToday'],1);self.assertEqual(self.c.status()['jobs'][0]['phase'],'FAILED')
  self.c.save_config(dict(maxCreditsPerRun=1500));self.c.tick(NOW);self.c.worker.join(10);count=len(self.calls)
  self.c.tick(NOW);self.assertEqual(len(self.calls),count)
 def test_scheduler_one_run_and_restart_claim(self):
  self.c.save_config(dict(frequency=1));self.c.tick(NOW);self.c.worker.join(10)
  self.assertEqual(self.c.status()['jobs'][0]['market'],'ALL');self.c.close()
  self.c=Collector(self.tmp.name,transport=self.transport,clock=lambda:NOW);count=len(self.calls);self.c.tick(NOW);self.assertEqual(len(self.calls),count)
 def test_read_only_http_and_config_protection(self):
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.session='session-test';server.broker=None;server.collector=self.c
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_port)
  try:
   req=urllib.request.Request(base+'/api/read/status',headers={'X-Atlas-Session':'session-test'})
   with urllib.request.urlopen(req) as r:status=json.load(r)['data'];self.assertTrue(status['readOnly']);self.assertNotIn('apiKey',status['config'])
   for route in ['config','connect','preview','submit']:
    req=urllib.request.Request(base+'/api/'+route,data=b'{}',headers={'X-Atlas-Session':'session-test','Content-Type':'application/json'})
    with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
    self.assertEqual(e.exception.code,403)
   with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(base+'/api/read/status')
  finally:server.shutdown();server.server_close();thread.join()
 def test_config_validation_and_process_lock(self):
  for changes in [dict(morning='25:00'),dict(creditsPerMinute=8),dict(symbols=[dict(market='KR',symbol='005930',mic='XNAS')]),dict(frequency=True)]:
   with self.assertRaises(DataError):self.c.save_config(changes)
  with self.assertRaises(DataError):Collector(self.tmp.name)
if __name__=='__main__':unittest.main()
