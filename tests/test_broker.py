import json, sys, tempfile, unittest, threading, urllib.request, urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from broker import Broker, BrokerError
from server import Handler
from http.server import ThreadingHTTPServer

class BrokerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.calls=[];self.failure=None
  self.b=Broker(self.tmp.name,self.transport)
  self.b.save_config(dict(appkey='TEST-KEY',appsecret='TEST-SECRET',account='12345678',cashAccountConfirmed=True))
 def tearDown(self):self.b.db.close();self.tmp.cleanup()
 def transport(self,method,path,headers,body=None,params=None):
  self.calls.append((method,path,headers,body,params))
  if path=='/oauth2/tokenP':return dict(access_token='TEST-TOKEN',expires_in=86400)
  if '/domestic-stock/v1/quotations/' in path:return dict(rt_cd='0',output=dict(stck_prpr='10000',acml_vol='900'))
  if 'overseas-price' in path:return dict(rt_cd='0',output=dict(last='100',tvol='800'))
  if method=='POST':
   if self.failure=='network':raise BrokerError('timeout')
   if self.failure=='reject':return dict(rt_cd='1',msg_cd='REJECT')
   return dict(rt_cd='0',output=dict(ODNO='12345'))
  return dict(rt_cd='0',output1=[dict(odno='12345',account='DO-NOT-RETURN')],output=[],_continuation='M')
 def order(self,market='KR',side='BUY'):
  return dict(market=market,symbol='005930' if market=='KR' else 'AAPL',exchange='KRX' if market=='KR' else 'NASD',side=side,quantity=1,price='10000' if market=='KR' else '100')
 def test_keys_masked_permissions_token_cache(self):
  self.b.authenticate();self.b.authenticate();self.assertEqual(sum(x[1]=='/oauth2/tokenP' for x in self.calls),1)
  s=json.dumps(self.b.status());self.assertNotIn('TEST-KEY',s);self.assertNotIn('TEST-SECRET',s);self.assertNotIn('12345678',s)
  self.assertEqual(self.b.configPath.stat().st_mode & 0o777,0o600)
 def test_domestic_and_us_quote_routing(self):
  self.assertEqual(self.b.quote('KR','005930','KRX')['price'],10000)
  self.assertEqual(self.calls[-1][2]['tr_id'],'FHKST01010100')
  self.b.quote('US','AAPL','NASD');self.assertEqual(self.calls[-1][4]['EXCD'],'NAS')
 def test_order_ids_and_single_submission(self):
  for market,side,tr in [('KR','BUY','VTTC0012U'),('KR','SELL','VTTC0011U'),('US','BUY','VTTT1002U'),('US','SELL','VTTT1001U')]:
   ticket=self.b.preview(self.order(market,side))['ticket'];self.assertEqual(self.b.submit(ticket)['phase'],'ACKNOWLEDGED')
   self.assertEqual(self.calls[-1][2]['tr_id'],tr);count=len(self.calls)
   self.assertTrue(self.b.submit(ticket)['duplicate']);self.assertEqual(len(self.calls),count)
 def test_live_requires_explicit_permission(self):
  self.b.save_config(dict(mode='live',appkey='LIVE-KEY',appsecret='LIVE-SECRET'))
  with self.assertRaises(BrokerError):self.b.preview(self.order())
  self.b.save_config(dict(allowLive=True));ticket=self.b.preview(self.order())['ticket'];self.b.submit(ticket)
  self.assertEqual(self.calls[-1][2]['tr_id'],'TTTC0012U')
 def test_unknown_never_retries_and_blocks_new_order_after_restart(self):
  ticket=self.b.preview(self.order())['ticket'];self.failure='network';self.assertEqual(self.b.submit(ticket)['phase'],'UNKNOWN')
  self.b.db.close();self.b=Broker(self.tmp.name,self.transport);count=len(self.calls)
  self.assertTrue(self.b.submit(ticket)['duplicate']);self.assertEqual(len(self.calls),count)
  new=self.b.preview(self.order())['ticket']
  with self.assertRaises(BrokerError):self.b.submit(new)
 def test_rejection_expiry_and_daily_limit(self):
  self.failure='reject';ticket=self.b.preview(self.order())['ticket'];self.assertEqual(self.b.submit(ticket)['phase'],'REJECTED')
  self.failure=None;ticket=self.b.preview(self.order())['ticket'];self.b.db.execute('UPDATE orders SET created=0 WHERE id=?',(ticket,));self.b.db.commit()
  with self.assertRaises(BrokerError):self.b.submit(ticket)
  self.b.save_config(dict(dailyKR=10000));ticket=self.b.preview(self.order())['ticket'];self.b.submit(ticket)
  ticket=self.b.preview(self.order())['ticket']
  with self.assertRaises(BrokerError):self.b.submit(ticket)
 def test_invalid_inputs_and_price_guard(self):
  for changes in [dict(quantity=True),dict(price='NaN'),dict(quantity=0),dict(exchange='NASD'),dict(price='1000000')]:
   with self.assertRaises(BrokerError):self.b.preview({**self.order(),**changes})
  with self.assertRaises(BrokerError):self.b.quote('US','../../secret','NASD')
 def test_order_query_redacts_extra_fields(self):
  r=self.b.broker_orders('KR','KRX','20261001','20261006');self.assertTrue(r['more']);self.assertNotIn('account',r['rows'][0])
 def test_loopback_host_session_origin_guards(self):
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.session='test-session';server.broker=self.b
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_port)
  try:
   for headers in [{},{'X-Atlas-Session':'wrong'},{'X-Atlas-Session':'test-session','Origin':'https://evil.example'},{'X-Atlas-Session':'test-session','Host':'evil.example'}]:
    with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(urllib.request.Request(base+'/api/status',headers=headers))
    self.assertEqual(e.exception.code,403)
   with urllib.request.urlopen(urllib.request.Request(base+'/api/status',headers={'X-Atlas-Session':'test-session'})) as r:self.assertTrue(json.load(r)['ok'])
   with urllib.request.urlopen(base) as r:self.assertIn(b'window.ATLAS_SESSION="test-session"',r.read())
  finally:server.shutdown();server.server_close();thread.join()
if __name__=='__main__':unittest.main()
