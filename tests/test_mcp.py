import copy
from datetime import date
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mcp_server import Reader, Server, TOOLS, ToolError, MAX_MESSAGE
from install_mcp import InstallError, merge_json, local_config, write_templates, register_codex, smoke_test


def fixture():
    row = {'id': 'US-AAPL-XNAS', 'symbol': 'AAPL', 'name': 'Example', 'market': 'US', 'currency': 'USD',
           'lastPriceDate': '2026-10-05', 'fundamental': 55, 'technical': 25, 'total': 80,
           'candidate': True, 'eligible': True, 'metrics': {'per': 15, 'pbr': 2, 'apiKey': 'SECRET'},
           'techParts': {'volume': 8, 'trend': 7, 'apiKey': 'SECRET'}, 'apiKey': 'SECRET'}
    stale = {**copy.deepcopy(row), 'id': 'KR-005930-XKRX', 'market': 'KR', 'symbol': '005930',
             'lastPriceDate': '2026-09-01', 'total': 90}
    return {'jobId': 'test', 'collectedAt': '2026-10-06T00:00:00+00:00', 'asOf': '2026-10-06', 'count': 2,
            'analysisStatus': '완료', 'apiKey': 'SECRET', 'data': {'synthetic': False, 'source': 'fixture',
            'pitPolicy': 'observed-only', 'stocks': [{'id': row['id'], 'symbol': 'AAPL', 'market': 'US',
            'currency': 'USD', 'bars': [{'date': '2026-10-05', 'open': 99, 'high': 101, 'low': 98, 'close': 100, 'volume': 1000, 'apiKey': 'SECRET'}]}]},
            'analysis': {'engineVersion': '1.4.0', 'rows': [row, stale]}}


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        self.latest = fixture()
        (self.directory / 'latest.json').write_text(json.dumps(self.latest))
        (self.directory / 'data-config.json').write_text('{"apiKey":"REAL-CONFIG-SECRET"}')
        (self.directory / 'collection-state.json').write_text(json.dumps({'jobs': [
            {'id': 'test', 'phase': 'DONE', 'credits': 762, 'apiKey': 'SECRET', 'note': 'SECRET'}]}))
        self.reader = Reader(self.directory, today=lambda: date(2026, 10, 6))

    def tearDown(self):
        self.tmp.cleanup()

    def test_tools_read_only_projection_and_no_file_changes(self):
        before = {p.name: p.read_bytes() for p in self.directory.iterdir()}
        requests = [('atlas_status', {}), ('atlas_rankings', {}),
                    ('atlas_stock_analysis', {'id': 'US-AAPL-XNAS'}),
                    ('atlas_price_history', {'id': 'US-AAPL-XNAS'}), ('atlas_collection_history', {})]
        for name, arguments in requests:
            value = self.reader.call(name, arguments)
            self.assertNotIn('SECRET', json.dumps(value))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.directory.iterdir()})
        self.assertTrue(all(t['annotations']['readOnlyHint'] for t in TOOLS))

    def test_saved_scores_freshness_and_candidate_filter(self):
        value = self.reader.call('atlas_rankings', {})
        self.assertEqual([r['total'] for r in value['rows']], [90, 80])
        self.assertTrue(value['rows'][0]['candidate'])
        self.assertFalse(value['rows'][0]['candidateUsableNow'])
        valid = self.reader.call('atlas_rankings', {'candidatesOnly': True})['rows']
        self.assertEqual([r['symbol'] for r in valid], ['AAPL'])
        self.assertEqual(valid[0]['total'], valid[0]['fundamental'] + valid[0]['technical'])
        self.assertFalse(value['context']['liveQuote'])
        self.assertEqual(self.reader.call('atlas_rankings', {'market': 'KR'})['matchingCount'], 1)

    def test_argument_bounds_and_no_orders_or_path_selection(self):
        for name, arguments in [('atlas_rankings', {'limit': 101}), ('atlas_rankings', {'limit': True}),
                                ('atlas_rankings', {'market': 'JP'}), ('atlas_rankings', {'path': 'data-config.json'}),
                                ('atlas_stock_analysis', {}), ('atlas_stock_analysis', {'id': '../data-config.json'}),
                                ('atlas_price_history', {'id': 'US-AAPL-XNAS', 'limit': 251}),
                                ('submit_order', {'quantity': 1}), ('atlas_status', [])]:
            with self.subTest(name=name, arguments=arguments), self.assertRaises(ToolError):
                self.reader.call(name, arguments)
        with self.assertRaises(ToolError):
            self.reader.read('data-config.json')

    def test_missing_scores_and_report_are_explicit(self):
        self.latest['analysis'] = None
        (self.directory / 'latest.json').write_text(json.dumps(self.latest))
        with self.assertRaisesRegex(ToolError, '미완료'):
            self.reader.call('atlas_rankings', {})
        (self.directory / 'latest.json').unlink()
        self.assertFalse(self.reader.call('atlas_status', {})['reportAvailable'])
        with self.assertRaisesRegex(ToolError, '보고서가 없습니다'):
            self.reader.call('atlas_rankings', {})

    def test_symlink_and_malformed_files_rejected_without_secrets(self):
        path = self.directory / 'latest.json'
        path.unlink()
        path.symlink_to(self.directory / 'data-config.json')
        with self.assertRaises(ToolError) as exc:
            self.reader.call('atlas_status', {})
        self.assertNotIn('SECRET', str(exc.exception))
        path.unlink()
        path.write_text('{')
        with self.assertRaises(ToolError):
            self.reader.call('atlas_status', {})


