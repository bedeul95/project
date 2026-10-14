const test=require('node:test');
const assert=require('node:assert/strict');
const Q=require('../src/engine.js');
const clone=x=>JSON.parse(JSON.stringify(x));
const sample=Q.sample();
test('예제·숫자·OHLC 범위·중복·잘못된 달력 날짜 검증',()=>{
 assert.equal(Q.validate(clone(sample)).stocks.length,20);
 for(const change of [d=>d.stocks[0].bars[0].close=NaN,d=>d.stocks[0].bars[0].low=1e9,d=>d.stocks[0].bars[1].date=d.stocks[0].bars[0].date,d=>d.stocks[0].bars[0].date='2025-02-30',d=>d.stocks[0].snapshots[0].availableAt='2024-01-01',d=>d.stocks[0].id='__proto__']){
  const d=clone(sample);change(d);assert.throws(()=>Q.validate(d));
 }
});
test('스냅샷은 당시 사용 가능 자료만 선택하고 나중 정정 버전을 보존',()=>{
 const s=clone(sample.stocks[0]),f=s.snapshots[0];
 s.snapshots.push({...f,version:'restated',availableAt:'2025-04-01',filedAt:'2025-04-01',netIncome:1});
 assert.equal(Q.snapshot(s,'2024-11-13'),null);
 assert.equal(Q.snapshot(s,'2025-01-02').version,f.version);
 // A later correction of an older period does not replace a newer fiscal period.
 assert.equal(Q.snapshot(s,'2025-04-02').periodEnd,'2024-12-31');
 const single={snapshots:[f,{...f,version:'correction',filedAt:'2025-02-01',availableAt:'2025-02-03'}]};
 assert.equal(Q.snapshot(single,'2025-02-02').version,f.version);
 assert.equal(Q.snapshot(single,'2025-02-03').version,'correction');
});
test('가격 순변화가 0이어도 큰 기간 범위면 횡보 신호에서 제외',()=>{
 const bars=clone(sample.stocks[0].bars.slice(-25));for(const b of bars){b.open=b.close=100;b.low=99;b.high=101;b.volume=100;}
 for(const b of bars.slice(-5))b.volume=300;
 const c=Q.config();assert.equal(Q.flow(bars,bars.at(-1).date,c).active,true);
 bars.at(-6).high=125;assert.equal(Q.flow(bars,bars.at(-1).date,c).active,false);
});
test('필수 재무 누락·적자·금융업·플래그는 고점수라도 투자 후보에서 제외',()=>{
 const d=clone(sample),date='2026-10-02';
 d.stocks[0].snapshots.at(-1).cfo=null;
 d.stocks[1].financialSector=true;
 d.stocks[2].flags=[{date:'2026-10-01',type:'accounting',note:'test'}];
 const r=Q.screen(Q.validate(d),'KR',date,{minScore:0});
 for(const id of ['KR-SIM01','KR-SIM02','KR-SIM03','KR-SIM09'])assert.equal(r.find(x=>x.stock.id===id).candidate,false);
 assert.equal(r.find(x=>x.stock.id==='KR-SIM07').candidate,false,'최근 이벤트는 신규 후보에서 제외');
});
test('이후 가격·재무 변경은 과거 평가·백테스트 곡선에 영향을 주지 않음',()=>{
 const a=clone(sample),b=clone(sample),cutoff='2026-01-30';
 for(const s of b.stocks){for(const bar of s.bars)if(bar.date>cutoff)for(const k of ['open','high','low','close'])bar[k]*=7;
 for(const f of s.snapshots)if(f.availableAt>cutoff){f.netIncome*=12;f.cfo*=10;}}
 const ra=Q.backtest(a,'KR'),rb=Q.backtest(b,'KR');
 assert.deepEqual(ra.curve.filter(x=>x.date<=cutoff),rb.curve.filter(x=>x.date<=cutoff));
 assert.deepEqual(Q.screen(a,'KR',cutoff).map(x=>[x.stock.id,x.total]),Q.screen(b,'KR',cutoff).map(x=>[x.stock.id,x.total]));
});
test('체결 비용은 실제 체결금액에 반영되고 현금·수량 한도를 지킴',()=>{
 const d=clone(sample);d.stocks=d.stocks.filter(s=>s.market==='KR').slice(0,1);
 for(const b of d.stocks[0].bars){b.open=b.close=10;b.low=9.9;b.high=10.1;}
 const r=Q.backtest(d,'KR',{capital:1000,minScore:0,topN:1,maxWeight:100,feeBp:100,rebalance:100,minFundamental:0,minTechnical:0,minTurnoverKR:0});
 assert.equal(r.trades[0].quantity,99);assert.equal(r.trades[0].fee,9.9);
 assert.ok(Math.abs(r.curve[0].nav-990.1)<1e-8);assert.ok(r.cash>=-1e-8);
 for(const t of r.trades){assert.ok(t.signalDate<t.date);assert.ok(Number.isInteger(t.quantity));}
});
test('서로 다른 거래일 배열은 임의 보간 없이 백테스트 거부',()=>{
 const d=clone(sample);d.stocks[0].bars.splice(30,1);assert.throws(()=>Q.backtest(d,'KR'),/동일한 거래일/);
});
test('모의 주문은 실제 비용·원가·실현손익과 매도 한도를 지킴',()=>{
 const s=clone(sample.stocks[0]);s.bars.at(-1).close=100;
 const original={currency:'KRW',cash:1000,initial:1000,realized:0,positions:{},orders:[]};
 const buy=Q.paperOrder(original,s,'BUY',3,100);
 assert.equal(original.cash,1000);assert.equal(buy.cash,697);assert.equal(buy.positions[s.id].cost,303);
 s.bars.at(-1).close=110;
 const sell=Q.paperOrder(buy,s,'SELL',2,100);
 assert.ok(Math.abs(sell.cash-914.8)<1e-8);assert.ok(Math.abs(sell.realized-15.8)<1e-8);assert.ok(Math.abs(sell.positions[s.id].cost-101)<1e-8);
 assert.throws(()=>Q.paperOrder(sell,s,'SELL',2));assert.throws(()=>Q.paperOrder(sell,s,'BUY',100));assert.throws(()=>Q.paperOrder(sell,s,'BUY',1.5));
 Q.validateAccount(sell,'KRW',new Set([s.id]));
});
test('분배는 결손·적립액을 반영하고 지급 현금 부족을 별도 계산',()=>{
 const d=Q.distribution({profit:100,loss:20,reserve:10,supply:1000,owned:10,availableCash:5});
 assert.deepEqual(d,{eligible:70,payout:14,retained:56,mine:.14,cashShortage:9});
 assert.equal(Q.distribution({profit:-10,loss:0,reserve:0,supply:1,owned:1,availableCash:0}).payout,0);
 assert.throws(()=>Q.distribution({profit:10,loss:0,reserve:0,supply:1,owned:2,availableCash:0}));
});
test('설정 가중치·수량·비용 범위를 검증',()=>{
 assert.throws(()=>Q.config({qualityWeight:90}));assert.throws(()=>Q.config({topN:2.5}));assert.throws(()=>Q.config({feeBp:900}));
});
test('70/30 구조와 세부 기술 배점은 상한을 지키고 합계와 일치',()=>{
 for(const r of Q.screen(sample,'KR','2026-10-02')){
  assert.ok(r.fundamental>=0&&r.fundamental<=70);
  assert.ok(r.technical>=0&&r.technical<=30);
  assert.ok(Math.abs(r.total-r.fundamental-r.technical)<1e-8);
  for(const [key,cap] of Object.entries({volume:10,trend:8,momentum:6,volatility:6}))assert.ok(r.tech.parts[key]>=0&&r.tech.parts[key]<=cap+1e-10);
 }
 assert.throws(()=>Q.config({safetyWeight:30}),/70/);
});
test('일정 가격 RSI=50, Wilder ATR=2%, MACD=0을 계산하고 80일 전은 보류',()=>{
 const bars=clone(sample.stocks[0].bars.slice(0,80));for(const b of bars){b.open=b.close=100;b.low=99;b.high=101;b.volume=100;}
 const t=Q.technical(bars,bars.at(-1).date);
 assert.equal(t.metrics.rsi,50);assert.equal(t.metrics.atr,2);assert.equal(t.metrics.atrPct,.02);assert.equal(t.metrics.hist,0);assert.equal(t.metrics.bbPosition,.5);assert.equal(t.total,21);
 assert.equal(Q.technical(bars,bars.at(-2).date).ready,false);
});
test('재무가 좋아도 과열 기술 조건·낮은 현금흐름·거래대금은 후보를 막음',()=>{
 const d=clone(sample);for(const s of d.stocks.filter(x=>x.market==='KR')){s.snapshots.at(-1).cfo=s.snapshots.at(-1).operatingIncome*2;for(let i=0;i<s.bars.length;i++){const v=10000*Math.pow(1.01,i);s.bars[i]={...s.bars[i],open:v,close:v,high:v*1.001,low:v*.999};}}
 const r=Q.screen(Q.validate(d),'KR','2026-10-02',{minScore:0,minFundamental:0,minTechnical:0,minTurnoverKR:0});
 assert.ok(r.every(x=>!x.candidate));assert.ok(r.every(x=>x.entryReasons.some(y=>y.includes('RSI'))));
 const noCash=clone(sample);noCash.stocks[0].snapshots.at(-1).cfo=-1;
 assert.equal(Q.screen(noCash,'KR','2026-10-02',{minScore:0,minFundamental:0,minTechnical:0}).find(x=>x.stock.id==='KR-SIM01').eligible,false);
 assert.ok(Q.screen(sample,'KR','2026-10-02',{minTurnoverKR:1e15}).every(x=>!x.eligible));
});
test('ATR 포함 실제 가격 갭을 계산하고 기술도 이후 자료를 참조하지 않음',()=>{
 const bars=clone(sample.stocks[0].bars.slice(0,100)),date=bars[79].date;
 const t=Q.technical(bars,date);for(const b of bars.slice(80)){b.close*=5;b.high*=5;b.low*=5;b.open*=5;}
 assert.deepEqual(Q.technical(bars,date),t);
 const a=clone(sample.stocks[0].bars.slice(0,80));for(const b of a){b.open=b.close=100;b.high=101;b.low=99;}
 a.at(-1).open=a.at(-1).close=130;a.at(-1).high=131;a.at(-1).low=129;
 assert.ok(Math.abs(Q.technical(a,a.at(-1).date).metrics.atr-(2*13+31)/14)<1e-8);
});
test('관측일 API 자료는 과거 백테스트 차단, 데이터 문제는 고점수여도 제외',()=>{
 const d=Q.sample();d.pitPolicy='observed-only';assert.throws(()=>Q.backtest(d,'KR',{start:'2025-06-02',end:'2026-10-02',capital:1000000}),/관측일/);
 d.stocks[0].dataIssues=['응답 종목 기준 확인 실패'];const r=Q.screen(d,'KR','2026-10-02').find(x=>x.stock.id===d.stocks[0].id);assert.equal(r.eligible,false);assert.ok(r.reasons.includes('응답 종목 기준 확인 실패'));
});
