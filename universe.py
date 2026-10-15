"""Validated, dated exchange/status snapshot. Never infer active status from a quote."""
import re
from datetime import date

MARKETS={'KR':{'XKRX','XKOS'},'US':{'XNAS','XNYS','XASE'}}
STATUSES={'active','halt','managed','delisted','noncompliant','unknown'}

def day(value):
    try:
        return isinstance(value,str) and date.fromisoformat(value).isoformat()==value
    except ValueError:
        return False

def validate_master(value, today):
    if not isinstance(value,dict) or value.get('schemaVersion')!=1:
        raise ValueError('Universe schemaVersion 1 required')
    if not isinstance(value.get('markets'),dict) or set(value['markets'])-set(MARKETS):
        raise ValueError('Universe markets must be KR/US')
    for market,meta in value['markets'].items():
        if not isinstance(meta,dict) or type(meta.get('complete')) is not bool:
            raise ValueError('Explicit complete flag required')
        for key in ['asOf','expectedMarketDate']:
            if not day(meta.get(key)) or meta[key]>today:
                raise ValueError('Invalid/future universe date: '+key)
        if meta['expectedMarketDate']>meta['asOf']:
            raise ValueError('Universe predates expected session')
        for key in ['source','calendarSource']:
            if not isinstance(meta.get(key),str) or not 1<=len(meta[key])<=200 or '://' in meta[key] and '?' in meta[key]:
                raise ValueError('Named source required; credential URLs forbidden')
        entries=meta.get('entries')
        if not isinstance(entries,list) or not 1<=len(entries)<=20000:
            raise ValueError('Universe requires 1..20000 entries per market')
        seen=set()
        for e in entries:
            if not isinstance(e,dict) or e.get('mic') not in MARKETS[market]:
                raise ValueError('Invalid universe exchange')
            symbol=e.get('symbol','')
            pattern=r'[0-9A-Z]{6}' if market=='KR' else r'[A-Z][A-Z0-9.\-]{0,11}'
            if not isinstance(symbol,str) or not re.fullmatch(pattern,symbol):
                raise ValueError('Invalid universe symbol')
            expected=market+'-'+symbol+'-'+e['mic']
            if e.get('id')!=expected or expected in seen:
                raise ValueError('Invalid/duplicate universe ID')
            seen.add(expected)
            if e.get('status') not in STATUSES or not day(e.get('statusAsOf')) or e['statusAsOf']>today:
                raise ValueError('Explicit status/date required')
            if not isinstance(e.get('securityType'),str) or not 1<=len(e['securityType'])<=80:
                raise ValueError('Security type required')
            if not isinstance(e.get('source'),str) or not 1<=len(e['source'])<=200 or '?' in e['source']:
                raise ValueError('Status source required without credentials')
    return value

def collection_symbols(master,market):
    return [dict(market=m,symbol=e['symbol'],mic=e['mic'])
            for m,meta in master['markets'].items() if market=='ALL' or m==market
            for e in meta['entries'] if e['status']=='active' and e['securityType']=='Common Stock']
