#!/usr/bin/env python3
"""ATLAS read-only stdio MCP, legacy protocol 2025-06-18. No network or keys."""
import argparse
from datetime import datetime, timezone, timedelta, date
import json
import math
import os
from pathlib import Path
import stat
import sys

VERSION = '1.4.0'
PROTOCOL = '2025-06-18'
LEGACY_VERSIONS = ('2024-11-05', '2025-03-26', PROTOCOL)
MAX_MESSAGE = 65536
MAX_FILE = 16 * 1024 * 1024
KST = timezone(timedelta(hours=9))
METRICS = ('per', 'pbr', 'marketCap', 'ev', 'fcf', 'roe', 'roic', 'margin',
           'profitCV', 'revenueGrowth', 'profitGrowth', 'cashConversion',
           'debtCashFlow', 'interestCover', 'earningsYield', 'fcfYield', 'opYield', 'evOp')
ROW_FIELDS = ('id', 'symbol', 'name', 'market', 'currency', 'asOf', 'lastPriceDate',
              'observedAt', 'fundamental', 'technical', 'total', 'candidate', 'eligible',
              'reasons', 'warnings', 'volumeRatio', 'flowActive', 'techParts', 'techReady',
              'financialPeriod', 'financialAvailableAt')
SUMMARY_FIELDS = ('jobId', 'collectedAt', 'asOf', 'count', 'marketDates', 'analysisStatus')
JOB_FIELDS = ('id', 'startedAt', 'endedAt', 'phase', 'market', 'reason', 'total', 'completed', 'credits')


class ToolError(Exception):
    pass


def project(value, fields):
    return {key: value[key] for key in fields if key in value}


def tool(name, description, properties=None, required=None):
    schema = {'type': 'object', 'properties': properties or {}, 'additionalProperties': False}
    if required:
        schema['required'] = required
    return {'name': name, 'description': description, 'inputSchema': schema,
            'annotations': {'readOnlyHint': True, 'destructiveHint': False,
                            'idempotentHint': True, 'openWorldHint': False}}


TOOLS = [
    tool('atlas_status', '저장된 보고서와 수집 기록의 상태. 서버 생존/인증 상태를 확인하는 도구는 아닙니다.'),
    tool('atlas_rankings', '저장된 기업70+기술30 점수 순위. 지정 목록 안의 비교이며 시장 전체 순위가 아닙니다.', {
        'market': {'type': 'string', 'enum': ['ALL', 'KR', 'US'], 'default': 'ALL'},
        'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 20},
        'candidatesOnly': {'type': 'boolean', 'default': False}}),
    tool('atlas_stock_analysis', '저장된 한 기업의 PER/PBR·70/30점·거래량·제외 사유. id는 순위 도구에서 가져오세요.',
         {'id': {'type': 'string', 'minLength': 1, 'maxLength': 80}}, ['id']),
    tool('atlas_price_history', '저장된 완료 일봉 최대250개. 실시간 호가가 아니며 추가 API 호출을 하지 않습니다.', {
        'id': {'type': 'string', 'minLength': 1, 'maxLength': 80},
        'limit': {'type': 'integer', 'minimum': 1, 'maximum': 250, 'default': 60}}, ['id']),
    tool('atlas_collection_history', '최근 수집 기록과 사용 크레딧. 재수집을 시작하지 않습니다.', {
        'limit': {'type': 'integer', 'minimum': 1, 'maximum': 30, 'default': 10}})
]


