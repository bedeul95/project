"""Account-free Twelve Data collection. Fixed GET endpoints; no broker/order routes."""
import copy, fcntl, json, math, os, re, secrets, shutil, subprocess, threading, time
import urllib.request, urllib.parse, urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from universe import validate_master, collection_symbols

ROOT=Path(__file__).resolve().parent
KST=ZoneInfo('Asia/Seoul');NY=ZoneInfo('America/New_York')
COSTS={'time_series':1,'profile':10,'statistics':50,'income_statement':100,'balance_sheet':100,'cash_flow':100,'splits':20}
DEFAULTS=dict(apiKey='',universeMode='watchlist',scheduled=True,morning='08:30',evening='18:30',frequency=2,
              creditsPerMinute=500,maxCreditsPerRun=1500,maxCreditsPerDay=3000,financialCacheHours=24,
              symbols=[dict(symbol='005930',mic='XKRX',market='KR'),dict(symbol='AAPL',mic='XNAS',market='US')])
FIELDS=['revenue','operatingIncome','netIncome','equity','cfo','capex','shares','debt','cash','interest','investedCapital','taxRate','previousRevenue','previousOperatingIncome','previousMargin','dilution']
class DataError(Exception):pass
class BudgetError(DataError):pass
class AccessError(DataError):pass

def valid_date(s):
 try:return isinstance(s,str) and datetime.strptime(s,'%Y-%m-%d').strftime('%Y-%m-%d')==s
 except ValueError:return False

def numeric(value):
 if value is None or isinstance(value,bool):return None
 try:n=float(value)
 except (TypeError,ValueError):return None
 return n if math.isfinite(n) else None

def at(obj,path):
 for key in path.split('.'):
  if not isinstance(obj,dict):return None
  obj=obj.get(key)
 return numeric(obj)

def total(items,path,positive=False):
 vals=[at(x,path) for x in items]
 return sum(abs(x) if positive else x for x in vals) if items and all(x is not None for x in vals) else None

def write_json(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 temp=path.with_name(path.name+'.'+secrets.token_hex(6)+'.tmp')
 try:
  fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'w') as f:json.dump(value,f,ensure_ascii=False,allow_nan=False);f.flush();os.fsync(f.fileno())
  os.replace(temp,path)
 finally:
  if temp.exists():temp.unlink()

def blank_snapshot(today):
 return dict(periodEnd=today,filedAt=today,availableAt=today,version='unavailable-'+today,observedOnly=True,**{k:None for k in FIELDS})

def indexed(response,key,currency):
 meta=response.get('meta',{})
 if meta.get('currency')!=currency or str(meta.get('period','')).lower()!='quarterly':raise DataError('재무 통화 또는 분기 기준이 일치하지 않습니다.')
 rows=response.get(key)
 if not isinstance(rows,list):raise DataError('재무 응답 배열이 없습니다.')
 result={}
 for row in rows:
  if not isinstance(row,dict) or not valid_date(row.get('fiscal_date')):raise DataError('재무 결산일 형식 오류')
  date=row['fiscal_date']
  if date in result:raise DataError('중복 재무 결산일')
  result[date]=row
 return result

