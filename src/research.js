(function(root,factory){
 const api=factory(typeof module==='object'&&module.exports?require('./engine.js'):root.Quant);
 if(typeof module==='object'&&module.exports)module.exports=api;else root.AtlasTop10=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(Q){
 'use strict';
 const VERSION='1.5.0',strategies=['value','legacy_technical','alpha_filters'];
 const labels={value:'저평가',legacy_technical:'기존 보조지표',alpha_filters:'알파스퀘어 근사 전략'};
 const defaults={pullbackPct:.03,turnoverRatio:2,rsiRecovery:30,minPeers:5,dividendYield:.02,maxFinancialAgeDays:200};
 const finite=Number.isFinite,mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
 const age=(a,b)=>(Date.parse(a)-Date.parse(b))/86400000;
 function gate(stock,meta,asOf){
  const date=meta.expectedMarketDate;
  if(!Q.date(date)||date>asOf)return '완료 거래일 미확인';
  const entry=(meta.entryMap||{})[stock.id];
  if(!entry)return '거래상태 미확인';
  if(!Q.date(entry.statusAsOf)||entry.statusAsOf<(meta.asOf||date)||entry.statusAsOf>asOf)return '거래상태 시점 미확인';
  if(entry.status!=='active')return '거래 제한: '+entry.status;
  if(entry.securityType!=='Common Stock'||stock.financialSector||/reit|insurance|bank|financial/i.test(stock.sector))return '상품·업종 별도 모델 필요';
  if(!entry.source)return '거래상태 출처 미확인';
  if(stock.bars.filter(b=>b.date<=date).at(-1)?.date!==date)return '완료 거래일 가격 누락';
  if(stock.bars.filter(b=>b.date<=date).length<80)return '완료 일봉 80개 미만';
  if((stock.dataIssues||[]).some(x=>/분할|가격|일봉|OHLCV/.test(x)))return '가격·기업행동 검증 보류';
  if((stock.flags||[]).some(f=>f.date<=asOf&&['halt','accounting','delisted'].includes(f.type)))return '거래·회계 제한 플래그';
  return null;
 }
 function risk(row,date){
  const bars=row.stock.bars.filter(b=>b.date<=date).slice(-252);
  let peak=0,mdd=0;for(const b of bars){peak=Math.max(peak,b.close);mdd=Math.min(mdd,b.close/peak-1);}
  const atr=row.tech.metrics.atrPct,debt=row.metrics.debtCashFlow,cover=row.metrics.interestCover;
  const values={atr_pct:atr,max_drawdown:mdd,observed_bars:bars.length,debt_cfo:debt,interest_cover:cover,average_turnover:row.flow.tradedValue};
  if(![atr,debt,cover,row.flow.tradedValue].every(finite))return {risk_level:'평가불가',risk_reasons:['위험 평가에 필요한 재무·가격 자료 부족'],risk_metrics:values};
  const reasons=[];
  if(atr>.06)reasons.push('ATR/종가 6% 초과');if(mdd<-.4)reasons.push('252일 내 최대낙폭 40% 초과');
  if(debt>8||cover<2)reasons.push('재무부담 높음');
  if(row.warnings.includes('최근 이벤트 확인'))reasons.push('최근 이벤트 확인');
  let level=reasons.length?'높음':atr>.03||mdd<-.2||debt>4?'보통':'낮음';
  if(level==='보통')reasons.push('ATR 3%·낙폭 20%·부채/CFO 4배 중 경계 초과');
  return {risk_level:level,risk_reasons:reasons,risk_metrics:values};
 }
 function alpha(row,peers,date,c){
  const s=row.stock,a=s.bars.filter(b=>b.date<=date),close=a.map(b=>b.close),last=a.at(-1),prev=a.at(-2),t=row.tech.metrics;
  const sma=(n,offset=0)=>close.length>=n+offset?mean(close.slice(close.length-n-offset,close.length-offset)):null;
  const volumeMean=mean(a.slice(-21,-1).map(b=>b.volume)),vol=volumeMean>0?last.volume/volumeMean:null;
  // No exact exchange turnover is implied by close * volume.
  const turnover=b=>b.turnover??b.close*b.volume;
  const turnBase=mean(a.slice(-21,-1).map(turnover)),turn=turnBase>0?turnover(last)/turnBase:null;
  const previousTech=Q.technical(a.slice(0,-1),prev.date),p=previousTech.metrics;
  const details=[];
  function signal(name,known,matched,observed,rule){details.push({name,status:known?(matched?'matched':'not_matched'):'unavailable',weight:10,feature_name:name,observed_value:observed,rule_threshold:rule,period:'완료 일봉 / 관측 재무',as_of:date,source:s.source||'Twelve Data'});}
  signal('상승 추세 눌림목',finite(sma(60,20)),sma(20)>sma(60)&&sma(60)>sma(60,20)&&Math.abs(last.close/sma(20)-1)<=c.pullbackPct&&last.close/prev.close>=.95,{sma20:sma(20),sma60:sma(60),distance:last.close/sma(20)-1},'SMA20>SMA60, SMA60 상승, ±'+c.pullbackPct*100+'%, 당일 -5% 이상');
  const high=a.length>=253?Math.max(...close.slice(-253,-1)):null;
  signal('신고가 돌파 모멘텀',finite(high)&&finite(vol),last.close>high&&vol>1,{prior_252_high:high,close:last.close,volume_ratio:vol},'직전252일 최고종가 돌파, 거래량>20일평균');
  signal('정배열 추세 지속',finite(sma(120)),sma(5)>sma(20)&&sma(20)>sma(60)&&sma(60)>sma(120)&&sma(20)>sma(20,1),{sma5:sma(5),sma20:sma(20),sma60:sma(60),sma120:sma(120)},'5>20>60>120, SMA20 상승');
  signal('골든크로스',finite(vol),sma(5,1)<=sma(20,1)&&sma(5)>sma(20)&&last.close>sma(20)&&vol>=1,{previous5:sma(5,1),previous20:sma(20,1),sma5:sma(5),sma20:sma(20),volume_ratio:vol},'SMA5 상향교차 SMA20, 종가>SMA20, 거래량>=평균');
  signal('거래대금 급증',finite(turn),turn>=c.turnoverRatio&&last.close>prev.close,{turnover_ratio:turn,proxy:!finite(last.turnover)},'거래대금(미제공시 종가×거래량 근사) >= '+c.turnoverRatio+'배, 상승');
  signal('단기 상승 모멘텀',finite(vol),last.close>close.at(-6)&&last.close>prev.close&&vol>1,{return5:last.close/close.at(-6)-1,volume_ratio:vol},'5일 수익률>0, 당일상승, 거래량>평균');
  signal('RSI 과매도 반등',finite(p.rsi),p.rsi<=c.rsiRecovery&&t.rsi>c.rsiRecovery&&last.close>prev.close,{previous:p.rsi,current:t.rsi},'Wilder RSI14 '+c.rsiRecovery+' 상향돌파, 종가 회복');
  signal('MACD 추세 전환',finite(p.hist),p.hist<=0&&t.hist>0&&last.close>sma(20),{previous_hist:p.hist,hist:t.hist},'MACD12/26/9 상향교차, 종가>SMA20');
  const valuePeers=peers._sectorPeers?.get(s.sector)||peers.filter(r=>r.stock.sector===s.sector&&r.eligible&&r.coverage===1);
  const median=k=>{if(valuePeers._medians&&k in valuePeers._medians)return valuePeers._medians[k];const v=valuePeers.map(r=>r.metrics[k]).filter(finite).sort((a,b)=>a-b);return v.length? v.length%2?v[(v.length-1)/2]:(v[v.length/2-1]+v[v.length/2])/2:null;};
  const financial= row.eligible&&row.coverage===1&&row.f&&age(date,row.f.periodEnd)<=c.maxFinancialAgeDays;
  const valueKnown=financial&&valuePeers.length>=c.minPeers;
  signal('저평가 우량주',valueKnown,row.metrics.per<median('per')&&row.metrics.pbr<median('pbr')&&row.metrics.roe>.1&&row.metrics.fcf>0,{per:row.metrics.per,pbr:row.metrics.pbr,peer_per:median('per'),peer_pbr:median('pbr'),roe:row.metrics.roe,fcf:row.metrics.fcf},'업종 표본≥'+c.minPeers+', PER/PBR 업종중앙값 미만, ROE>10%, FCF>0');
  const d=s.dividend;
  const dividendKnown=!!(financial&&d&&d.confirmed===true&&Q.date(d.availableAt)&&d.availableAt<=row.asOf&&Q.date(d.asOf)&&d.asOf===date&&finite(d.yield)&&d.yield>=0&&d.yield<=1&&Number.isInteger(d.yearsPaid)&&d.yearsPaid>=0&&finite(d.payoutRatio)&&d.source);
  signal('배당주',dividendKnown,dividendKnown&&d.yield>=c.dividendYield&&d.yearsPaid>=3&&d.payoutRatio>0&&d.payoutRatio<=1&&row.metrics.fcf>0,d||null,'확정배당 수익률≥'+c.dividendYield*100+'%, 3년지속, 지급률0~100%, FCF>0');
  const matched=details.filter(d=>d.status==='matched').length,unknown=details.filter(d=>d.status==='unavailable').length;
  return {score:matched*10,score_upper_bound:(matched+unknown)*10,unknown_count:unknown,matched_count:matched,signal_details:details};
 }
 function generate(data,asOf,config={},alphaConfig={}){
  Q.validate(data);if(!Q.date(asOf))throw Error('Invalid analysis date');
  const c={...defaults,...alphaConfig};
  for(const k of Object.keys(defaults))if(!finite(c[k])||c[k]<=0)throw Error('Invalid alpha setting: '+k);
  if(c.pullbackPct>1||c.rsiRecovery>100||c.dividendYield>1||!Number.isInteger(c.minPeers))throw Error('Alpha setting out of range');
  const lists=[],legacy=[];
  for(const market of ['KR','US']){
   const meta=data.universe?.[market]||{},entries=meta.entries||[],entryMap=Object.fromEntries(entries.map(e=>[e.id,e]));
   const m={...meta,entryMap},date=meta.expectedMarketDate||data.stocks.filter(s=>s.market===market).map(s=>s.bars.at(-1)?.date).filter(Boolean).sort().at(-1)||null;
   const reasons={},excluded={},countReason=x=>{reasons[x]=(reasons[x]||0)+1;};
   for(const e of entries){if(e.status!=='active'||e.securityType!=='Common Stock'){const k=e.status!=='active'?e.status:e.securityType;excluded[k]=(excluded[k]||0)+1;}}
   const target=data.stocks.filter(s=>s.market===market),accepted=[];
   for(const s of target){const reason=gate(s,{...m,expectedMarketDate:date},asOf);if(reason)countReason(reason);else accepted.push(s);}
   const eligibleEntries=entries.filter(e=>e.status==='active'&&e.securityType==='Common Stock');
   const denomin=entries.length?eligibleEntries.length:target.length;
   const calculated=accepted.length?Q.screen({...data,stocks:accepted},market,asOf,config,date):[];
   for(const r of calculated)r.asOf=asOf;
   legacy.push(...Q.screen(data,market,asOf,config,date||asOf));
   const candidates=calculated.filter(r=>r.tech.ready&&r.flow.tradedValue>=(market==='KR'?Q.config(config).minTurnoverKR:Q.config(config).minTurnoverUS));
   const missing=Math.max(0,denomin-accepted.length);if(missing)reasons['유니버스 대비 미수집·공통평가 보류']=missing;
   const fundamental=r=>r.eligible&&r.coverage===1&&age(asOf,r.f.periodEnd)<=c.maxFinancialAgeDays;
   candidates._sectorPeers=new Map();
   for(const r of candidates.filter(r=>r.eligible&&r.coverage===1)){const k=r.stock.sector;if(!candidates._sectorPeers.has(k))candidates._sectorPeers.set(k,[]);candidates._sectorPeers.get(k).push(r);}
   for(const peers of candidates._sectorPeers.values()){peers._medians={};for(const k of ['per','pbr']){const v=peers.map(r=>r.metrics[k]).filter(finite).sort((a,b)=>a-b);peers._medians[k]=v.length?v.length%2?v[(v.length-1)/2]:(v[v.length/2-1]+v[v.length/2])/2:null;}}
   const alphaMap=new Map(candidates.map(r=>[r.stock.id,alpha(r,candidates,date,c)]));
   for(const strategy of strategies){
    const evaluate=r=>strategy==='value'?fundamental(r):strategy==='alpha_filters'?alphaMap.get(r.stock.id).unknown_count===0:true;
    const evaluated=candidates.filter(evaluate).length;
    const selectable=candidates.filter(r=>strategy==='value'?fundamental(r):strategy==='alpha_filters'?alphaMap.get(r.stock.id).matched_count>0:true);
    const score=r=>strategy==='value'?r.fundamental/70*100:strategy==='legacy_technical'?r.technical/30*100:alphaMap.get(r.stock.id).score;
    const coverage=denomin?evaluated/denomin:0;
    const scopeFresh=meta.complete===true&&Q.date(meta.asOf)&&meta.asOf>=date&&meta.asOf===asOf&&age(asOf,date)<=7;
    const verified=!data.synthetic&&scopeFresh&&coverage===1&&Object.keys(reasons).length===0&&!!meta.source&&!!meta.calendarSource&&data.priceAdjustmentPolicy==='corporate-actions-verified';
    selectable.sort((a,b)=>score(b)-score(a)||b.coverage-a.coverage||b.flow.tradedValue-a.flow.tradedValue||a.tech.metrics.atrPct-b.tech.metrics.atrPct||a.stock.id.localeCompare(b.stock.id));
    const rows=selectable.slice(0,10).map((r,i)=>{
     const al=alphaMap.get(r.stock.id),knownFundamental=fundamental(r);
     const evidence=(name,value,rule)=>({feature_name:name,observed_value:value,rule_threshold:rule,period:r.f?.periodEnd,as_of:date,source:data.source});
     const details=strategy==='alpha_filters'?al.signal_details:strategy==='value'?[evidence('기업70',r.fundamental,'기업점수 내림차순'),evidence('가치·수익성·안정·성장',{value:r.value,quality:r.quality,safety:r.safety,growth:r.growth},'가중치20/20/20/10'),evidence('PER/PBR/ROE/FCF',{per:r.metrics.per,pbr:r.metrics.pbr,roe:r.metrics.roe,fcf:r.metrics.fcf},r.peerBasis),evidence('이자보상·부채/CFO',{interest_cover:r.metrics.interestCover,debt_cfo:r.metrics.debtCashFlow},'이자보상≥2, 부채/CFO≤8')]:[evidence('기술30',r.technical,'거래량10·추세8·모멘텀6·변동성6'),evidence('기술 배점',r.tech.parts,'세부 배점 합계'),evidence('RSI/MACD/ATR',r.tech.metrics,'Wilder RSI14, MACD12/26/9, ATR14'),evidence('거래량 배수',r.flow.ratio,'과거20일 대비 최근5일')];
     return {rank:i+1,id:r.stock.id,name:r.stock.name,symbol:r.stock.symbol||r.stock.id,exchange:r.stock.mic||entryMap[r.stock.id]?.mic,market,score:score(r),score_scale:100,fundamental_70:knownFundamental?r.fundamental:null,technical_30:r.technical,total_100:knownFundamental?r.total:null,signal_details:details,...risk(r,date),data_as_of:date,financial_available_at:r.f?.availableAt,source:data.source,score_meaning:strategy==='alpha_filters'&&al.unknown_count?'확인된 신호의 하한 점수 · 판별불가 신호 별도':'관측자료 점수',...(strategy==='alpha_filters'?{score_upper_bound:al.score_upper_bound,unknown_signal_count:al.unknown_count}:{}),warnings:[...r.warnings,...(strategy==='alpha_filters'&&al.matched_count>1?['가격 이벤트 신호 중복·상관 위험']:[])]};
    });
    lists.push({market,strategy,label:labels[strategy],status:rows.length?(verified?'verified':'partial'):'unavailable',title:verified?'전체시장 TOP 10':'조회 성공 표본 TOP 10 (전체시장 순위 아님)',as_of_market_close:date,generated_at:data.collectedAt||asOf,universe_count:entries.length||target.length,eligible_count:denomin,prices_covered_count:accepted.length,fundamentals_covered_count:candidates.filter(fundamental).length,fully_scored_count:evaluated,coverage_rate:coverage,exclude_reasons:reasons,excluded_count_by_reason:excluded,algorithm_version:VERSION,engine_version:Q.VERSION,source_provenance:[data.source,meta.source].filter(Boolean),source_snapshots:{universe_as_of:meta.asOf||null,calendar_source:meta.calendarSource||null,price_adjustment_policy:data.priceAdjustmentPolicy||'split-consistent-only',status_sources:[...new Set(entries.map(e=>e.source).filter(Boolean))]},is_full_market_ranking:verified,synthetic:data.synthetic,config:c,data_quality_notes:[...(!meta.complete?['전체 유니버스 미확보']:[]),...(data.priceAdjustmentPolicy!=='corporate-actions-verified'?['기업행동 전체 보정 검증 미완료']:[]),...(meta.asOf!==asOf?['분석일 기준 거래상태 미갱신']:[]),...(data.synthetic?['합성 검증자료']:[])],shortfall_reason:rows.length<10?'10종목 미충족 · 조건 또는 자료 부족':null,rows});
   }
  }
  return {algorithmVersion:VERSION,engineVersion:Q.VERSION,asOf,rankings:lists,legacy};
 }
 return {VERSION,strategies,defaults,generate,alpha,risk};
});