class Reader:
    def __init__(self, directory, today=None):
        self.directory = Path(directory).resolve()
        self.today = today or (lambda: datetime.now(KST).date())

    def read(self, name):
        # Tool arguments cannot select a path. Config, cache and broker files are never opened.
        if name not in ('latest.json', 'collection-state.json'):
            raise ToolError('허용하지 않는 자료입니다.')
        try:
            fd = os.open(self.directory / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ToolError('일반 JSON 파일만 읽을 수 있습니다.')
                raw = stream.read(MAX_FILE + 1)
            if len(raw) > MAX_FILE:
                raise ToolError('보고서 용량 한도 초과입니다.')
            value = json.loads(raw, parse_constant=lambda _: None)
            if not isinstance(value, dict):
                raise ToolError('보고서 형식 오류입니다.')
            return value
        except FileNotFoundError:
            return None
        except (OSError, ValueError, UnicodeError):
            raise ToolError('저장된 보고서를 읽을 수 없습니다. 웹 화면에서 자료를 확인하세요.') from None

    def latest(self):
        value = self.read('latest.json')
        if value is None:
            raise ToolError('수집된 보고서가 없습니다. 웹 화면에서 조회·분석을 먼저 실행하세요.')
        return value

    def context(self, latest):
        data = latest.get('data') or {}
        return {**project(latest, SUMMARY_FIELDS), 'source': data.get('source'),
                'synthetic': data.get('synthetic'), 'pitPolicy': data.get('pitPolicy'),
                'retrievedAt': datetime.now(timezone.utc).isoformat(), 'liveQuote': False,
                'scope': '사용자가 지정한 종목 목록',
                'scoreMeaning': '분석일의 가설 점수. 미래 수익률 예측 확률이 아닙니다.',
                'freshnessPolicy': '가격일 7일 초과 또는 날짜 미확인은 현재 후보로 사용 보류'}

    def row(self, raw):
        row = project(raw, ROW_FIELDS)
        row['metrics'] = project(raw.get('metrics') or {}, METRICS)
        row['techParts'] = project(raw.get('techParts') or {}, ('volume', 'trend', 'momentum', 'volatility'))
        try:
            age = (self.today() - date.fromisoformat(raw['lastPriceDate'])).days
        except (KeyError, ValueError, TypeError):
            age = None
        row['priceAgeCalendarDays'] = age
        row['stale'] = age is None or age > 7 or age < 0
        row['candidateUsableNow'] = raw.get('candidate') is True and not row['stale']
        return row

    def rows(self, latest):
        analysis = latest.get('analysis')
        if not isinstance(analysis, dict) or not isinstance(analysis.get('rows'), list):
            raise ToolError('서버 점수 계산이 미완료입니다. Node 설치와 웹 화면의 분석 상태를 확인하세요.')
        return [self.row(raw) for raw in analysis['rows'] if isinstance(raw, dict)]

    def call(self, name, arguments):
        definition = next((t for t in TOOLS if t['name'] == name), None)
        if definition is None:
            raise ToolError('허용하지 않는 도구입니다. 조회 전용 도구만 제공합니다.')
        validate_arguments(arguments, definition['inputSchema'])
        if name == 'atlas_collection_history':
            state = self.read('collection-state.json') or {}
            jobs = state.get('jobs', [])
            if not isinstance(jobs, list):
                raise ToolError('수집 기록 형식 오류입니다.')
            return {'jobs': [project(j, JOB_FIELDS) for j in reversed(jobs[-arguments.get('limit', 10):])
                             if isinstance(j, dict)], 'runningIsRecordedStateOnly': True}
        if name == 'atlas_status':
            latest = self.read('latest.json')
            return {'version': VERSION, 'readOnly': True, 'providerCallsMade': 0,
                    'reportAvailable': latest is not None, 'scoresAvailable': bool(latest and latest.get('analysis')),
                    'lastData': self.context(latest) if latest else None,
                    'collectorLiveness': '확인하지 않음', 'credentials': '읽지 않음'}
        latest = self.latest()
        context = self.context(latest)
        if name == 'atlas_price_history':
            stocks = (latest.get('data') or {}).get('stocks', [])
            stock = next((s for s in stocks if isinstance(s, dict) and s.get('id') == arguments['id']), None)
            if stock is None:
                raise ToolError('저장 목록에 없는 종목 ID입니다.')
            bars = stock.get('bars') or []
            if not isinstance(bars, list):
                raise ToolError('일봉 형식 오류입니다.')
            return {'context': context, **project(stock, ('id', 'symbol', 'market', 'currency')),
                    'bars': [project(b, ('date', 'open', 'high', 'low', 'close', 'volume'))
                             for b in bars[-arguments.get('limit', 60):] if isinstance(b, dict)]}
        rows = self.rows(latest)
        if name == 'atlas_stock_analysis':
            row = next((r for r in rows if r.get('id') == arguments['id']), None)
            if row is None:
                raise ToolError('저장 목록에 없는 종목 ID입니다.')
            return {'context': context, 'engineVersion': latest['analysis'].get('engineVersion'), 'row': row}
        market = arguments.get('market', 'ALL')
        selected = [r for r in rows if (market == 'ALL' or r.get('market') == market)
                    and (not arguments.get('candidatesOnly', False) or r['candidateUsableNow'])]
        selected.sort(key=lambda r: (-(r.get('total') if isinstance(r.get('total'), (int, float)) else -1), str(r.get('id', ''))))
        return {'context': context, 'engineVersion': latest['analysis'].get('engineVersion'),
                'matchingCount': len(selected), 'rows': selected[:arguments.get('limit', 20)]}


def validate_arguments(arguments, schema):
    if not isinstance(arguments, dict) or set(arguments) - set(schema['properties']):
        raise ToolError('허용된 인자만 객체로 입력하세요.')
    for key in schema.get('required', []):
        if key not in arguments:
            raise ToolError('필수 인자가 없습니다: ' + key)
    for key, value in arguments.items():
        rule = schema['properties'][key]
        if rule['type'] == 'integer':
            ok = type(value) is int and rule.get('minimum', value) <= value <= rule.get('maximum', value)
        elif rule['type'] == 'boolean':
            ok = type(value) is bool
        else:
            ok = isinstance(value, str) and rule.get('minLength', 0) <= len(value) <= rule.get('maxLength', 100) and not any(ord(c) < 32 for c in value)
        if not ok or ('enum' in rule and value not in rule['enum']):
            raise ToolError('인자 형식/범위 오류: ' + key)


def clean(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value


class Server:
    def __init__(self, reader):
        self.reader = reader
        self.initialized = False
        self.ready = False

    @staticmethod
    def error(request_id, code, message):
        return {'jsonrpc': '2.0', 'id': request_id, 'error': {'code': code, 'message': message}}

    def handle(self, request):
        if not isinstance(request, dict) or request.get('jsonrpc') != '2.0' or not isinstance(request.get('method'), str):
            return self.error(None, -32600, 'Invalid request')
        notification = 'id' not in request
        request_id = request.get('id')
        if not notification and (request_id is None or type(request_id) not in (str, int)):
            return self.error(None, -32600, 'Invalid request id')
        method = request['method']
        params = request.get('params', {})
        if not isinstance(params, dict):
            return None if notification else self.error(request_id, -32602, 'Invalid params')
        if notification:
            if method == 'notifications/initialized' and self.initialized:
                self.ready = True
            return None
        if method == 'server/discover':
            # Explicit legacy fallback for dual-era clients; do not claim 2026-07-28 support.
            return self.error(request_id, -32601, 'Legacy MCP server; use initialize, protocol 2025-06-18')
        metadata = params.get('_meta', {})
        if isinstance(metadata, dict) and any(str(k).startswith('io.modelcontextprotocol/') for k in metadata):
            return self.error(request_id, -32601, 'Legacy MCP server; use initialize, protocol 2025-06-18')
        if method == 'initialize':
            if self.initialized or not isinstance(params.get('protocolVersion'), str):
                return self.error(request_id, -32602, 'Invalid initialize')
            self.initialized = True
            version = params['protocolVersion'] if params['protocolVersion'] in LEGACY_VERSIONS else PROTOCOL
            result = {'protocolVersion': version, 'capabilities': {'tools': {'listChanged': False}},
                      'serverInfo': {'name': 'atlas-quant-readonly', 'version': VERSION},
                      'instructions': '저장된 분석만 조회합니다. 날짜·stale·제외 사유를 함께 설명하세요. 주문 도구는 없습니다.'}
        elif method == 'ping':
            result = {}
        elif not self.ready:
            return self.error(request_id, -32600, 'Initialize and send notifications/initialized first')
        elif method == 'tools/list':
            result = {'tools': TOOLS}
        elif method == 'tools/call':
            if not isinstance(params.get('name'), str):
                return self.error(request_id, -32602, 'Tool name required')
            try:
                value = clean(self.reader.call(params['name'], params.get('arguments', {})))
                result = {'content': [{'type': 'text', 'text': json.dumps(value, ensure_ascii=False, allow_nan=False)}]}
            except ToolError as exc:
                result = {'content': [{'type': 'text', 'text': str(exc)}], 'isError': True}
            except Exception:
                result = {'content': [{'type': 'text', 'text': '보고서 형식 오류입니다. 웹 화면에서 확인하세요.'}], 'isError': True}
        else:
            return self.error(request_id, -32601, 'Method not found')
        return {'jsonrpc': '2.0', 'id': request_id, 'result': result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-dir', type=Path, default=Path(__file__).resolve().parent / 'runtime' / 'research', help='research 보고서 폴더')
    args = parser.parse_args()
    server = Server(Reader(args.runtime_dir))
    stream = sys.stdin.buffer
    while True:
        raw = stream.readline(MAX_MESSAGE + 1)
        if not raw:
            break
        if len(raw) > MAX_MESSAGE:
            # Drain the same oversized line without allocating it.
            while raw and not raw.endswith(b'\n'):
                raw = stream.readline(MAX_MESSAGE + 1)
            response = server.error(None, -32600, 'Message size limit')
        else:
            try:
                request = json.loads(raw)
                response = server.handle(request)
            except (ValueError, UnicodeError):
                response = server.error(None, -32700, 'Parse error')
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False, allow_nan=False) + '\n')
            sys.stdout.flush()


if __name__ == '__main__':
    main()