def ttm_snapshots(raw,currency,today):
 inc=indexed(raw['income_statement'],'income_statement',currency)
 bal=indexed(raw['balance_sheet'],'balance_sheet',currency)
 cf=indexed(raw['cash_flow'],'cash_flow',currency)
 dates=sorted(d for d in inc if d<=today)
 statistics=raw['statistics'].get('statistics',{})
 shares=at(statistics,'stock_statistics.shares_outstanding')
 out=[]
 for end in range(3,len(dates)):
  current=dates[end-3:end+1];period=current[-1]
  # Four distinct consecutive quarters, never four arbitrary reporting periods.
  gaps=[(datetime.fromisoformat(b)-datetime.fromisoformat(a)).days for a,b in zip(current,current[1:])]
  if any(not 65<=g<=115 for g in gaps) or any(d not in bal or d not in cf for d in current):continue
  ii=[inc[d] for d in current];cc=[cf[d] for d in current];b=bal[period]
  revenue=total(ii,'sales');op=total(ii,'operating_income');net=total(ii,'net_income')
  minor=total(ii,'minority_interests');preferred=total(ii,'preferred_stock_dividends')
  # Do not guess zero for an absent minority/preferred adjustment.
  if net is not None and minor is not None and preferred is not None:net-=minor+preferred
  else:net=None
  equity=at(b,'shareholders_equity.total_shareholders_equity')
  cash=at(b,'assets.current_assets.cash_and_cash_equivalents')
  short=at(b,'liabilities.current_liabilities.short_term_debt');long=at(b,'liabilities.non_current_liabilities.long_term_debt')
  debt=short+long if short is not None and long is not None else None
  tax=total(ii,'income_tax');pretax=total(ii,'pretax_income')
  taxrate=tax/pretax if tax is not None and pretax is not None and pretax>0 and 0<=tax/pretax<=1 else None
  previous=dates[end-7:end-3] if end>=7 else []
  if previous:
   all8=previous+current
   if any(not 65<=(datetime.fromisoformat(bd)-datetime.fromisoformat(ad)).days<=115 for ad,bd in zip(all8,all8[1:])):previous=[]
  prev=[inc[d] for d in previous];prevrev=total(prev,'sales');prevop=total(prev,'operating_income')
  dilution=None
  if end>=4:
   old=at(inc[dates[end-4]],'basic_shares_outstanding');new=at(inc[period],'basic_shares_outstanding')
   if old is not None and old>0 and new is not None and not raw.get('splits',{}).get('splits'):dilution=new/old-1
  if period==dates[-1]:
   common=at(statistics,'financials.income_statement.net_income_to_common_ttm')
   if common is not None and statistics.get('financials',{}).get('most_recent_quarter')==period:net=common
  out.append(dict(periodEnd=period,filedAt=today,availableAt=today,version='observed-'+period+'-'+today,observedOnly=True,
    revenue=revenue,operatingIncome=op,netIncome=net,equity=equity,cfo=total(cc,'operating_activities.operating_cash_flow'),
    capex=total(cc,'investing_activities.capital_expenditures',True),shares=shares,debt=debt,cash=cash,
    interest=total(ii,'non_operating_interest.expense',True),investedCapital=equity+debt-cash if all(x is not None for x in [equity,debt,cash]) else None,
    taxRate=taxrate,previousRevenue=prevrev,previousOperatingIncome=prevop,
    previousMargin=prevop/prevrev if prevop is not None and prevrev is not None and prevrev>0 else None,dilution=dilution))
 return out[-12:] or [blank_snapshot(today)]

def completed_date(market,now):
 local=now.astimezone(KST if market=='KR' else NY)
 cutoff=18*60 # EOD publishing buffer, not just market-close time.
 day=local.date()
 if local.hour*60+local.minute<cutoff:day-=timedelta(days=1)
 while day.weekday()>4:day-=timedelta(days=1)
 return day.isoformat()

