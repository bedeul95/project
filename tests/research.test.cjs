const test=require('node:test'),assert=require('node:assert/strict');
const Q=require('../src/engine.js'),R=require('../src/research.js');
const {fixture}=require('./fixtures/research.cjs');
test('six independent lists, capped ten, scales and reproducible ordering',()=>{
 const data=fixture(),lists=R.generate(data,'2026-10-02').rankings;
 assert.equal(lists.length,6);assert.ok(lists.every(r=>r.rows.length===10));
 for(const list of lists){assert.ok(list.rows.every(r=>r.score>=0&&r.score<=100));assert.equal(list.status,'verified');assert.equal(list.coverage_rate,1);assert.equal(list.fully_scored_count,15);for(const row of list.rows){if(list.strategy==='value')assert.equal(row.score,row.fundamental_70/70*100);if(list.strategy==='legacy_technical')assert.equal(row.score,row.technical_30/30*100);assert.ok(row.signal_details.every(d=>d.as_of==='2026-10-02'));}}
 const shuffled=structuredClone(data);shuffled.stocks.reverse();assert.deepEqual(R.generate(shuffled,'2026-10-02').rankings,lists);
 assert.ok(lists[0].rows.some(r=>lists[1].rows.some(t=>t.id===r.id)));
});
test('halt/managed/delisted/unknown and stale status never enter any list',()=>{
 const data=fixture();['halt','managed','delisted','unknown','noncompliant'].forEach((status,i)=>{data.universe.KR.entries[i].status=status;});
 data.universe.KR.entries[5].statusAsOf='2026-10-01';
 const lists=R.generate(data,'2026-10-02').rankings.filter(r=>r.market==='KR');
 for(const list of lists){assert.ok(list.rows.every(r=>!['KR-0','KR-1','KR-2','KR-3','KR-4','KR-5'].includes(r.id)));assert.equal(list.is_full_market_ranking,false);assert.equal(list.excluded_count_by_reason.halt,1);}
});
test('incomplete universe/collection and synthetic datasets cannot be full-market',()=>{
 for(const change of [d=>{d.synthetic=true;},d=>{d.universe.KR.complete=false;},d=>{d.stocks.splice(0,1);},d=>{delete d.priceAdjustmentPolicy;},d=>{d.universe.KR.asOf='2026-10-01';}]){
  const d=fixture();change(d);const list=R.generate(d,'2026-10-02').rankings[0];assert.notEqual(list.status,'verified');assert.equal(list.is_full_market_ranking,false);
 }
 const d=fixture();delete d.universe;assert.ok(R.generate(d,'2026-10-02').rankings.every(r=>r.status==='unavailable'));
});
test('missing alpha history/dividend is unavailable, scores are lower bounds',()=>{
 const data=fixture();for(const s of data.stocks){s.bars=s.bars.slice(-120);delete s.dividend;}
 const list=R.generate(data,'2026-10-02').rankings.find(x=>x.market==='KR'&&x.strategy==='alpha_filters');
 const row=list.rows[0];assert.ok(row);assert.equal(row.unknown_signal_count,2);assert.equal(row.score_upper_bound,row.score+20);assert.equal(row.signal_details.find(s=>s.name==='신고가 돌파 모멘텀').status,'unavailable');assert.equal(row.signal_details.find(s=>s.name==='배당주').status,'unavailable');assert.equal(list.status,'partial');
});
test('US completed price date is separate from KST financial observation date',()=>{
 const data=fixture(),asOf='2026-10-03';
 for(const meta of Object.values(data.universe)){meta.asOf=asOf;for(const e of meta.entries)e.statusAsOf=asOf;}
 const stock=data.stocks.find(s=>s.market==='US');for(const f of stock.snapshots){f.availableAt=asOf;f.filedAt=asOf;}
 const list=R.generate(data,asOf).rankings.find(r=>r.market==='US'&&r.strategy==='value');
 assert.ok(list.rows.some(r=>r.id===stock.id));assert.equal(list.as_of_market_close,'2026-10-02');assert.ok(list.rows.every(r=>r.data_as_of==='2026-10-02'));
});
test('Wilder RSI and MACD reversal are actual crossings; future data is ignored',()=>{
 const d=fixture(),row=Q.screen(d,'KR','2026-10-02')[0];row.asOf='2026-10-02';
 const result=R.alpha(row,[row],'2026-10-02',R.defaults);
 assert.equal(result.signal_details.find(x=>x.name==='RSI 과매도 반등').status,'not_matched');assert.equal(result.signal_details.find(x=>x.name==='MACD 추세 전환').status,'not_matched');
 const changed=structuredClone(row);changed.stock.bars.push({date:'2026-10-05',open:1,close:1,low:1,high:1,volume:1});
 assert.deepEqual(R.alpha(changed,[changed],'2026-10-02',R.defaults),result);
});
test('missing fundamental is null in technical list, never a fabricated zero',()=>{
 const d=fixture();for(const f of d.stocks[0].snapshots)f.cfo=null;
 const lists=R.generate(d,'2026-10-02').rankings;
 assert.ok(!lists[0].rows.some(r=>r.id==='KR-0'));const r=lists[1].rows.find(r=>r.id==='KR-0');assert.ok(r);assert.equal(r.fundamental_70,null);assert.equal(r.total_100,null);assert.equal(r.risk_level,'평가불가');
});
