"""KIS REST adapter. Credentials remain on the Mac. No automatic strategy orders."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation

class BrokerError(Exception):
    pass

class Rejected(BrokerError):
    pass

DEFAULTS = dict(mode='demo', appkey='', appsecret='', account='', product='01', allowLive=False,
                cashAccountConfirmed=False, maxKR=1000000, maxUS=1000, dailyKR=5000000, dailyUS=5000)
DOMAINS = {'demo':'https://openapivts.koreainvestment.com:29443',
           'live':'https://openapi.koreainvestment.com:9443'}
EXCHANGES = {'NASD':'NAS','NYSE':'NYS','AMEX':'AMS'}

def number(value):
    try:
        n = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise BrokerError('숫자 형식이 잘못됐습니다.')
    if not n.is_finite():
        raise BrokerError('유한한 숫자가 필요합니다.')
    return n

class Broker:
    def __init__(self, directory, transport=None):
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
        os.chmod(self.directory,0o700)
        self.configPath=self.directory/'kis-config.json'
        self.config={**DEFAULTS}
        if self.configPath.exists():
            try:self.config=self.validate_config(json.loads(self.configPath.read_text()))
            except Exception:raise BrokerError('KIS 설정 파일이 손상됐습니다. 파일을 확인하세요.')
        self.lock=threading.RLock();self.token='';self.expires=0;self.last_call=0
        self.transport=transport or self.network
        self.db=sqlite3.connect(str(self.directory/'orders.sqlite'),check_same_thread=False)
        os.chmod(self.directory/'orders.sqlite',0o600)
        self.db.execute('CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, created REAL, identity TEXT, body TEXT, phase TEXT, result TEXT)')
        # An interrupted submit can never be assumed unsent.
        self.db.execute("UPDATE orders SET phase='UNKNOWN', result=? WHERE phase='SENDING'",(json.dumps({'error':'서버 중단 · 증권사 확인 필요'}),));self.db.commit()

    def validate_config(self, data):
        if not isinstance(data,dict):raise BrokerError('설정 형식을 확인하세요.')
        c={**DEFAULTS,**{k:data[k] for k in DEFAULTS if k in data}}
        if c['mode'] not in DOMAINS:raise BrokerError('모의/실전 환경을 확인하세요.')
        for k in ['appkey','appsecret']:
            if not isinstance(c[k],str) or len(c[k])>500 or any(ord(x)<32 for x in c[k]):raise BrokerError('키 형식을 확인하세요.')
        if c['account'] and not re.fullmatch(r'\d{8}',str(c['account'])):raise BrokerError('계좌 앞 8자리를 입력하세요.')
        if not re.fullmatch(r'\d{2}',str(c['product'])):raise BrokerError('계좌상품코드 2자리를 입력하세요.')
        for k in ['allowLive','cashAccountConfirmed']:
            if type(c[k]) is not bool:raise BrokerError('주문 허용 설정을 확인하세요.')
        for k in ['maxKR','maxUS','dailyKR','dailyUS']:
            v=number(c[k])
            if v<=0 or v>Decimal('10000000000'):raise BrokerError('주문 한도 범위를 확인하세요.')
            c[k]=float(v)
        return c

    def identity(self):
        c=self.config
        return hashlib.sha256((c['mode']+'|'+c['account']+'|'+c['product']+'|'+c['appkey']).encode()).hexdigest()

    def status(self):
        c=self.config
        return dict(provider='KIS',mode=c['mode'],configured=bool(c['appkey'] and c['appsecret'] and c['account']),
                    authenticated=bool(self.token and self.expires>time.time()),accountMasked=('****'+c['account'][-4:]) if c['account'] else '',
                    allowLive=c['allowLive'],cashAccountConfirmed=c['cashAccountConfirmed'],
                    maxKR=c['maxKR'],maxUS=c['maxUS'],dailyKR=c['dailyKR'],dailyUS=c['dailyUS'])

    def save_config(self, data):
        with self.lock:
            # Blank keys keep existing credentials only when the environment/account is unchanged.
            changed=data.get('mode',self.config['mode'])!=self.config['mode'] or data.get('account',self.config['account'])!=self.config['account']
            c={**self.config,**data}
            for key in ['appkey','appsecret']:
                if not data.get(key):c[key]='' if changed else self.config[key]
            c=self.validate_config(c)
            fd=os.open(self.configPath.with_suffix('.tmp'),os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,'w') as stream:json.dump(c,stream)
            os.replace(self.configPath.with_suffix('.tmp'),self.configPath);os.chmod(self.configPath,0o600)
            self.config=c;self.token='';self.expires=0
            self.db.execute("DELETE FROM orders WHERE phase='PREPARED'");self.db.commit()
            return self.status()

    def network(self, method, path, headers, body=None, params=None):
        # No caller-supplied destination and no automatic POST retries or redirects.
        url=DOMAINS[self.config['mode']]+path
        if params:url+='?'+urllib.parse.urlencode(params)
        payload=json.dumps(body,separators=(',',':')).encode() if body is not None else None
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):return None
        request=urllib.request.Request(url,data=payload,headers=headers,method=method)
        try:
            with urllib.request.build_opener(NoRedirect()).open(request,timeout=15) as response:
                raw=response.read(2*1024*1024)
                data=json.loads(raw)
                data['_continuation']=response.headers.get('tr_cont','')
                return data
        except urllib.error.HTTPError as error:
            raise BrokerError('증권사 HTTP 오류 '+str(error.code)+' · 재전송하지 마세요.') from None
        except Exception:
            raise BrokerError('증권사 응답을 확인하지 못했습니다. 주문이었다면 접수 여부를 증권사에서 확인하세요.') from None

    def authenticate(self):
        with self.lock:
            if self.token and time.time()<self.expires:return self.status()
            c=self.config
            if not c['appkey'] or not c['appsecret']:raise BrokerError('맥의 API 연결 화면에 App Key와 App Secret을 입력하세요.')
            result=self.transport('POST','/oauth2/tokenP',{'Content-Type':'application/json'},
                                  {'grant_type':'client_credentials','appkey':c['appkey'],'appsecret':c['appsecret']})
            token=result.get('access_token');duration=result.get('expires_in')
            if not isinstance(token,str) or not token or not isinstance(duration,(int,float)) or duration<=60:raise BrokerError('토큰 발급 응답을 확인하세요.')
            self.token=token;self.expires=time.time()+min(duration,86400)-60
            return self.status()

    def request(self, method, path, tr_id, body=None, params=None):
        self.authenticate()
        wait=.6-(time.monotonic()-self.last_call)
        if wait>0 and self.transport==self.network:time.sleep(wait)
        self.last_call=time.monotonic()
        headers={'Content-Type':'application/json','authorization':'Bearer '+self.token,
                 'appkey':self.config['appkey'],'appsecret':self.config['appsecret'],'tr_id':tr_id,'custtype':'P'}
        result=self.transport(method,path,headers,body,params)
        if not isinstance(result,dict) or 'rt_cd' not in result:raise BrokerError('예상한 증권사 응답 형식이 아닙니다.')
        if str(result['rt_cd'])!='0':
            code=re.sub(r'[^A-Za-z0-9_-]','',str(result.get('msg_cd','UNKNOWN')))[:40]
            raise Rejected('증권사 요청 거절 · 코드 '+code)
        return result

    def validate_symbol(self,market,symbol,exchange):
        if market=='KR':
            if not isinstance(symbol,str) or not re.fullmatch(r'[0-9A-Z]{6}',symbol):raise BrokerError('국내 주식 코드 6자리를 입력하세요.')
            if exchange!='KRX':raise BrokerError('국내 주문은 KRX만 지원합니다.')
        elif market=='US':
            if not isinstance(symbol,str) or not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,11}',symbol):raise BrokerError('미국 주식 티커를 입력하세요.')
            if exchange not in EXCHANGES:raise BrokerError('미국 거래소 NASD/NYSE/AMEX를 선택하세요.')
        else:raise BrokerError('KR 또는 US 시장을 선택하세요.')

    def quote(self,market,symbol,exchange):
        with self.lock:
            self.validate_symbol(market,symbol,exchange)
            if market=='KR':
                r=self.request('GET','/uapi/domestic-stock/v1/quotations/inquire-price','FHKST01010100',params={'FID_COND_MRKT_DIV_CODE':'J','FID_INPUT_ISCD':symbol})
                o=r.get('output',{});price=o.get('stck_prpr');volume=o.get('acml_vol')
            else:
                r=self.request('GET','/uapi/overseas-price/v1/quotations/price','HHDFS00000300',params={'AUTH':'','EXCD':EXCHANGES[exchange],'SYMB':symbol})
                o=r.get('output',{});price=o.get('last');volume=o.get('tvol')
            value=number(price)
            if value<=0:raise BrokerError('유효한 현재가가 없습니다.')
            return dict(market=market,symbol=symbol,exchange=exchange,price=float(value),volume=str(volume or ''),
                        currency='KRW' if market=='KR' else 'USD',fetchedAt=datetime.now(timezone.utc).isoformat(),
                        mode=self.config['mode'],type='REST snapshot',delay='조회 시점 스냅샷 · 미국 시세 지연/권한은 계약에 따라 다름')

    def validate_order(self, data):
        if not isinstance(data,dict):raise BrokerError('주문 형식을 확인하세요.')
        market=data.get('market');symbol=data.get('symbol');exchange=data.get('exchange');self.validate_symbol(market,symbol,exchange)
        side=data.get('side');qty=data.get('quantity');price=number(data.get('price'))
        if side not in ['BUY','SELL'] or type(qty) is not int or not 1<=qty<=100000:raise BrokerError('매수/매도와 정수 수량 1~100,000을 확인하세요.')
        if price<=0 or price>Decimal('100000000') or (market=='KR' and price!=price.to_integral_value()) or (market=='US' and price.as_tuple().exponent<-2):raise BrokerError('지정가를 확인하세요. 국내는 정수 원, 미국은 소수점 2자리까지입니다.')
        amount=price*qty
        if amount>number(self.config['max'+market]):raise BrokerError('1회 주문 금액 한도를 초과했습니다.')
        if not self.config['account']:raise BrokerError('계좌 설정이 필요합니다.')
        if not self.config['cashAccountConfirmed']:raise BrokerError('현금 범위 거래 계좌 설정을 확인한 뒤 주문을 허용하세요.')
        if self.config['mode']=='live' and not self.config['allowLive']:raise BrokerError('실전 주문이 잠겨 있습니다. API 설정에서 명시적으로 활성화해야 합니다.')
        return dict(market=market,symbol=symbol,exchange=exchange,side=side,quantity=qty,price=str(price),amount=str(amount),currency='KRW' if market=='KR' else 'USD')

    def preview(self,data):
        with self.lock:
            order=self.validate_order(data)
            quote=self.quote(order['market'],order['symbol'],order['exchange'])
            if abs(float(order['price'])/quote['price']-1)>.05:raise BrokerError('지정가가 조회 현재가에서 5% 이상 벗어났습니다.')
            ticket=secrets.token_urlsafe(24);created=time.time()
            self.db.execute('INSERT INTO orders VALUES(?,?,?,?,?,?)',(ticket,created,self.identity(),json.dumps(order),'PREPARED','{}'));self.db.commit()
            return dict(ticket=ticket,expiresAt=created+120,order=order,quote=quote,mode=self.config['mode'])

    def submit(self,ticket):
        with self.lock:
            row=self.db.execute('SELECT created,identity,body,phase,result FROM orders WHERE id=?',(ticket,)).fetchone()
            if not row:raise BrokerError('주문 검토표가 없습니다.')
            created,identity,raw,phase,result=row
            if identity!=self.identity():raise BrokerError('계좌·환경이 바뀌었습니다. 다시 검토하세요.')
            if phase!='PREPARED':return dict(ticket=ticket,phase=phase,result=json.loads(result),duplicate=True)
            if time.time()-created>120:raise BrokerError('검토표가 만료됐습니다. 새 현재가로 다시 검토하세요.')
            order=self.validate_order(json.loads(raw));self.authenticate()
            if self.db.execute("SELECT 1 FROM orders WHERE identity=? AND phase IN ('UNKNOWN','SENDING') LIMIT 1",(identity,)).fetchone():raise BrokerError('미확인 주문이 있습니다. 증권사 접수 여부 확인 전 새 주문을 막았습니다.')
            used=Decimal('0');start=time.time()-86400
            for (body,) in self.db.execute("SELECT body FROM orders WHERE identity=? AND created>=? AND phase IN ('ACKNOWLEDGED','UNKNOWN','SENDING')",(identity,start)):
                old=json.loads(body)
                if old['market']==order['market']:used+=number(old['amount'])
            if used+number(order['amount'])>number(self.config['daily'+order['market']]):raise BrokerError('최근 24시간 주문 한도를 초과했습니다.')
            # Re-query the price before reserving the durable submission record.
            current=self.quote(order['market'],order['symbol'],order['exchange'])
            if abs(float(order['price'])/current['price']-1)>.05:raise BrokerError('현재가가 변했습니다. 주문을 다시 검토하세요.')
            self.db.execute("UPDATE orders SET phase='SENDING' WHERE id=?",(ticket,));self.db.commit()
            c=self.config;body={'CANO':c['account'],'ACNT_PRDT_CD':c['product'],'PDNO':order['symbol'],'ORD_QTY':str(order['quantity']),'ORD_DVSN':'00'}
            if order['market']=='KR':
                body.update(ORD_UNPR=order['price'],EXCG_ID_DVSN_CD='KRX',SLL_TYPE='01' if order['side']=='SELL' else '',CNDT_PRIC='')
                tr=('TTTC' if c['mode']=='live' else 'VTTC')+('0012U' if order['side']=='BUY' else '0011U');path='/uapi/domestic-stock/v1/trading/order-cash'
            else:
                body.update(OVRS_EXCG_CD=order['exchange'],OVRS_ORD_UNPR=order['price'],CTAC_TLNO='',MGCO_APTM_ODNO='',SLL_TYPE='00' if order['side']=='SELL' else '',ORD_SVR_DVSN_CD='0')
                tr=('TTTT1002U' if order['side']=='BUY' else 'TTTT1006U') if c['mode']=='live' else ('VTTT1002U' if order['side']=='BUY' else 'VTTT1001U');path='/uapi/overseas-stock/v1/trading/order'
            try:
                response=self.request('POST',path,tr,body=body);out=response.get('output',{})
                if isinstance(out,list):out=out[0] if out else {}
                broker_id=str(out.get('ODNO',out.get('odno','')))
                if not broker_id:raise BrokerError('주문번호를 받지 못했습니다. 증권사에서 접수 여부를 확인하세요.')
                phase='ACKNOWLEDGED';result=dict(brokerOrderId=broker_id,note='접수 응답 · 체결 완료 아님')
            except Rejected as error:phase='REJECTED';result=dict(error=str(error))
            except Exception:phase='UNKNOWN';result=dict(error='응답 미확인 · 자동 재전송 없음 · 증권사 앱에서 확인 필요')
            self.db.execute('UPDATE orders SET phase=?,result=? WHERE id=?',(phase,json.dumps(result),ticket));self.db.commit()
            return dict(ticket=ticket,phase=phase,result=result,duplicate=False)

    def history(self):
        with self.lock:
            return [dict(ticket=i,created=t,order=json.loads(b),phase=p,result=json.loads(r)) for i,t,b,p,r in self.db.execute('SELECT id,created,body,phase,result FROM orders WHERE identity=? ORDER BY created DESC LIMIT 50',(self.identity(),))]

    def broker_orders(self,market,exchange,start,end):
        with self.lock:
            for date in [start,end]:
                if not isinstance(date,str) or not re.fullmatch(r'\d{8}',date):raise BrokerError('조회일은 YYYYMMDD입니다.')
                try:datetime.strptime(date,'%Y%m%d')
                except ValueError:raise BrokerError('올바른 조회일을 입력하세요.')
            if start>end:raise BrokerError('조회 기간을 확인하세요.')
            if (datetime.strptime(end,'%Y%m%d')-datetime.strptime(start,'%Y%m%d')).days>31:raise BrokerError('최대 31일을 조회하세요.')
            c=self.config;params={'CANO':c['account'],'ACNT_PRDT_CD':c['product']}
            if market=='KR':
                params.update(INQR_STRT_DT=start,INQR_END_DT=end,SLL_BUY_DVSN_CD='00',PDNO='',CCLD_DVSN='00',INQR_DVSN='00',INQR_DVSN_3='00',ORD_GNO_BRNO='',ODNO='',INQR_DVSN_1='',CTX_AREA_FK100='',CTX_AREA_NK100='',EXCG_ID_DVSN_CD='KRX')
                r=self.request('GET','/uapi/domestic-stock/v1/trading/inquire-daily-ccld','TTTC0081R' if c['mode']=='live' else 'VTTC0081R',params=params);rows=r.get('output1',[])
            elif market=='US' and exchange in EXCHANGES:
                params.update(PDNO='',ORD_STRT_DT=start,ORD_END_DT=end,SLL_BUY_DVSN='00',CCLD_NCCS_DVSN='00',OVRS_EXCG_CD=exchange,SORT_SQN='DS',ORD_DT='',ORD_GNO_BRNO='',ODNO='',CTX_AREA_NK200='',CTX_AREA_FK200='')
                r=self.request('GET','/uapi/overseas-stock/v1/trading/inquire-ccnl','TTTS3035R' if c['mode']=='live' else 'VTTS3035R',params=params);rows=r.get('output',[])
            else:raise BrokerError('조회 시장·거래소를 확인하세요.')
            if not isinstance(rows,list):raise BrokerError('주문 조회 응답 형식을 확인하세요.')
            allowed=['odno','ord_dt','pdno','prdt_name','sll_buy_dvsn_cd','sll_buy_dvsn','ord_qty','tot_ccld_qty','ft_ccld_qty','nccs_qty','rmn_qty','ord_unpr','ft_ord_unpr','avg_prvs','cncl_yn','rjct_qty']
            return dict(rows=[{k:row[k] for k in allowed if k in row} for row in rows[:100]],more=r.get('_continuation') in ['M','F'],note='첫 페이지 · 필드명은 증권사 응답 기준. 취소·정정은 증권사 앱에서 수행하세요.')
