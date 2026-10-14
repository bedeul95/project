const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
function harness(saved){
 const listeners={},items=new Map(),nodes=new Map(),downloads=[];
 function element(id){if(!nodes.has(id))nodes.set(id,{id,innerHTML:'',textContent:'',value:'',files:[],dataset:{},fields:{},selectionStart:0,classList:{add(){},remove(){}},addEventListener(type,fn){listeners[id+':'+type]=fn;},focus(){},setSelectionRange(){},click(){},remove(){},reportValidity(){return true;}});return nodes.get(id);}
 const context={console,window:null,Blob,URL:{createObjectURL(blob){downloads.push(blob);return 'blob:test';},revokeObjectURL(){}},setTimeout:()=>0,clearTimeout(){},confirm:()=>true,localStorage:{getItem:k=>saved??items.get(k)??null,setItem:(k,v)=>items.set(k,v)},document:{getElementById:element,addEventListener:(k,v)=>{const old=listeners[k];listeners[k]=old?event=>{old(event);return v(event);}:v;},createElement:()=>({click(){},remove(){}}),body:{appendChild(){}}},FormData:class{constructor(form){this.fields=form.fields;}get(k){return this.fields[k]??null;}has(k){return Object.hasOwn(this.fields,k);}[Symbol.iterator](){return Object.entries(this.fields)[Symbol.iterator]();}}};
 context.window=context;context.scrollTo=()=>{};vm.createContext(context);
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/engine.js'),'utf8'),context);
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/read-ui.js'),'utf8'),context);
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/app.js'),'utf8'),context);
 const click=(action,extra={})=>listeners.click({target:{closest:()=>({dataset:{action,...extra}})}});
 const submit=(id,fields)=>{const form=element(id);form.fields=fields;listeners.submit({target:form,preventDefault(){}});};
 const html=()=>element('app').innerHTML;
 const state=()=>JSON.parse(items.get('atlas-quant-mac-v1'));
 return {context,element,listeners,click,submit,html,state,downloads};
}
test('모든 화면·관심종목·시장 변경·기업 상세를 렌더링',()=>{
 const h=harness();assert.match(h.html(),/좋은 기업을/);assert.match(h.html(),/합성 예제 데이터/);
 for(const [page,text] of [['research','하루 두 번'],['flow','조용한 가격'],['lab','아이디어를 숫자로'],['portfolio','모의 주문'],['company','지급 가능 현금'],['data','API 연결 현황'],['screen','좋은 기업을']]){h.click('page',{page});assert.ok(h.html().includes(text));}
 h.click('watch',{id:'KR-SIM01'});assert.deepEqual(h.state().watch,['KR-SIM01']);
 h.click('detail',{id:'KR-SIM01'});assert.match(h.html(),/사용 가능일/);assert.match(h.html(),/재무 버전/);
 h.listeners.change({target:{id:'market',value:'US'}});assert.equal(h.state().market,'US');assert.match(h.html(),/미국 · USD/);
});
test('폼 경로로 조건·비중·모의 주문·분배·백테스트를 실행',()=>{
 const h=harness();h.click('page',{page:'flow'});h.submit('flow-form',{volumeRatio:'2',flatReturn:'4',flatRange:'9'});assert.equal(h.state().config.volumeRatio,2);
 h.click('page',{page:'lab'});h.submit('weights-form',{valueWeight:'20',qualityWeight:'25',safetyWeight:'15',growthWeight:'10'});assert.equal(h.state().config.qualityWeight,25);
 h.click('page',{page:'portfolio'});h.submit('paper-form',{stockId:'KR-SIM01',side:'BUY',quantity:'3'});assert.equal(h.state().accounts.KR.positions['KR-SIM01'].quantity,3);
 h.click('page',{page:'company'});h.submit('company-form',{profit:'100',loss:'20',reserve:'10',availableCash:'5',supply:'1000',owned:'10'});assert.equal(h.state().company.availableCash,5);assert.match(h.html(),/현금 부족액/);
 h.click('page',{page:'lab'});h.element('lab-form').fields={start:'2025-03-03',end:'2026-10-02',capital:'1000000',topN:'3',maxWeight:'40',rebalance:'20',minScore:'55',feeBp:'13'};
 h.submit('lab-form',h.element('lab-form').fields);assert.match(h.html(),/자산 추이/);assert.match(h.html(),/최대 낙폭/);
 h.element('lab-form').fields={start:'2025-03-03',end:'2026-10-02',capital:'1000000',topN:'3',maxWeight:'40',rebalance:'20',minScore:'55',feeBp:'13'};h.click('ablation');assert.match(h.html(),/거래량 조건의 추가 효과/);
});
test('가져오기 유효성 실패 시 기존 자료 유지, 문자열은 HTML/CSV 안전 처리',async()=>{
 const h=harness(),d=h.context.Quant.sample();d.stocks[0].name=' <img src=x onerror=alert(1)>';d.stocks[1].name=' =HYPERLINK("bad")';
 const input=h.element('import-file');input.dataset.mode='data';input.files=[{size:1000,text:async()=>JSON.stringify(d)}];await h.listeners['import-file:change']({target:input});
 h.click('page',{page:'screen'});assert.match(h.html(),/&lt;img/);assert.ok(!h.html().includes('<img src=x'));
 const before=JSON.stringify(h.state());input.files=[{size:1000,text:async()=>'{bad'}];await h.listeners['import-file:change']({target:input});assert.equal(JSON.stringify(h.state()),before);
 h.click('export-scores');const csv=await h.downloads.at(-1).text();assert.ok(csv.includes("' =HYPERLINK"));
 h.click('backup');const backup=JSON.parse(await h.downloads.at(-1).text());assert.equal(backup.version,1);
});
test('전체 백업 복원과 손상된 로컬 저장 fallback',async()=>{
 const a=harness();a.click('watch',{id:'KR-SIM01'});a.click('backup');const saved=await a.downloads.at(-1).text();
 const b=harness(saved);assert.match(b.html(),/star on/);
 const c=harness('{broken');assert.match(c.html(),/합성 예제 데이터/);assert.match(c.element('toast').textContent,/예제로 시작/);
});
test('기존 백업을 유지하면서 70/30 설정으로 이관하고 CSV와 상세에 점수 분리',async()=>{
 const a=harness();a.click('watch',{id:'KR-SIM01'});a.click('backup');const old=JSON.parse(await a.downloads.at(-1).text());
 delete old.scoringVersion;old.config.valueWeight=35;old.config.qualityWeight=40;old.config.growthWeight=25;delete old.config.safetyWeight;
 const b=harness(JSON.stringify(old));b.click('backup');const current=JSON.parse(await b.downloads.at(-1).text());
 assert.equal(current.scoringVersion,2);assert.deepEqual(current.watch,['KR-SIM01']);assert.equal(current.config.valueWeight+current.config.qualityWeight+current.config.safetyWeight+current.config.growthWeight,70);
 b.click('export-scores');const csv=await b.downloads.at(-1).text();assert.ok(csv.includes('fundamental70'));assert.ok(csv.includes('technical30'));
 b.click('detail',{id:'KR-SIM01'});assert.ok(b.html().includes('기술적 지표 / 30점'));assert.ok(b.html().includes('RSI14'));assert.ok(b.html().includes('재무 안정성'));
});
test('번들 HTML은 외부 런타임·외부 직접 요청·ES module 없이 실행 가능한 구조',()=>{
 const html=fs.readFileSync(path.join(__dirname,'../시작.html'),'utf8');
 assert.ok(!html.includes('type="module"'));assert.ok(!/<script[^>]*src=/.test(html));assert.ok(!/<link[^>]*rel="stylesheet"/.test(html));assert.match(html,/fetch\('\/api\/read\/\'/);assert.ok(!/fetch\(['"]https?:/.test(html));assert.match(html,/Mac local edition/);
});
test('API 화면은 파일 실행에서 서버 안내, 서버 실행에서 세션을 붙여 상태 조회',async()=>{
 const listeners={},calls=[];let repaints=0;
 const c={window:null,console,URLSearchParams,FormData,confirm:()=>true,document:{addEventListener:(k,v)=>listeners[k]=v},fetch:async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>({ok:true,data:{mode:'demo',authenticated:true}})};}};
 c.window=c;c.AtlasRefresh=()=>repaints++;vm.createContext(c);vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/broker-ui.js'),'utf8'),c);
 assert.match(c.AtlasBroker.page(),/파일로 실행 중/);
 listeners.click({target:{closest:()=>({dataset:{action:'api-status'}})}});await new Promise(resolve=>setImmediate(resolve));assert.equal(calls.length,0);
 c.ATLAS_SESSION='a'.repeat(32);listeners.click({target:{closest:()=>({dataset:{action:'api-status'}})}});await new Promise(resolve=>setImmediate(resolve));
 assert.equal(calls[0].url,'/api/status');assert.equal(calls[0].options.headers['X-Atlas-Session'],c.ATLAS_SESSION);assert.match(c.AtlasBroker.page(),/토큰 인증 확인됨/);assert.ok(repaints>=2);
});
test('조회 설정은 키를 로컬 서버로만 보내고 분석 결과를 기존 화면에 적용',async()=>{
 const h=harness(),calls=[];h.click('watch',{id:'KR-SIM01'});h.context.ATLAS_SESSION='s'.repeat(32);
 const config={scheduled:false,morning:'08:30',evening:'18:30',frequency:2,creditsPerMinute:500,maxCreditsPerRun:1500,maxCreditsPerDay:3000,financialCacheHours:24,symbols:[{market:'US',symbol:'AAPL',mic:'XNAS'}]};
 const latest={data:h.context.Quant.sample(),asOf:'2026-10-06',analysis:{rows:[]},analysisStatus:'완료'};
 h.context.fetch=async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>({ok:true,data:url.endsWith('/latest')?latest:{configured:true,nodeAvailable:true,config,jobs:[]}})};};
 h.click('page',{page:'research'});await new Promise(r=>setImmediate(r));assert.match(h.html(),/조회 설정/);
 h.submit('read-config',{apiKey:'secret-test',scheduled:'on',frequency:'2',morning:'08:30',evening:'18:30',creditsPerMinute:'500',maxCreditsPerRun:'1500',maxCreditsPerDay:'3000',financialCacheHours:'24',symbols:'US,AAPL,XNAS'});
 await new Promise(r=>setImmediate(r));const req=calls.find(x=>x.url.endsWith('/config'));assert.equal(JSON.parse(req.options.body).apiKey,'secret-test');assert.ok(!JSON.stringify(h.state()).includes('secret-test'));
 h.click('read-apply');await new Promise(r=>setImmediate(r));assert.equal(h.state().asOf,'2026-10-06');assert.match(h.html(),/좋은 기업을/);
});
test('six ranking cards render unknown signals, scope and escaped stock names',async()=>{
 const h=harness(),calls=[];h.context.ATLAS_SESSION='s'.repeat(32);
 h.context.fetch=async(url,options)=>{calls.push({url,options});const params=new URL(url,'http://test').searchParams;let data={configured:false,nodeAvailable:true,config:{symbols:[]},jobs:[]};
  if(url.endsWith('/latest'))data=null;
  if(url.startsWith('/api/research/rankings'))data={market:params.get('market'),strategy:params.get('strategy'),status:'partial',title:'조회 성공 표본 TOP 10 (전체시장 순위 아님)',coverage_rate:.5,eligible_count:20,as_of_market_close:'2026-10-02',rows:[{rank:1,name:'<unsafe>',symbol:'005930',exchange:'XKRX',score:40,technical_30:20,fundamental_70:null,risk_level:'평가불가',unknown_signal_count:2,score_upper_bound:60,signal_details:[{feature_name:'RSI',status:'matched'}],risk_reasons:['자료부족']}]};
  return {ok:true,json:async()=>({ok:true,data})};};
 h.click('page',{page:'research'});for(let i=0;i<10;i++)await new Promise(r=>setImmediate(r));
 assert.equal((h.html().match(/<h3>(KR|US) ·/g)||[]).length,6);assert.match(h.html(),/판별불가 2개/);assert.match(h.html(),/전체시장 순위 아님/);assert.match(h.html(),/&lt;unsafe&gt;/);assert.ok(!h.html().includes('<unsafe>'));
 assert.equal(calls.filter(c=>c.url.startsWith('/api/research/rankings')).length,6);assert.ok(calls.every(c=>c.options.headers['X-Atlas-Session']===h.context.ATLAS_SESSION));
});