class ProtocolTests(unittest.TestCase):
    def request(self, method, params=None, request_id=1):
        return {'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params or {}}

    def test_legacy_negotiation_notifications_and_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            server = Server(Reader(directory))
            self.assertEqual(server.handle(self.request('server/discover'))['error']['code'], -32601)
            self.assertIn('error', server.handle(self.request('tools/list')))
            result = server.handle(self.request('initialize', {'protocolVersion': '2099-01-01'}))
            self.assertEqual(result['result']['protocolVersion'], '2025-06-18')
            self.assertIsNone(server.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'}))
            self.assertEqual(len(server.handle(self.request('tools/list'))['result']['tools']), 6)
            self.assertTrue(server.handle(self.request('tools/call', {'name': 'submit_order'}))['result']['isError'])
            self.assertIn('error', server.handle(self.request('initialize', {'protocolVersion': '2025-06-18'})))
            self.assertEqual(server.handle([])['error']['code'], -32600)

    def test_stdio_subprocess_parse_error_size_limit_and_clean_stdout(self):
        with tempfile.TemporaryDirectory() as directory:
            messages = [self.request('initialize', {'protocolVersion': '2025-06-18'}),
                        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                        self.request('tools/list', request_id=2),
                        self.request('tools/call', {'name': 'atlas_status', 'arguments': {}}, 3)]
            raw = '{bad json}\n' + 'x' * (MAX_MESSAGE + 1) + '\n' + ''.join(json.dumps(m) + '\n' for m in messages)
            run = subprocess.run([sys.executable, str(ROOT / 'mcp_server.py'), '--runtime-dir', directory], input=raw,
                                 capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 0)
            self.assertEqual(run.stderr, '')
            lines = [json.loads(line) for line in run.stdout.splitlines()]
            self.assertEqual(len(lines), 5)
            self.assertEqual(lines[0]['error']['code'], -32700)
            self.assertEqual(lines[1]['error']['code'], -32600)
            self.assertEqual(len(lines[3]['result']['tools']), 6)
            self.assertFalse(json.loads(lines[4]['result']['content'][0]['text'])['reportAvailable'])

    def test_real_installer_smoke_test(self):
        self.assertTrue(smoke_test()['readOnly'])


class InstallerTests(unittest.TestCase):
    def test_json_merge_backup_idempotence_and_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            original = {'preferences': {'theme': 'dark'}, 'mcpServers': {'existing': {'command': 'original'}}}
            path.write_text(json.dumps(original))
            additions = {'atlas-quant-readonly': local_config()}
            status, saved = merge_json(path, additions)
            self.assertEqual(status, 'registered')
            self.assertEqual(json.loads(saved.read_text()), original)
            self.assertEqual(os.stat(saved).st_mode & 0o777, 0o600)
            merged = path.read_bytes()
            self.assertEqual(json.loads(merged)['preferences'], original['preferences'])
            self.assertEqual(merge_json(path, additions), ('already_registered', None))
            with self.assertRaises(InstallError):
                merge_json(path, {'atlas-quant-readonly': {'command': 'different'}})
            self.assertEqual(path.read_bytes(), merged)

    def test_invalid_config_and_symlink_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text('{broken')
            with self.assertRaises(InstallError):
                merge_json(path, {'atlas': {}})
            self.assertEqual(path.read_text(), '{broken')
            link = Path(directory) / 'link.json'
            link.symlink_to(path)
            with self.assertRaises(InstallError):
                merge_json(link, {'atlas': {}})

    def test_templates_have_absolute_paths_and_no_remote_enabled_locally(self):
        with tempfile.TemporaryDirectory(prefix='atlas space ') as directory:
            root = Path(directory)
            output = write_templates(root)
            config = json.loads((output / 'local-mcp.json').read_text())['mcpServers']
            self.assertEqual(set(config), {'atlas-quant-readonly'})
            self.assertTrue(Path(config['atlas-quant-readonly']['command']).is_absolute())
            self.assertEqual(config['atlas-quant-readonly']['args'][0], str(root / 'mcp_server.py'))
            self.assertEqual(os.stat(output / 'local-mcp.json').st_mode & 0o777, 0o600)

    def test_codex_conflict_fails_before_mutation(self):
        result = subprocess.CompletedProcess([], 0, json.dumps([{'name': 'atlas', 'enabled': True,
                                              'transport': {'command': 'other', 'args': []}}]), '')
        with patch('install_mcp.subprocess.run', return_value=result) as run:
            with self.assertRaises(InstallError):
                register_codex('/fake/codex', {'new': local_config(), 'atlas': local_config()})
            self.assertEqual(run.call_count, 1)

    def test_codex_registration_verifies_cli_readback(self):
        config = local_config()
        responses = [subprocess.CompletedProcess([], 0, '[]', ''), subprocess.CompletedProcess([], 0),
                     subprocess.CompletedProcess([], 0, json.dumps({'enabled': True, 'transport': config}), '')]
        with patch('install_mcp.backup'), patch('install_mcp.subprocess.run', side_effect=responses) as run:
            result = register_codex('/fake/codex', {'atlas': config})
            self.assertEqual(result, [{'name': 'atlas', 'status': 'registered'}])
            self.assertEqual(run.call_args_list[1].args[0], ['/fake/codex', 'mcp', 'add', 'atlas', '--', config['command'], *config['args']])


if __name__ == '__main__':
    unittest.main()
