'use strict';
const Q=require('./src/engine.js');
let input='';process.stdin.setEncoding('utf8');process.stdin.on('data',part=>{input+=part;if(Buffer.byteLength(input)>12*1024*1024){process.stderr.write('Input limit');process.exit(2);}});
process.stdin.on('end',()=>{try{
 const {data,asOf,config}=JSON.parse(input);Q.validate(data);const scoreConfig=Q.config(config);
 const rows=['KR','US'].flatMap(m=>Q.screen(data,m,asOf,scoreConfig)).map(r=>({id:r.stock.id,symbol:r.stock.symbol||r.stock.id,name:r.stock.name,market:r.stock.market,currency:r.stock.currency,
  asOf,lastPriceDate:r.last?.date,observedAt:r.stock.observedAt,fundamental:r.fundamental,technical:r.technical,total:r.total,
  candidate:r.candidate,eligible:r.eligible,reasons:[...r.reasons,...r.entryReasons],warnings:r.warnings,metrics:r.metrics,volumeRatio:r.flow.ratio,
  flowActive:r.flow.active,techParts:r.tech.parts,techReady:r.tech.ready,financialPeriod:r.f?.periodEnd,financialAvailableAt:r.f?.availableAt}));
 process.stdout.write(JSON.stringify({engineVersion:Q.VERSION,asOf,config:scoreConfig,rows}));
 }catch(e){process.stderr.write(String(e.message));process.exitCode=1;}});
