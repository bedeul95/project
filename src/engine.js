(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.Quant=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const VERSION='1.3.0';
 const defaults={valueWeight:20,qualityWeight:20,safetyWeight:20,growthWeight:10,minScore:70,minFundamental:45,minTechnical:12,minTurnoverKR:100000000,minTurnoverUS:100000,volumeRatio:1.8,flatReturn:5,flatRange:10,flowRequired:false,topN:5,maxWeight:20,rebalance:20,feeBp:13};
 const financialFields=['revenue','operatingIncome','netIncome','equity','cfo','capex','shares','debt','cash','interest','investedCapital','taxRate','previousRevenue','previousOperatingIncome','previousMargin','dilution'];
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
 const clamp=x=>Math.max(0,Math.min(100,x));
 const scale=(x,lo,hi)=>finite(x)?clamp((x-lo)/(hi-lo)*100):null;
 function date(d){return typeof d==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(d)&&Number.isFinite(Date.parse(d))&&new Date(d+'T00:00:00Z').toISOString().slice(0,10)===d;}
 function validate(data){
  if(!data||data.schemaVersion!==1||!Array.isArray(data.stocks)||data.stocks.length<1||data.stocks.length>20000)throw Error('schemaVersion: 1과 종목 1~20,000개가 필요합니다.');
  if(data.priceBasis!=='split-consistent')throw Error('priceBasis는 split-consistent여야 합니다. 가격·주식수·거래량의 분할 기준을 맞춰주세요.');
  if(typeof data.source!=='string'||!data.source.trim()||data.source.length>200)throw Error('데이터 출처(source)를 입력하세요.');
  if(typeof data.synthetic!=='boolean')throw Error('synthetic은 true 또는 false여야 합니다.');
  const ids=new Set();
  for(const s of data.stocks){
   for(const field of ['id','name','sector'])if(typeof s[field]!=='string'||!s[field].trim()||s[field].length>80)throw Error('종목의 id/name/sector를 확인하세요.');
   if(['__proto__','constructor','prototype','toString','hasOwnProperty','valueOf'].includes(s.id))throw Error('사용할 수 없는 종목 ID입니다.');
   if(ids.has(s.id))throw Error('중복 종목 ID: '+s.id);ids.add(s.id);
   if(!['KR','US'].includes(s.market)||s.currency!==(s.market==='KR'?'KRW':'USD'))throw Error(s.name+': 시장과 통화가 맞지 않습니다.');
   for(const k of ['dataIssues','dataWarnings'])if(s[k]!==undefined&&(!Array.isArray(s[k])||s[k].length>30||s[k].some(x=>typeof x!=='string'||x.length>300)))throw Error('자료 검사 항목 형식 오류');
   if(typeof s.financialSector!=='boolean')throw Error(s.name+': financialSector를 명시하세요.');
   if(!Array.isArray(s.bars)||s.bars.length<25||s.bars.length>2500)throw Error(s.name+': 가격 행은 25~2,500개가 필요합니다.');
   let previous='';
   for(const b of s.bars){
    if(!date(b.date)||b.date<=previous)throw Error(s.name+': 날짜는 중복 없이 오름차순이어야 합니다.');previous=b.date;
    for(const f of ['open','high','low','close','volume'])if(!finite(b[f])||b[f]<0||(f!=='volume'&&b[f]===0))throw Error(s.name+': OHLCV 숫자를 확인하세요.');
    if(b.low>Math.min(b.open,b.close)||b.high<Math.max(b.open,b.close)||b.low>b.high)throw Error(s.name+': 고가·저가 범위가 잘못됐습니다.');
   }
   if(!Array.isArray(s.snapshots)||s.snapshots.length<1||s.snapshots.length>100)throw Error(s.name+': 재무 스냅샷 1~100개가 필요합니다.');
   const versions=new Set(),availableVersions=new Set();
   for(const f of s.snapshots){
    if(!date(f.periodEnd)||!date(f.filedAt)||!date(f.availableAt)||f.periodEnd>f.filedAt||f.filedAt>f.availableAt)throw Error(s.name+': 결산일 ≤ 공시일 ≤ 사용가능일을 확인하세요.');
    if(typeof f.version!=='string'||!f.version||f.version.length>80||versions.has(f.version))throw Error(s.name+': 서로 다른 재무 버전 ID가 필요합니다.');versions.add(f.version);
    const timeKey=f.periodEnd+'|'+f.availableAt;
    if(availableVersions.has(timeKey))throw Error(s.name+': 같은 결산일·사용가능일의 여러 버전은 날짜 단위로 구분할 수 없습니다.');availableVersions.add(timeKey);
    for(const key of financialFields)if(f[key]!==null&&f[key]!==undefined&&!finite(f[key]))throw Error(s.name+': '+key+'는 숫자 또는 null이어야 합니다.');
    for(const key of ['revenue','shares','debt','cash','capex','interest','investedCapital'])if(finite(f[key])&&f[key]<0)throw Error(s.name+': '+key+'는 음수일 수 없습니다.');
    if(finite(f.taxRate)&&(f.taxRate<0||f.taxRate>1))throw Error('taxRate는 0~1입니다.');
   }
   if(s.flags!==undefined&&(!Array.isArray(s.flags)||s.flags.length>20))throw Error('flags는 배열입니다.');
   for(const f of s.flags||[])if(!f||!date(f.date)||!['halt','accounting','event','delisted'].includes(f.type)||typeof f.note!=='string'||f.note.length>300)throw Error('이벤트의 date/type/note를 확인하세요.');
  }
  return data;
 }
 function config(input={}){
  const c={...defaults,...input};
  for(const k of ['valueWeight','qualityWeight','safetyWeight','growthWeight','minScore','minFundamental','minTechnical','minTurnoverKR','minTurnoverUS','flatReturn','flatRange','feeBp'])if(!finite(c[k])||c[k]<0)throw Error('설정값은 0 이상의 숫자여야 합니다.');
  if(Math.abs(c.valueWeight+c.qualityWeight+c.safetyWeight+c.growthWeight-70)>.0001)throw Error('기업·안정성 가중치 합계는 70이어야 합니다. 기술 점수는 30점 고정입니다.');
  if(c.minFundamental>70||c.minTechnical>30)throw Error('기업 기준은 0~70점, 기술 기준은 0~30점입니다.');
  if(c.minScore>100||c.flatReturn>100||c.flatRange>100||c.feeBp>500||!finite(c.volumeRatio)||c.volumeRatio<1||c.volumeRatio>20)throw Error('평가·거래량·비용 설정 범위를 확인하세요.');
  for(const k of ['topN','rebalance'])if(!Number.isInteger(c[k])||c[k]<1||c[k]>(k==='topN'?50:100))throw Error('보유 수/재평가 주기를 확인하세요.');
  if(!finite(c.maxWeight)||c.maxWeight<1||c.maxWeight>100||typeof c.flowRequired!=='boolean')throw Error('종목 비중/거래량 필수 조건을 확인하세요.');
  return c;
 }
 function snapshot(stock,asOf){
  return stock.snapshots.filter(f=>f.availableAt<=asOf).sort((a,b)=>b.periodEnd.localeCompare(a.periodEnd)||b.availableAt.localeCompare(a.availableAt)||b.filedAt.localeCompare(a.filedAt)).at(0)||null;
 }
 function flow(bars,asOf,c=defaults){
  const a=bars.filter(b=>b.date<=asOf);if(a.length<25)return {ready:false,status:'관찰 기간 부족'};
  const tail=a.slice(-5),base=a.slice(-25,-5),recent=a.slice(-10),prior=a.at(-11),last=a.at(-1);
  const baseVolume=mean(base.map(x=>x.volume)),ratio=baseVolume?mean(tail.map(x=>x.volume))/baseVolume:null;
  const change=last.close/prior.close-1,range=(Math.max(...recent.map(x=>x.high))-Math.min(...recent.map(x=>x.low)))/mean(recent.map(x=>x.close));
  const repeated=baseVolume?tail.filter(b=>b.volume/baseVolume>=1.5).length:0;
  const active=finite(ratio)&&ratio>=c.volumeRatio&&Math.abs(change)*100<=c.flatReturn&&range*100<=c.flatRange&&repeated>=3;
  const lastRange=last.high-last.low,closeLocation=lastRange?(last.close-last.low)/lastRange:.5;
  return {ready:true,ratio,change,range,repeated,active,closeLocation,tradedValue:mean(base.map(x=>x.close*x.volume)),status:active?'횡보·거래량 증가':finite(ratio)&&ratio>=c.volumeRatio?'거래량 증가':'일반',hint:active?'방향 미확인 · 매집으로 단정할 수 없음':null};
 }
 function weighted(items){const total=items.reduce((s,x)=>s+x[1],0),known=items.filter(x=>finite(x[0]));return {score:items.reduce((s,x)=>s+(finite(x[0])?x[0]:0)*x[1],0)/total,coverage:known.reduce((s,x)=>s+x[1],0)/total};}
 function emaSeries(values,period){const out=values.map(()=>null);if(values.length<period)return out;let current=mean(values.slice(0,period));out[period-1]=current;for(let i=period;i<values.length;i++){current+=(values[i]-current)*2/(period+1);out[i]=current;}return out;}
 function technical(bars,asOf,c=defaults){
  const a=bars.filter(b=>b.date<=asOf),fl=flow(bars,asOf,c),parts={volume:0,trend:0,momentum:0,volatility:0};
  if(a.length<80)return {ready:false,total:0,parts,reasons:['기술 분석 80거래일 필요'],metrics:{}};
  const close=a.map(b=>b.close),last=close.at(-1),sma20=mean(close.slice(-20)),sma60=mean(close.slice(-60)),previous60=mean(close.slice(-80,-20));
  let gain=0,loss=0,tr=0;for(let i=1;i<=14;i++){const delta=close[i]-close[i-1];gain+=Math.max(delta,0);loss+=Math.max(-delta,0);tr+=Math.max(a[i].high-a[i].low,Math.abs(a[i].high-close[i-1]),Math.abs(a[i].low-close[i-1]));}gain/=14;loss/=14;tr/=14;
  for(let i=15;i<a.length;i++){const delta=close[i]-close[i-1];gain=(gain*13+Math.max(delta,0))/14;loss=(loss*13+Math.max(-delta,0))/14;const range=Math.max(a[i].high-a[i].low,Math.abs(a[i].high-close[i-1]),Math.abs(a[i].low-close[i-1]));tr=(tr*13+range)/14;}
  const rsi=loss===0?(gain===0?50:100):100-100/(1+gain/loss),atrPct=tr/last;
  const e12=emaSeries(close,12),e26=emaSeries(close,26),macd=close.slice(25).map((_,i)=>e12[i+25]-e26[i+25]),signal=emaSeries(macd,9),hist=macd.at(-1)-signal.at(-1),previousHist=macd.at(-2)-signal.at(-2);
  const sd=Math.sqrt(close.slice(-20).reduce((s,x)=>s+(x-sma20)**2,0)/20),upper=sma20+2*sd,lower=sma20-2*sd,bbPosition=upper>lower?(last-lower)/(upper-lower):.5,bandwidth=4*sd/sma20;
  parts.volume=fl.ready?4*(scale(fl.ratio,1,c.volumeRatio)||0)/100+(Math.abs(fl.change)*100<=c.flatReturn&&fl.range*100<=c.flatRange?4:0)+2*Math.min(1,fl.repeated/3):0;
  parts.trend=(last>=sma60?3:0)+(sma20>=sma60?3:0)+(sma60>=previous60?2:0);
  const rsiSuitability=rsi>=40&&rsi<=65?1:rsi>65&&rsi<80?(80-rsi)/15:rsi>=30&&rsi<40?(rsi-30)/10:0;
  parts.momentum=3*rsiSuitability+(hist>0?2:0)+(hist>previousHist?1:0);
  const bandSuitability=bbPosition>=.35&&bbPosition<=.8?1:bbPosition>.8&&bbPosition<1?(1-bbPosition)/.2:bbPosition>0&&bbPosition<.35?bbPosition/.35:0;
  parts.volatility=3*(1-scale(atrPct,.02,.06)/100)+3*bandSuitability;
  const reasons=[];if(atrPct>.06)reasons.push('ATR/종가 6% 초과');if(rsi>80)reasons.push('RSI 80 초과 · 과열');if(last<sma60*.9)reasons.push('60일 평균 대비 10% 이상 하락');
  return {ready:true,total:Object.values(parts).reduce((s,x)=>s+x,0),parts,reasons,metrics:{sma20,sma60,rsi,atr:tr,atrPct,macd:macd.at(-1),macdSignal:signal.at(-1),hist,bbPosition,bandwidth}};
 }
 function features(s,asOf,c,priceAsOf=asOf){
  const bars=s.bars.filter(b=>b.date<=priceAsOf),last=bars.at(-1),f=snapshot(s,asOf),reasons=[],warnings=[];
  if(!last||last.date!==priceAsOf)reasons.push('평가일 가격 없음');
  if(!f)reasons.push('당시 공개된 재무자료 없음');
  if(s.financialSector)reasons.push('금융업 별도 모델 필요');
  const flags=(s.flags||[]).filter(x=>x.date<=asOf);
  if(flags.some(x=>['halt','accounting','delisted'].includes(x.type)))reasons.push('거래·회계 제한 플래그');
  if(flags.some(x=>x.type==='event'&&asOf>=x.date&&Date.parse(asOf)-Date.parse(x.date)<=10*86400000))warnings.push('최근 이벤트 확인');
  const fl=flow(s.bars,priceAsOf,c),tech=technical(s.bars,priceAsOf,c);
  if(!f||!last)return {stock:s,f,last,flow:fl,tech,reasons,warnings,eligible:false,coverage:0,value:0,quality:0,safety:0,growth:0,fundamental:0,technical:tech.total,total:0,metrics:{}};
  for(const issue of s.dataIssues||[])reasons.push(issue);
  for(const warning of s.dataWarnings||[])warnings.push(warning);
  for(const k of ['revenue','operatingIncome','netIncome','equity','cfo','capex','shares'])if(!finite(f[k]))reasons.push('필수 재무 누락: '+k);
  if(!(f.equity>0))reasons.push('자본이 양수가 아님');
  if(!(f.netIncome>0)||!(f.operatingIncome>0))reasons.push('적자·턴어라운드 별도 평가');
  if(!(f.cfo>0))reasons.push('영업현금흐름이 양수가 아님');
  if(!(f.shares>0)||!(f.revenue>0))reasons.push('매출·주식수 확인 필요');
  if(!fl.ready||!(fl.tradedValue>0))reasons.push('거래량·유동성 데이터 부족');
  if(fl.ready&&fl.tradedValue<(s.market==='KR'?c.minTurnoverKR:c.minTurnoverUS))reasons.push('평균 거래대금 하한 미달');
  const marketCap=last.close*f.shares,fcf=finite(f.cfo)&&finite(f.capex)?f.cfo-f.capex:null;
  const ev=finite(f.debt)&&finite(f.cash)?marketCap+f.debt-f.cash:null;
  const roe=f.equity>0?f.netIncome/f.equity:null,margin=f.revenue>0?f.operatingIncome/f.revenue:null;
  const roic=f.investedCapital>0&&finite(f.taxRate)?f.operatingIncome*(1-f.taxRate)/f.investedCapital:null;
  const revenueGrowth=f.previousRevenue>0?f.revenue/f.previousRevenue-1:null;
  const profitGrowth=f.previousOperatingIncome>0?f.operatingIncome/f.previousOperatingIncome-1:null;
  const cashConversion=f.operatingIncome>0?f.cfo/f.operatingIncome:null;
  const debtCashFlow=f.cfo>0&&finite(f.debt)?f.debt/f.cfo:null;
  const interestCover=f.interest>0?f.operatingIncome/f.interest:f.interest===0?100:null;
  const earningsYield=marketCap>0?f.netIncome/marketCap:null,fcfYield=marketCap>0&&finite(fcf)?fcf/marketCap:null,opYield=ev>0?f.operatingIncome/ev:null;
  const history=s.snapshots.filter(x=>x.availableAt<=asOf&&finite(x.operatingIncome)).sort((a,b)=>b.periodEnd.localeCompare(a.periodEnd)||b.availableAt.localeCompare(a.availableAt));
  const seenPeriods=new Set(),profits=[];for(const h of history){if(!seenPeriods.has(h.periodEnd)){seenPeriods.add(h.periodEnd);profits.push(h.operatingIncome);}if(profits.length===4)break;}
  const avgProfit=profits.length?mean(profits):0,profitCV=profits.length>=2&&avgProfit>0?Math.sqrt(mean(profits.map(x=>(x-avgProfit)**2)))/avgProfit:null;
  const quality=weighted([[scale(roic,0,.25),30],[scale(cashConversion,0,1.2),25],[scale(margin,0,.25),25],[finite(profitCV)?100-scale(profitCV,0,.5):null,20]]);
  const safety=weighted([[finite(debtCashFlow)?100-scale(debtCashFlow,0,8):f.debt===0?100:null,40],[scale(interestCover,2,10),35],[finite(f.dilution)?100-scale(f.dilution,0,.1):null,25]]);
  const growth=weighted([[scale(revenueGrowth,-.05,.3),45],[scale(profitGrowth,-.1,.4),35],[finite(f.previousMargin)&&finite(margin)?scale(margin-f.previousMargin,-.03,.05):null,20]]);
  if(quality.coverage<.8||growth.coverage<.8||safety.coverage<.8)reasons.push('평가에 필요한 데이터 부족');
  if(finite(interestCover)&&interestCover<2)reasons.push('이자보상배율 2배 미만');
  if(finite(debtCashFlow)&&debtCashFlow>8)reasons.push('영업현금흐름 대비 부채 과다');
  if(Date.parse(asOf)-Date.parse(f.periodEnd)>550*86400000)reasons.push('재무자료 오래됨');
  if(finite(fcf)&&fcf<0)warnings.push('잉여현금흐름 음수');
  if(finite(f.dilution)&&f.dilution>.05)warnings.push('주식 희석 5% 초과');
  return {stock:s,f,last,flow:fl,tech,reasons,warnings,eligible:reasons.length===0,coverage:Math.min(quality.coverage,growth.coverage,safety.coverage),quality:quality.score,safety:safety.score,growth:growth.score,value:0,total:0,metrics:{marketCap,ev,fcf,roe,roic,margin,profitCV,revenueGrowth,profitGrowth,cashConversion,debtCashFlow,interestCover,earningsYield,fcfYield,opYield,per:f.netIncome>0?marketCap/f.netIncome:null,pbr:f.equity>0?marketCap/f.equity:null,evOp:ev>0&&f.operatingIncome>0?ev/f.operatingIncome:null}};
 }
 function ranker(pool){
  const a=pool.filter(finite).sort((x,y)=>x-y),n=a.length;
  return value=>{if(!finite(value)||!n)return 0;if(n===1)return 50;
   const bound=upper=>{let lo=0,hi=n;while(lo<hi){const mid=(lo+hi)>>1;if(a[mid]<value||(upper&&a[mid]===value))lo=mid+1;else hi=mid;}return lo;};
   const lower=bound(false),upper=bound(true);return 100*(lower+.5*(upper-lower-1))/(n-1);
  };
 }
 function screen(data,market,asOf,input={},priceAsOf=asOf){
  if(!['KR','US'].includes(market)||!date(asOf))throw Error('시장·평가일을 확인하세요.');const c=config(input);
  const results=data.stocks.filter(s=>s.market===market).map(s=>features(s,asOf,c,priceAsOf));
  const eligible=results.filter(p=>p.eligible),sectorPools=new Map();
  for(const p of eligible){if(!sectorPools.has(p.stock.sector))sectorPools.set(p.stock.sector,[]);sectorPools.get(p.stock.sector).push(p);}
  const rankCache=new Map();
  for(const r of results){
   let peers=sectorPools.get(r.stock.sector)||[];r.peerBasis='업종';
   if(peers.length<5){peers=eligible;r.peerBasis='시장 · 업종 표본 부족';}
   if(!rankCache.has(peers)){const functions={};for(const k of ['earningsYield','fcfYield','opYield'])functions[k]=ranker(peers.map(p=>p.metrics[k]));functions.pbr=ranker(peers.map(p=>p.metrics.pbr>0?1/p.metrics.pbr:null));rankCache.set(peers,functions);}
   const rank=rankCache.get(peers);
   const parts=['earningsYield','fcfYield','opYield'].map(k=>finite(r.metrics[k])&&r.metrics[k]>0?rank[k](r.metrics[k]):0);
   // PBR gets less influence, and must be supported by positive ROE.
   parts.push(r.metrics.pbr>0&&r.metrics.roe>0?rank.pbr(1/r.metrics.pbr):0);
   r.value=parts[0]*.3+parts[1]*.3+parts[2]*.3+parts[3]*.1;
   r.fundamental=(r.value*c.valueWeight+r.quality*c.qualityWeight+r.safety*c.safetyWeight+r.growth*c.growthWeight)/100;
   r.technical=r.tech.total;r.total=r.fundamental+r.technical;
   r.entryReasons=[...r.tech.reasons];if(r.fundamental<c.minFundamental)r.entryReasons.push('기업·안정성 점수 기준 미달');if(r.technical<c.minTechnical)r.entryReasons.push('기술 점수 기준 미달');if(r.total<c.minScore)r.entryReasons.push('총점 기준 미달');if(c.flowRequired&&!r.flow.active)r.entryReasons.push('횡보·거래량 필수 조건 미달');if(r.warnings.includes('최근 이벤트 확인'))r.entryReasons.push('최근 이벤트 확인');
   r.candidate=r.eligible&&r.tech.ready&&r.entryReasons.length===0;
  }
  return results.sort((a,b)=>Number(b.eligible)-Number(a.eligible)||b.total-a.total||a.stock.id.localeCompare(b.stock.id));
 }
 function backtest(data,market,input={}){
  if(data.pitPolicy==='observed-only')throw Error('관측일 기준 API 자료는 과거 시점 백테스트에 사용할 수 없습니다. 당시 공개된 재무 버전 자료를 입력하세요.');
  const c=config(input),stocks=data.stocks.filter(s=>s.market===market);
  if(!stocks.length)throw Error('선택 시장에 종목이 없습니다.');
  const dates=stocks[0].bars.map(b=>b.date);
  if(stocks.some(s=>s.bars.length!==dates.length||s.bars.some((b,i)=>b.date!==dates[i])))throw Error('연구 백테스트는 동일한 거래일 배열이 필요합니다. 거래정지·상장폐지와 불일치 자료는 별도 처리 후 사용하세요.');
  const start=input.start||dates[80],end=input.end||dates.at(-1),capital=input.capital??(market==='KR'?100000000:100000);
  if(!date(start)||!date(end)||start>=end||!finite(capital)||capital<=0||capital>1e15)throw Error('기간·자본을 확인하세요.');
  const first=dates.findIndex((d,i)=>i>=80&&d>=start),last=dates.findLastIndex(d=>d<=end);
  if(first<0||last-first<20)throw Error('관찰 기간 이후 최소 20거래일이 필요합니다.');
  let cash=capital,units=stocks.map(()=>0),peak=capital,fees=0,tradeCount=0,previousNav=capital;
  const curve=[],trades=[],bench=stocks.map((s,j)=>capital/stocks.length/s.bars[first].close);
  // Signal on the prior day's close. Execute at today's close, with cash-constrained integer quantities.
  for(let t=first;t<=last;t++){
   let nav=cash+stocks.reduce((sum,s,j)=>sum+units[j]*s.bars[t].close,0);
   if((t-first)%c.rebalance===0){
    const chosen=screen(data,market,dates[t-1],c).filter(r=>r.candidate).slice(0,c.topN),ids=new Set(chosen.map(r=>r.stock.id));
    const weight=chosen.length?Math.min(1/chosen.length,c.maxWeight/100):0;
    const desired=stocks.map(s=>ids.has(s.id)?Math.floor(nav*weight/s.bars[t].close):0);
    // Sells precede buys. Fees apply to the actual executed notional.
    for(const direction of [-1,1])for(let j=0;j<stocks.length;j++){
     const price=stocks[j].bars[t].close,delta=desired[j]-units[j];if(Math.sign(delta)!==direction)continue;
     let quantity=Math.abs(delta);if(direction===1)quantity=Math.min(quantity,Math.floor(cash/(price*(1+c.feeBp/10000))));if(quantity<=0)continue;
     const amount=quantity*price,fee=amount*c.feeBp/10000;cash+=direction===1?-amount-fee:amount-fee;units[j]+=direction*quantity;fees+=fee;tradeCount++;
     trades.push({date:dates[t],signalDate:dates[t-1],id:stocks[j].id,side:direction===1?'BUY':'SELL',quantity,price,fee});
    }
    nav=cash+stocks.reduce((sum,s,j)=>sum+units[j]*s.bars[t].close,0);
   }
   peak=Math.max(peak,nav);curve.push({date:dates[t],nav,drawdown:nav/peak-1,return:nav/previousNav-1,benchmark:stocks.reduce((sum,s,j)=>sum+bench[j]*s.bars[t].close,0)});previousNav=nav;
  }
  const returns=curve.map(p=>p.return),avg=mean(returns),sd=returns.length>1?Math.sqrt(returns.reduce((s,x)=>s+(x-avg)**2,0)/(returns.length-1)):0,final=curve.at(-1);
  return {curve,trades,cash,fees,tradeCount,holdings:stocks.map((s,j)=>({id:s.id,quantity:units[j],price:s.bars[last].close})),metrics:{total:final.nav/capital-1,mdd:Math.min(...curve.map(p=>p.drawdown)),sharpe:sd?avg/sd*Math.sqrt(252):0,benchmark:final.benchmark/capital-1,days:curve.length},capital,currency:market==='KR'?'KRW':'USD'};
 }
 function paperOrder(account,stock,side,quantity,feeBp=13){
  if(!['BUY','SELL'].includes(side)||!Number.isInteger(quantity)||quantity<=0||!finite(feeBp)||feeBp<0||feeBp>500)throw Error('수량은 양의 정수, 비용은 0~500bp로 입력하세요.');
  if(account.currency!==stock.currency)throw Error('모의 계좌 통화가 다릅니다.');
  const a=JSON.parse(JSON.stringify(account)),price=stock.bars.at(-1).close,current=a.positions[stock.id]||{quantity:0,cost:0},amount=price*quantity,fee=amount*feeBp/10000;
  if(side==='BUY'){if(amount+fee>a.cash+1e-8)throw Error('모의 현금이 부족합니다.');a.cash-=amount+fee;a.positions[stock.id]={quantity:current.quantity+quantity,cost:current.cost+amount+fee};}
  else {if(quantity>current.quantity)throw Error('보유 수량을 초과합니다.');a.cash+=amount-fee;a.realized+=amount-fee-current.cost*quantity/current.quantity;a.positions[stock.id]={quantity:current.quantity-quantity,cost:current.cost*(1-quantity/current.quantity)};}
  a.orders.unshift({id:Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,8),date:stock.bars.at(-1).date,stockId:stock.id,side,quantity,price,fee});a.orders=a.orders.slice(0,500);return a;
 }
 function distribution(input){
  const {profit,loss,reserve,supply,owned,availableCash}=input;
  for(const k of ['profit','loss','reserve','supply','owned','availableCash'])if(!finite(input[k]))throw Error('숫자를 입력하세요.');
  if(loss<0||reserve<0||supply<=0||owned<0||owned>supply||availableCash<0)throw Error('결손·적립·현금·보유량을 확인하세요.');
  const eligible=Math.max(0,profit-loss-reserve),payout=eligible*.2;
  return {eligible,payout,retained:eligible*.8,mine:payout*owned/supply,cashShortage:Math.max(0,payout-availableCash)};
 }
 function sample(){
  let seed=76543;const random=()=>{seed=(seed*16807)%2147483647;return seed/2147483647;};
  const dates=[];for(let d=new Date('2025-01-02T00:00:00Z');d<=new Date('2026-10-02T00:00:00Z');d.setUTCDate(d.getUTCDate()+1))if(![0,6].includes(d.getUTCDay()))dates.push(d.toISOString().slice(0,10));
  const names=['아스터 로보틱스','그린셀 에너지','노바 컴퓨팅','오션 헬스','루멘 반도체','테라 인프라','포레스트 소재','오로라 의료','브릿지 자동화','코어 클라우드'];
  const stocks=[];
  for(const market of ['KR','US'])for(let j=0;j<10;j++){
   const id=market+'-SIM'+String(j+1).padStart(2,'0'),currency=market==='KR'?'KRW':'USD';let price=(market==='KR'?15000:30)*(1+j*.14),bars=[];
   for(let i=0;i<dates.length;i++){
    const open=price*(1+(random()-.5)*.006),recent=i>=dates.length-25;
    const close=open*(1+(recent&&j%3===0?(random()-.5)*.003:(random()-.49)*.026));
    const high=Math.max(open,close)*(1+random()*.009),low=Math.min(open,close)*(1-random()*.009),volume=Math.round((100000+j*30000)*(.7+random()*.6)*(i>=dates.length-5&&j%3===0?2.8:1));
    bars.push({date:dates[i],open:+open.toFixed(4),high:+high.toFixed(4),low:+low.toFixed(4),close:+close.toFixed(4),volume});price=close;
   }
   const snapshots=[],shares=market==='KR'?10000000:20000000;
   const periods=[['2024-09-30','2024-11-14'],['2024-12-31','2025-03-20'],['2025-03-31','2025-05-15'],['2025-06-30','2025-08-14'],['2025-09-30','2025-11-14'],['2025-12-31','2026-03-20'],['2026-03-31','2026-05-15'],['2026-06-30','2026-08-14']];
   for(let k=0;k<periods.length;k++){
    const cap=bars[0].close*shares,revenue=cap*(.6+j*.11)*(1+k*.035),margin=.09+j*.016,op=revenue*margin,net=op*.72;
    snapshots.push({periodEnd:periods[k][0],filedAt:periods[k][1],availableAt:periods[k][1],version:id+'-'+k,revenue,operatingIncome:op,netIncome:j===8?-net:net,equity:cap*(.55+j*.08),cfo:op*(.8+j*.045),capex:op*.3,shares,debt:op*(1+j*.25),cash:op*.8,interest:op*.06,investedCapital:cap*.55,taxRate:.24,previousRevenue:revenue/(1.06+j*.017),previousOperatingIncome:op/(1.09+j*.027),previousMargin:margin-.008,dilution:j===7?.08:.008});
   }
   stocks.push({id,name:names[j]+(market==='US'?' US':''),market,currency,sector:['테크놀로지','산업·헬스'][j%2],financialSector:false,bars,snapshots,flags:j===6?[{date:'2026-09-30',type:'event',note:'합성 예제: 일회성 이벤트'}]:[]});
  }
  return {schemaVersion:1,source:'ATLAS 합성 예제 · 실제 기업·시세 아님',synthetic:true,priceBasis:'split-consistent',stocks};
 }
 function validateAccount(a,currency,ids){
  if(!a||a.currency!==currency||!finite(a.cash)||a.cash<0||!finite(a.realized)||!finite(a.initial)||a.initial<=0||!a.positions||typeof a.positions!=='object'||Array.isArray(a.positions)||!Array.isArray(a.orders)||a.orders.length>500)throw Error('모의 계좌 백업이 잘못됐습니다.');
  for(const [id,p] of Object.entries(a.positions))if(!ids.has(id)||!p||!Number.isInteger(p.quantity)||p.quantity<0||!finite(p.cost)||p.cost<0)throw Error('보유 종목 백업이 잘못됐습니다.');
  for(const o of a.orders)if(!o||!date(o.date)||!ids.has(o.stockId)||!['BUY','SELL'].includes(o.side)||!Number.isInteger(o.quantity)||o.quantity<=0||!finite(o.price)||o.price<=0||!finite(o.fee)||o.fee<0||typeof o.id!=='string')throw Error('주문 백업이 잘못됐습니다.');
  return a;
 }
 return {VERSION,defaults,financialFields,date,validate,config,snapshot,flow,technical,screen,backtest,paperOrder,distribution,sample,validateAccount};
});
