#!/usr/bin/env python3
"""Account-free batch runner and exchange snapshot importer."""
import argparse
import json
from datetime import datetime,timezone
from pathlib import Path
from market_data import Collector,DataError,write_json
from universe import validate_master

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--runtime-dir',default=str(Path(__file__).resolve().parent/'runtime/research'))
    sub=p.add_subparsers(dest='command',required=True)
    imp=sub.add_parser('import-universe');imp.add_argument('file',type=Path)
    run=sub.add_parser('run');run.add_argument('--market',choices=['ALL','KR','US'],default='ALL')
    dataset=sub.add_parser('analyze-file');dataset.add_argument('file',type=Path)
    sub.add_parser('status')
    args=p.parse_args()
    try:
        c=Collector(args.runtime_dir)
        try:
            if args.command=='import-universe':
                # Dates, session calendar and status source must come from a verified supplier.
                value=json.loads(args.file.read_text())
                validate_master(value,datetime.now(timezone.utc).astimezone(__import__('market_data').KST).date().isoformat())
                write_json(c.directory/'universe.json',value)
                c.save_config({'universeMode':'master'})
                print(json.dumps({'imported':{m:len(v['entries']) for m,v in value['markets'].items()},'mode':'master'}))
            elif args.command=='analyze-file':
                value=json.loads(args.file.read_text())
                now=c.clock();today=now.astimezone(__import__('market_data').KST).date().isoformat()
                as_of=value.get('analysisAsOf',today)
                if not __import__('universe').day(as_of) or as_of>today:raise ValueError('Invalid analysis date')
                validate_master({'schemaVersion':1,'markets':value.get('universe',{})},as_of)
                value['collectedAt']=now.isoformat()
                result=c.analyze(value,as_of,{})
                from rankings_store import publish
                publish(c.directory,result['rankings'],now)
                write_json(c.directory/'latest.json',dict(jobId='import-'+now.strftime('%Y%m%dT%H%M%S'),collectedAt=now.isoformat(),asOf=as_of,count=len(value['stocks']),data=value,analysis=result,analysisStatus='완료',failures=[]))
                print(json.dumps({'lists':[{k:r[k] for k in ['market','strategy','status','coverage_rate']} for r in result['rankings']]},ensure_ascii=False))
            elif args.command=='run':
                c.start(args.market);c.worker.join()
                job=c.status()['jobs'][0]
                print(json.dumps({k:job[k] for k in ['id','phase','completed','total','credits','note']},ensure_ascii=False))
                return 0 if job['phase']=='DONE' else 2
            else:
                print(json.dumps(c.status(),ensure_ascii=False))
        finally:
            c.close()
    except (DataError,ValueError) as error:
        p.exit(1,str(error)+'\n')
    except OSError:
        p.exit(1,'Cannot access research input/runtime files.\n')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
