#!/usr/bin/env python3
"""Loopback-only application server with server-side KIS credentials."""
import argparse
import http.server
from pathlib import Path
import threading
import urllib.parse
import webbrowser
import json
import secrets
from broker import Broker, BrokerError
from market_data import Collector, DataError

ROOT = Path(__file__).resolve().parent
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Query strings and account diagnostics never go to stdout.

    def permitted(self, api=False):
        expected='127.0.0.1:'+str(self.server.server_port)
        if self.headers.get('Host')!=expected:
            self.send_error(403);return False
        if api and not secrets.compare_digest(self.headers.get('X-Atlas-Session',''),self.server.session):
            self.send_error(403);return False
        if api and self.headers.get('Origin') not in (None,'http://'+expected):
            self.send_error(403);return False
        return True

    def respond(self,body,content_type='application/json',status=200):
        if not isinstance(body,bytes):body=json.dumps(body,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self' data: blob:; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers();self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if not self.permitted(path.startswith('/api/')):return
        if path.startswith('/api/'):
            query=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            get=lambda k:query.get(k,[''])[0]
            try:
                broker=getattr(self.server,'broker',None)
                collector=getattr(self.server,'collector',None)
                if path=='/api/read/status' and collector:result=collector.status()
                elif path=='/api/read/latest' and collector:result=collector.latest()
                elif path=='/api/status':result=broker.status() if broker else {'provider':'KIS','enabled':False,'note':'계좌·주문 연결 비활성'}
                elif not broker:self.respond({'ok':False,'error':'계좌·주문 API 비활성'},status=403);return
                elif path=='/api/quote':result=broker.quote(get('market'),get('symbol'),get('exchange'))
                elif path=='/api/history':result=broker.history()
                elif path=='/api/orders':result=broker.broker_orders(get('market'),get('exchange'),get('start'),get('end'))
                else:self.send_error(404);return
                self.respond({'ok':True,'data':result})
            except (BrokerError,DataError) as error:self.respond({'ok':False,'error':str(error)},status=400)
            except Exception:self.respond({'ok':False,'error':'서버 처리 실패 · 주문을 자동 재전송하지 마세요.'},status=500)
            return
        if path == '/health':
            body = b'{"status":"ok","mode":"local-research"}'
            content_type = 'application/json'
        elif path in ('/', '/index.html', '/' + urllib.parse.quote('시작.html')) or urllib.parse.unquote(path) == '/시작.html':
            html=(ROOT / '시작.html').read_text()
            html=html.replace('<script>', '<script>window.ATLAS_SESSION='+json.dumps(self.server.session)+';</script><script>',1)
            body=html.encode()
            content_type = 'text/html; charset=utf-8'
        else:
            self.send_error(404)
            return
        self.respond(body,content_type)
    def do_POST(self):
        path=urllib.parse.urlsplit(self.path).path
        if not path.startswith('/api/'):self.send_error(405);return
        if not self.permitted(True):return
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size<=0 or size>65536 or self.headers.get_content_type()!='application/json':raise BrokerError('JSON 본문 최대 64KiB가 필요합니다.')
            data=json.loads(self.rfile.read(size))
            if not isinstance(data,dict):raise BrokerError('JSON 객체를 입력하세요.')
            b=getattr(self.server,'broker',None)
            c=getattr(self.server,'collector',None)
            if path=='/api/read/config' and c:result=c.save_config(data)
            elif path=='/api/read/run' and c:result=c.start(data.get('market','ALL'))
            elif not b:self.respond({'ok':False,'error':'계좌·주문 API 비활성'},status=403);return
            elif path=='/api/config':result=b.save_config(data)
            elif path=='/api/connect':result=b.authenticate()
            elif path=='/api/preview':result=b.preview(data)
            elif path=='/api/submit':
                ticket=data.get('ticket')
                if not isinstance(ticket,str) or len(ticket)>100:raise BrokerError('검토표 ID를 확인하세요.')
                result=b.submit(ticket)
            else:self.send_error(404);return
            self.respond({'ok':True,'data':result})
        except (ValueError,TypeError):self.respond({'ok':False,'error':'JSON 입력 형식을 확인하세요.'},status=400)
        except (BrokerError,DataError) as error:self.respond({'ok':False,'error':str(error)},status=400)
        except Exception:self.respond({'ok':False,'error':'서버 처리 실패 · 주문을 자동 재전송하지 마세요.'},status=500)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-open', action='store_true')
    parser.add_argument('--runtime-dir',default=str(ROOT/'runtime'))
    parser.add_argument('--enable-broker',action='store_true',help='Opt-in legacy account/order API; disabled by default')
    parser.add_argument('--no-schedule',action='store_true')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('port must be 1024~65535')
    try:
        server = http.server.ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
        server.session=secrets.token_urlsafe(32)
        server.broker=Broker(args.runtime_dir) if args.enable_broker else None
        server.collector=Collector(Path(args.runtime_dir)/'research')
        if not args.no_schedule:server.collector.begin_scheduler()
    except (OSError,BrokerError,DataError) as exc:
        parser.exit(1, f'서버를 시작할 수 없습니다: {exc}\n다른 포트를 쓰거나 시작.html을 직접 여세요.\n')
    url = f'http://127.0.0.1:{args.port}'
    print(f'ATLAS Mac: {url}\n종료: Ctrl+C', flush=True)
    if not args.no_open:
        threading.Timer(.3, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.collector.close()
        server.server_close()

if __name__ == '__main__':
    main()