def normalize(spec,raw,now):
 today=now.astimezone(KST).date().isoformat();currency='KRW' if spec['market']=='KR' else 'USD'
 issues=[];warnings=['수집 관측일 기준 재무 · 실제 과거 공시일 미확인 · 백테스트 금지','표준 재무의 주주 귀속·투하자본은 단순 추정']
 series=raw['time_series'];meta=series.get('meta',{})
 if meta.get('currency')!=currency:raise DataError('가격 통화가 시장과 일치하지 않습니다.')
 if str(meta.get('symbol','')).upper()!=spec['symbol'].upper() or meta.get('mic_code')!=spec['mic']:raise DataError('응답 종목·MIC가 요청과 다릅니다.')
 values=series.get('values')
 if not isinstance(values,list):raise DataError('일봉 응답이 없습니다.')
 cutoff=completed_date(spec['market'],now);bars=[];seen=set()
 splits=raw.get('splits',{}).get('splits')
 lastsplit=''
 if not isinstance(splits,list):issues.append('분할 이력 조회 실패 · 가격/거래량 기준 미확인')
 else:
  for split in splits:
   if not isinstance(split,dict) or not valid_date(split.get('date')):raise DataError('분할 날짜 형식 오류')
   if split['date']<=cutoff:lastsplit=max(lastsplit,split['date'])
  if lastsplit:warnings.append('분할 전 일봉 제거 · 최근 분할 뒤 80거래일 전 기술평가 보류')
 for v in values:
  if not isinstance(v,dict) or not valid_date(v.get('datetime')):raise DataError('일봉 날짜 형식 오류')
  d=v['datetime']
  if d>cutoff or d<lastsplit:continue
  if d in seen:raise DataError('중복 일봉 날짜')
  seen.add(d);b=dict(date=d,**{k:numeric(v.get(k)) for k in ['open','high','low','close','volume']})
  if any(b[k] is None or b[k]<0 or (k!='volume' and b[k]==0) for k in ['open','high','low','close','volume']):raise DataError('일봉 OHLCV 결측·비정상')
  if b['low']>min(b['open'],b['close']) or b['high']<max(b['open'],b['close']):raise DataError('일봉 고저 범위 오류')
  bars.append(b)
 bars=sorted(bars,key=lambda x:x['date'])[-400:]
 if len(bars)<25:raise DataError('완료 일봉 25개 미만 · 최근 분할/신규 상장/조회 실패 확인')
 if bars[-1]['date']<cutoff:warnings.append('최근 예상 거래일보다 일봉이 늦음 · 휴장/제공자 게시 지연 확인')
 if (datetime.fromisoformat(today)-datetime.fromisoformat(bars[-1]['date'])).days>7:issues.append('가격 자료 7일 초과 지연')
 profile=raw.get('profile',{});sector=profile.get('sector')
 if not isinstance(sector,str) or not sector.strip():sector='업종 미확인';issues.append('업종 조회 미확인')
 try:
  for endpoint in ['income_statement','balance_sheet','cash_flow']:
   metaFinancial=raw[endpoint].get('meta',{})
   if str(metaFinancial.get('symbol','')).upper()!=spec['symbol'].upper() or metaFinancial.get('mic_code')!=spec['mic']:raise DataError('재무 응답 종목 불일치')
  snapshots=ttm_snapshots(raw,currency,today)
  financialDate=datetime.fromisoformat(raw.get('_financialFetchedAt') or now.isoformat()).astimezone(KST).date().isoformat()
  for snapshot in snapshots:
   snapshot['periodEnd']=min(snapshot['periodEnd'],financialDate);snapshot['filedAt']=financialDate;snapshot['availableAt']=financialDate;snapshot['version']='observed-'+snapshot['periodEnd']+'-'+financialDate
  latestFiscal=max((r['fiscal_date'] for r in raw['income_statement']['income_statement'] if r['fiscal_date']<=today),default='')
  if snapshots[-1]['periodEnd']!=latestFiscal:issues.append('최신 분기 연결 재무 미완료')
 except (KeyError,DataError,TypeError,ValueError):
  snapshots=[blank_snapshot(today)];issues.append('분기 재무/통계 미지원·권한·통화 확인 필요')
 if all(s['revenue'] is None for s in snapshots):issues.append('연속 4분기 재무 미확보')
 if raw.get('_cached'):warnings.append('재무 캐시 사용 · 수집 시각을 확인하세요')
 for f in snapshots:
  for field in ['revenue','shares','debt','cash','capex','interest','investedCapital']:
   if f.get(field) is not None and f[field]<0:raise DataError('재무 비음수 필드 값 오류: '+field)
 name=profile.get('name') or meta.get('name') or spec['symbol']
 return dict(id=spec['market']+'-'+spec['symbol']+'-'+spec['mic'],name=str(name)[:80],symbol=spec['symbol'],market=spec['market'],currency=currency,
             sector=sector[:80],financialSector=bool(re.search(r'financial|bank|insurance',sector,re.I)),bars=bars,snapshots=snapshots,flags=[],
             dataIssues=issues,dataWarnings=warnings,observedAt=now.isoformat(),financialFetchedAt=raw.get('_financialFetchedAt'),mic=spec['mic'])

