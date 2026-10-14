const Q=require('../../src/engine.js');
function fixture(){
 const sample=Q.sample(),stocks=[];
 for(const market of ['KR','US'])for(let i=0;i<15;i++){
  const s=structuredClone(sample.stocks.find(s=>s.market===market));
  s.id=market+'-'+i;s.symbol=market==='KR'?String(i).padStart(6,'0'):'T'+i;s.mic=market==='KR'?'XKRX':'XNAS';s.sector='Technology';s.financialSector=false;s.flags=[];
  // Complete, liquid trend fixture; no market data claim.
  s.bars=s.bars.map((b,j)=>{const close=(market==='KR'?10000:100)*(1+j/1000)*(1+i/100);return {...b,open:close,close,high:close*1.005,low:close*.995,volume:j===s.bars.length-1?3000000:1000000};});
  s.dividend={confirmed:true,availableAt:'2026-10-02',asOf:'2026-10-02',yield:.03,yearsPaid:3,payoutRatio:.4,source:'Test dividend source'};
  stocks.push(s);
 }
 const data={...sample,stocks,synthetic:false,source:'Test fixtures only',collectedAt:'2026-10-02T12:00:00Z',priceAdjustmentPolicy:'corporate-actions-verified',universe:{}};
 for(const market of ['KR','US'])data.universe[market]={complete:true,source:'Test exchange snapshot',calendarSource:'Test sessions',asOf:'2026-10-02',expectedMarketDate:'2026-10-02',entries:stocks.filter(s=>s.market===market).map(s=>({id:s.id,market,symbol:s.symbol,mic:s.mic,status:'active',statusAsOf:'2026-10-02',securityType:'Common Stock',source:'Test status source'}))};
 return data;
}
module.exports={fixture};
