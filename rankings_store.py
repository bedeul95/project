"""Atomic six-list publication, history, last successful result and CSV export."""
import copy
import csv
import io
import json
from datetime import datetime,date,timezone
from pathlib import Path
from market_data import DataError,write_json

STRATEGIES=('value','legacy_technical','alpha_filters')

def publish(directory,rankings,now):
    directory=Path(directory)
    path=directory/'rankings.json'
    old=json.loads(path.read_text()) if path.exists() else {'last_success':{},'last_verified':{}}
    result={'generated_at':now.isoformat(),'attempts':{},'last_success':old.get('last_success',{}),'last_verified':old.get('last_verified',{})}
    for row in rankings:
        key=row['market']+':'+row['strategy']
        result['attempts'][key]=row
        if row['status'] in ('verified','partial') and row['rows']:
            result['last_success'][key]=row
        if row['status']=='verified':
            result['last_verified'][key]=row
    write_json(directory/'ranking-history'/(now.strftime('%Y%m%dT%H%M%S%f')+'.json'),result)
    write_json(path,result)
    for p in sorted((directory/'ranking-history').glob('*.json'),reverse=True)[30:]:
        p.unlink()

def publish_failure(directory,markets,now,note):
    path=Path(directory)/'rankings.json'
    old=json.loads(path.read_text()) if path.exists() else {}
    attempts=copy.deepcopy(old.get('attempts',{}))
    for market in markets:
        for strategy in STRATEGIES:
            key=market+':'+strategy
            attempts[key]={**attempts.get(key,{}),'market':market,'strategy':strategy,
                           'status':'unavailable','rows':[],'is_full_market_ranking':False,
                           'generated_at':now.isoformat(),'latest_attempt_note':note,
                           'exclude_reasons':{'collection_or_analysis_failure':1}}
    publish(directory,list(attempts.values()),now)

def select(snapshot,market,strategy,as_of='',today=None):
    if market not in ('KR','US') or strategy not in STRATEGIES:
        raise DataError('market=KR|US; strategy=value|legacy_technical|alpha_filters required')
    if as_of:
        try:
            if date.fromisoformat(as_of).isoformat()!=as_of:raise ValueError()
        except ValueError:raise DataError('as_of must be YYYY-MM-DD') from None
    key=market+':'+strategy
    attempt=snapshot.get('attempts',{}).get(key)
    available=attempt and attempt.get('rows')
    row=attempt if available else snapshot.get('last_success',{}).get(key,attempt)
    if not row:
        return {'market':market,'strategy':strategy,'status':'unavailable','rows':[],'note':'No stored analysis; configure data and run collection.'}
    row=copy.deepcopy(row)
    if as_of and row.get('as_of_market_close')!=as_of:
        return {'market':market,'strategy':strategy,'status':'unavailable','rows':[],'note':'No stored result for requested market date.'}
    today=today or datetime.now(timezone.utc).date()
    try:days=(today-date.fromisoformat(row['as_of_market_close'])).days
    except (KeyError,ValueError,TypeError):days=None
    row.update(stale=days is None or days<0 or days>7,price_age_calendar_days=days,historical=bool(not available and row.get('rows')),live_quote=False)
    if row.get('rows') and (row['historical'] or row['stale']):
        row['saved_status']=row['status'];row['status']='partial';row['is_full_market_ranking']=False
        row['title']='과거 저장 결과 · 기준일 확인'
    if attempt and not available:
        row['latest_attempt_status']=attempt['status'];row['latest_attempt_exclude_reasons']=attempt.get('exclude_reasons',{})
        row['latest_attempt_note']=attempt.get('latest_attempt_note')
    return row

def load(directory,market,strategy,as_of='',today=None):
    root=Path(directory)
    path=root/'rankings.json'
    snapshot=json.loads(path.read_text()) if path.exists() else {}
    if as_of:
        # Fixed directory, no path selected by untrusted query arguments.
        matches=[]
        for p in sorted((root/'ranking-history').glob('*.json'),reverse=True):
            value=json.loads(p.read_text());a=value.get('attempts',{}).get(market+':'+strategy,{})
            if a.get('as_of_market_close')==as_of:
                matches.append(value);break
        if matches:snapshot=matches[0]
    return select(snapshot,market,strategy,as_of,today)

def csv_export(result):
    out=io.StringIO(newline='');writer=csv.writer(out)
    columns=['rank','name','symbol','exchange','market','score','score_scale','fundamental_70','technical_30','total_100','risk_level','data_as_of','source','status']
    writer.writerow(columns)
    for row in result.get('rows',[]):
        values=[result['status'] if key=='status' else row.get(key,'') for key in columns]
        writer.writerow(["'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v for v in values])
    return ('\ufeff'+out.getvalue()).encode('utf-8')