class Collector:
 def __init__(self,directory,transport=None,clock=None,analyzer=None):
  self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True);os.chmod(self.directory,0o700)
  self.processLock=open(self.directory/'collector.lock','a')
  os.chmod(self.directory/'collector.lock',0o600)
  try:fcntl.flock(self.processLock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except OSError:
   self.processLock.close()
   raise DataError('같은 조회 폴더의 서버가 이미 실행 중입니다.') from None
  self.clock=clock or (lambda:datetime.now(timezone.utc));self.transport=transport or self.network;self.analyzer=analyzer or self.analyze
  self.lock=threading.RLock();self.stop=threading.Event();self.worker=None;self.minute=[];self.run_used=0;self.running=False
  self.configPath=self.directory/'data-config.json';self.statePath=self.directory/'collection-state.json'
  self.config=self.validate_config(self.read(self.configPath,DEFAULTS));self.state=self.read(self.statePath,dict(jobs=[],claims=[],daily={}))
  for job in self.state['jobs']:
   if job['phase']=='RUNNING':job.update(phase='INTERRUPTED',note='서버 재시작 · 해당 슬롯 자동 재수집 없음')
  write_json(self.statePath,self.state)
 @staticmethod
 def read(path,fallback):
  if not path.exists():return copy.deepcopy(fallback)
  try:return json.loads(path.read_text())
  except Exception:raise DataError('수집 설정/기록 파일 손상 · 이전 자료를 확인하세요.') from None
 def validate_config(self,value):
  if not isinstance(value,dict):raise DataError('조회 설정은 객체여야 합니다.')
  c={**copy.deepcopy(DEFAULTS),**{k:value[k] for k in DEFAULTS if k in value}}
  if c['universeMode'] not in ['watchlist','master']:raise DataError('Universe mode must be watchlist or master')
  if not isinstance(c['apiKey'],str) or len(c['apiKey'])>200 or any(ord(x)<32 for x in c['apiKey']):raise DataError('API 키 형식 오류')
  if type(c['scheduled']) is not bool or type(c['frequency']) is not int or c['frequency'] not in [1,2]:raise DataError('스케줄 설정 오류')
  for k in ['morning','evening']:
   if not isinstance(c[k],str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',c[k]):raise DataError('시간은 HH:MM입니다.')
  if c['morning']>=c['evening']:raise DataError('아침 시간이 저녁보다 앞서야 합니다.')
  for k,lo,hi in [('creditsPerMinute',100,10000),('maxCreditsPerRun',1,10000000),('maxCreditsPerDay',1,20000000),('financialCacheHours',1,48)]:
   if type(c[k]) is not int or not lo<=c[k]<=hi:raise DataError('호출/캐시 한도 설정 오류: '+k)
  if not isinstance(c['symbols'],list) or not 1<=len(c['symbols'])<=200:raise DataError('분석 종목 1~200개를 입력하세요.')
  seen=set()
  for s in c['symbols']:
   if not isinstance(s,dict) or set(s)!=set(['symbol','mic','market']):raise DataError('종목은 symbol/mic/market가 필요합니다.')
   market=s['market'];mic=s['mic'];sym=s['symbol']
   if market=='KR':ok=mic in ['XKRX','XKOS','XKON'] and isinstance(sym,str) and re.fullmatch(r'[0-9A-Z]{6}',sym)
   else:ok=market=='US' and mic in ['XNAS','XNYS','XASE'] and isinstance(sym,str) and re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,11}',sym)
   if not ok:raise DataError('종목 코드/시장/MIC가 잘못됐습니다.')
   key=(market,mic,sym)
   if key in seen:raise DataError('중복 종목')
   seen.add(key)
  return c
 def save_config(self,data):
  with self.lock:
   if self.running:raise DataError('수집 중에는 설정을 바꿀 수 없습니다.')
   c={**self.config,**data}
   if not data.get('apiKey'):c['apiKey']=self.config['apiKey']
   c=self.validate_config(c);write_json(self.configPath,c);self.config=c
   return self.status()
 def node_path(self):
  for path in [shutil.which('node'),'/opt/homebrew/bin/node','/usr/local/bin/node']:
   if path and Path(path).is_file() and os.access(path,os.X_OK):return path
  return None
 def status(self):
  with self.lock:
   c={k:v for k,v in self.config.items() if k!='apiKey'}
   today=self.clock().astimezone(KST).date().isoformat()
   return dict(provider='Twelve Data',configured=bool(self.config['apiKey']),readOnly=True,brokerEnabled=False,config=c,running=self.running,
     nodeAvailable=bool(self.node_path()),creditsToday=self.state['daily'].get(today,0),jobs=copy.deepcopy(self.state['jobs'][-20:][::-1]),
     scheduler='맥의 로컬 서버가 실행 중일 때 동작',schedulePolicy='2회: 아침 미국/저녁 한국 · 1회: 저녁 양 시장',lastData=self.latest_summary())
 def latest_summary(self):
  latest=self.read(self.directory/'latest.json',None)
  return {k:latest[k] for k in ['jobId','collectedAt','asOf','count','marketDates','failures','analysisStatus'] if k in latest} if latest else None
 def network(self,endpoint,params):
  if endpoint not in COSTS:raise DataError('허용하지 않는 조회 경로')
  # The key is not logged or returned to the browser. Fixed host and GET only.
  url='https://api.twelvedata.com/'+endpoint+'?'+urllib.parse.urlencode({**params,'apikey':self.config['apiKey']})
  class NoRedirect(urllib.request.HTTPRedirectHandler):
   def redirect_request(self,*args,**kwargs):return None
  try:
   with urllib.request.build_opener(NoRedirect()).open(urllib.request.Request(url,headers={'Accept':'application/json'}),timeout=20) as r:
    raw=r.read(8*1024*1024+1)
    if len(raw)>8*1024*1024:raise DataError('제공자 응답 용량 초과')
    data=json.loads(raw)
  except urllib.error.HTTPError as e:
   if e.code in [401,403,429]:raise AccessError('제공자 인증/권한/호출 한도 오류 '+str(e.code)) from None
   raise DataError('데이터 제공자 HTTP 오류 '+str(e.code)) from None
  except DataError:raise
  except Exception:raise DataError('조회 응답 미확인 · 기존 자료 유지') from None
  if not isinstance(data,dict):raise DataError('조회 응답 객체 오류')
  if data.get('status')=='error':
   code=data.get('code')
   if code in [401,403,429]:raise AccessError('제공자 인증/권한/호출 한도 오류 '+str(code))
   raise DataError('종목/자료 조회 실패 · 제공자 코드 '+str(code)[:8])
  return data
 def request(self,endpoint,params):
  cost=COSTS[endpoint];today=self.clock().astimezone(KST).date().isoformat()
  with self.lock:
   if self.run_used+cost>self.config['maxCreditsPerRun'] or self.state['daily'].get(today,0)+cost>self.config['maxCreditsPerDay']:raise BudgetError('수집 호출 크레딧 한도 도달')
   self.run_used+=cost;self.state['daily'][today]=self.state['daily'].get(today,0)+cost
   self.state['daily']={k:v for k,v in self.state['daily'].items() if k>=(self.clock().astimezone(KST).date()-timedelta(days=30)).isoformat()}
   write_json(self.statePath,self.state)
  while True:
   now=time.monotonic();self.minute=[x for x in self.minute if now-x[0]<61]
   if sum(x[1] for x in self.minute)+cost<=self.config['creditsPerMinute']:break
   if self.stop.wait(min(1,max(.05,61-(now-self.minute[0][0])))):raise DataError('서버 종료 요청')
  self.minute.append((time.monotonic(),cost))
  return self.transport(endpoint,params)
 def analyze(self,data,asof,score_config):
  node=self.node_path()
  if not node:raise DataError('Node.js 18+ 설치 필요 · 수집 자료는 저장됨, 자동 점수 미계산')
  payload=json.dumps(dict(data=data,asOf=asof,config=score_config),allow_nan=False).encode()
  if len(payload)>512*1024*1024:raise DataError('분석 데이터 512MiB 한도 초과')
  try:r=subprocess.run([node,str(ROOT/'analyze.cjs')],input=payload,capture_output=True,timeout=600)
  except Exception:raise DataError('분석 엔진 실행 실패') from None
  if r.returncode:raise DataError('분석 엔진 입력 검증 실패 · 새 결과 미적용')
  return json.loads(r.stdout)
 def latest(self):return self.read(self.directory/'latest.json',None)
 def start(self,market='ALL',reason='manual',claim=None):
  with self.lock:
   if market not in ['ALL','KR','US']:raise DataError('수집 시장 오류')
   if self.running:raise DataError('이미 수집 중입니다.')
   if not self.config['apiKey']:raise DataError('Twelve Data API 키를 먼저 저장하세요. 증권계좌는 필요 없습니다.')
   master=self.read(self.directory/'universe.json',{'schemaVersion':1,'markets':{}})
   if master['markets']:
    try:validate_master(master,self.clock().astimezone(KST).date().isoformat())
    except ValueError:raise DataError('Universe/status snapshot invalid; import a current validated file') from None
   self.batchUniverse=copy.deepcopy(master['markets'])
   symbols=collection_symbols(master,market) if self.config['universeMode']=='master' else [s for s in self.config['symbols'] if market=='ALL' or s['market']==market]
   if not symbols:raise DataError('선택 시장의 분석 종목이 없습니다.')
   if claim and claim in self.state['claims']:return dict(skipped=True)
   id=secrets.token_hex(12);now=self.clock().isoformat()
   job=dict(id=id,startedAt=now,phase='RUNNING',market=market,reason=reason,total=len(symbols),completed=0,credits=0,failures=[],note='수집 시작')
   self.state['jobs'].append(job);self.state['jobs']=self.state['jobs'][-30:]
   if claim:self.state['claims']=(self.state['claims']+[claim])[-90:]
   write_json(self.statePath,self.state);self.running=True;self.run_used=0
   self.worker=threading.Thread(target=self.run,args=(job,symbols),daemon=True);self.worker.start()
   return dict(jobId=id,phase='RUNNING')
 def run(self,job,symbols):
  successes=[];failures=[];now=self.clock();today=now.astimezone(KST).date().isoformat()
  try:
   for spec in symbols:
    if self.stop.is_set():break
    params=dict(symbol=spec['symbol'],mic_code=spec['mic'])
    try:
     raw={'time_series':self.request('time_series',{**params,'interval':'1day','outputsize':400,'order':'asc','adjust':'none','end_date':completed_date(spec['market'],now)})}
     cachePath=self.directory/'cache'/('td-'+spec['market']+'-'+spec['mic']+'-'+spec['symbol']+'.json')
     cached=self.read(cachePath,None);cacheFresh=False
     if cached:
      age=(now-datetime.fromisoformat(cached['fetchedAt'])).total_seconds()
      cacheFresh=0<=age<self.config['financialCacheHours']*3600
     if cacheFresh:
      raw.update(cached['raw']);raw['_cached']=True;raw['_financialFetchedAt']=cached['fetchedAt']
     else:
      financial={};errors=[]
      for endpoint in ['splits','profile','statistics','income_statement','balance_sheet','cash_flow']:
       try:financial[endpoint]=self.request(endpoint,{**params,**({'period':'quarterly','outputsize':12} if endpoint in ['income_statement','balance_sheet','cash_flow'] else {})})
       except BudgetError:raise
       except AccessError as e:
        if '403' in str(e):errors.append(endpoint+' 권한 없음');break
        raise
       except DataError:errors.append(endpoint+' 조회 실패')
      raw.update(financial);raw['_financialFetchedAt']=now.isoformat()
      if errors:failures.append(dict(symbol=spec['symbol'],market=spec['market'],error='일봉 확보 · 재무 일부 실패: '+', '.join(errors)))
      if not errors and all(k in financial for k in ['splits','profile','statistics','income_statement','balance_sheet','cash_flow']):write_json(cachePath,dict(fetchedAt=now.isoformat(),raw=financial))
     stock=normalize(spec,raw,now)
     entry=next((e for e in self.batchUniverse.get(spec['market'],{}).get('entries',[]) if e['id']==stock['id']),{})
     if 'dividend' in entry:stock['dividend']=copy.deepcopy(entry['dividend'])
     successes.append(stock)
    except (BudgetError,AccessError) as e:
     failures.append(dict(symbol=spec['symbol'],market=spec['market'],error=str(e)));break # No quota/auth storm across the universe.
    except Exception as e:
     failures.append(dict(symbol=spec['symbol'],market=spec['market'],error=str(e) if isinstance(e,DataError) else '종목 자료 변환 실패'))
    with self.lock:job.update(completed=len(successes),credits=self.run_used,failures=failures,note=spec['symbol']+' 처리');write_json(self.statePath,self.state)
   processed={(x['market'],x['symbol']) for x in successes}|{(x['market'],x['symbol']) for x in failures}
   for s in symbols:
    if (s['market'],s['symbol']) not in processed:failures.append(dict(symbol=s['symbol'],market=s['market'],error='한도/중단으로 이번 실행에서 미수집'))
   if not successes:raise DataError('성공한 종목 없음 · 기존 결과 유지')
   # Replace only this batch's markets; keep other market data with its original dates/provenance.
   old=self.latest();targetMarkets={s['market'] for s in symbols}
   allowedSymbols=collection_symbols({'markets':self.batchUniverse},'ALL') if self.config['universeMode']=='master' else self.config['symbols']
   allowedIds={s['market']+'-'+s['symbol']+'-'+s['mic'] for s in allowedSymbols}
   preserved=[s for s in old['data']['stocks'] if s['market'] not in targetMarkets and s['id'] in allowedIds] if old else []
   stocks=preserved+successes
   for s in preserved:
    if (datetime.fromisoformat(today)-datetime.fromisoformat(s['bars'][-1]['date'])).days>7 and '가격 자료 7일 초과 지연' not in s.get('dataIssues',[]):s.setdefault('dataIssues',[]).append('가격 자료 7일 초과 지연')
   dataset=dict(schemaVersion=1,synthetic=False,source='Twelve Data · 관측일 기준 · 일부 종목 실패는 수집 기록 확인',priceBasis='split-consistent',pitPolicy='observed-only',collectedAt=now.isoformat(),analysisAsOf=today,stocks=stocks)
   # Re-read status snapshot immediately before ranking publication.
   refreshed=self.read(self.directory/'universe.json',{'schemaVersion':1,'markets':{}})
   if refreshed['markets']:
    try:validate_master(refreshed,self.clock().astimezone(KST).date().isoformat())
    except ValueError:raise DataError('Publication status recheck failed; previous result retained') from None
    self.batchUniverse=copy.deepcopy(refreshed['markets'])
   oldUniverse=old['data'].get('universe',{}) if old else {}
   dataset['universe']={m:copy.deepcopy(self.batchUniverse.get(m,{})) if m in targetMarkets else copy.deepcopy(oldUniverse.get(m,{})) for m in ['KR','US']}
   # Watchlist mode can never claim whole-market completeness.
   if self.config['universeMode']=='watchlist':
    for meta in dataset['universe'].values():meta['complete']=False
   analysis=None;analysisStatus='완료'
   try:analysis=self.analyzer(dataset,today,{})
   except DataError as e:
    if '입력 검증 실패' in str(e):raise
    analysisStatus=str(e)
   latest=dict(jobId=job['id'],collectedAt=now.isoformat(),asOf=today,count=len(stocks),marketDates={m:max(s['bars'][-1]['date'] for s in stocks if s['market']==m) for m in ['KR','US'] if any(s['market']==m for s in stocks)},failures=failures,analysisStatus=analysisStatus,data=dataset,analysis=analysis)
   write_json(self.directory/'latest.json',latest)
   write_json(self.directory/'reports'/(job['id']+'.json'),latest)
   reports=sorted((self.directory/'reports').glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)
   for path in reports[30:]:path.unlink()
   if analysis and analysis.get('rankings'):
    from rankings_store import publish
    publish(self.directory,analysis['rankings'],now)
   else:
    from rankings_store import publish_failure
    publish_failure(self.directory,targetMarkets,self.clock(),analysisStatus)
   with self.lock:job.update(phase='PARTIAL' if failures or analysis is None or any(r['status']!='verified' for r in (analysis or {}).get('rankings',[]) if r['market'] in targetMarkets) else 'DONE',completed=len(successes),note=analysisStatus,failures=failures,endedAt=self.clock().isoformat(),credits=self.run_used)
  except Exception as e:
   from rankings_store import publish_failure
   try:publish_failure(self.directory,{s['market'] for s in symbols},self.clock(),str(e) if isinstance(e,DataError) else 'Collection failed; previous result retained')
   except (OSError,ValueError):pass
   with self.lock:job.update(phase='FAILED',note=str(e) if isinstance(e,DataError) else '수집 처리 실패 · 이전 결과 유지',failures=failures,credits=self.run_used,endedAt=self.clock().isoformat())
  finally:
   with self.lock:self.running=False;write_json(self.statePath,self.state)
 def tick(self,now=None):
  now=now or self.clock();local=now.astimezone(KST)
  with self.lock:
   c=copy.deepcopy(self.config)
   if not c['scheduled'] or not c['apiKey'] or self.running:return
  timeNow=local.strftime('%H:%M');today=local.date().isoformat()
  slots=[('evening',c['evening'],'ALL')] if c['frequency']==1 else [('morning',c['morning'],'US'),('evening',c['evening'],'KR')]
  for name,due,market in slots:
   # At most 3h catch-up. Never replay many missed days after sleep/reboot.
   minutes=lambda x:int(x[:2])*60+int(x[3:])
   if not 0<=minutes(timeNow)-minutes(due)<=180:continue
   if market=='KR' and local.weekday()>4:continue
   if market=='US' and datetime.fromisoformat(completed_date('US',now)).weekday()>4:continue
   # US morning: Saturday follows Friday; Monday has no fresh US session.
   if market=='US' and local.weekday() not in [1,2,3,4,5]:continue
   claim=today+'-'+name
   try:self.start(market,'schedule',claim)
   except DataError:pass
 def scheduler(self):
  while not self.stop.is_set():
   self.tick()
   self.stop.wait(15)
 def begin_scheduler(self):threading.Thread(target=self.scheduler,daemon=True).start()
 def close(self):
  self.stop.set()
  if self.worker and self.worker.is_alive():self.worker.join(timeout=22)
  if not self.running and not self.processLock.closed:self.processLock.close()
