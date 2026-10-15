#!/usr/bin/env python3
"""Register ATLAS locally; optionally register the official Twelve Data remote MCP."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
LOCAL_NAME = 'atlas-quant-readonly'
REMOTE_NAME = 'atlas-twelvedata'
REMOTE_URL = 'https://mcp.twelvedata.com/mcp'


class InstallError(Exception):
    pass


def atomic_json(path, value):
    path = Path(path)
    if path.is_symlink():
        raise InstallError('심볼릭 링크 설정 파일은 수정하지 않습니다.')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(prefix='.atlas-mcp-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def backup(path):
    path = Path(path)
    if path.is_symlink():
        raise InstallError('심볼릭 링크 설정 파일은 수정하지 않습니다.')
    if path.exists():
        fd, target = tempfile.mkstemp(prefix=path.name + '.atlas-backup-', dir=path.parent)
        os.close(fd)
        shutil.copyfile(path, target)
        os.chmod(target, 0o600)
        return Path(target)
    return None


def merge_json(path, additions):
    path = Path(path)
    if path.is_symlink():
        raise InstallError('심볼릭 링크 설정 파일은 수정하지 않습니다.')
    try:
        previous = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    except (ValueError, OSError):
        raise InstallError('기존 MCP 설정을 읽을 수 없어 변경하지 않았습니다.') from None
    if not isinstance(previous, dict) or not isinstance(previous.get('mcpServers', {}), dict):
        raise InstallError('기존 MCP 설정 형식이 달라 변경하지 않았습니다.')
    existing = previous.get('mcpServers', {})
    for name, value in additions.items():
        if name in existing and existing[name] != value:
            raise InstallError('동일 이름의 다른 설정이 있어 보존했습니다: ' + name)
    if all(existing.get(name) == value for name, value in additions.items()):
        return 'already_registered', None
    saved_backup = backup(path)
    value = {**previous, 'mcpServers': {**existing, **additions}}
    atomic_json(path, value)
    return 'registered', saved_backup


def executable(name):
    candidates = [shutil.which(name), str(Path('/opt/homebrew/bin') / name),
                  str(Path('/usr/local/bin') / name)]
    return next((p for p in candidates if p and Path(p).is_file() and os.access(p, os.X_OK)), None)


def local_config(root=ROOT):
    return {'command': str(Path(sys.executable).resolve()),
            'args': [str(root / 'mcp_server.py'), '--runtime-dir', str(root / 'runtime' / 'research')]}


def write_templates(root=ROOT):
    directory = root / 'runtime' / 'mcp'
    local = local_config(root)
    atomic_json(directory / 'local-mcp.json', {'mcpServers': {LOCAL_NAME: local}})
    # Separate optional provider queries: not enabled by local-only installation.
    atomic_json(directory / 'twelvedata-remote.json', {'mcpServers': {REMOTE_NAME: {'url': REMOTE_URL}}})
    toml = '[mcp_servers.' + LOCAL_NAME + ']\ncommand = ' + json.dumps(local['command']) + '\nargs = ' + json.dumps(local['args']) + '\n'
    snippet = directory / 'codex-local.toml'
    if snippet.is_symlink():
        raise InstallError('심볼릭 링크에 설정을 쓰지 않습니다.')
    snippet.write_text(toml, encoding='utf-8')
    snippet.chmod(0o600)
    return directory


def register_codex(codex, additions):
    try:
        listed = subprocess.run([codex, 'mcp', 'list', '--json'], capture_output=True, text=True, timeout=30)
        if listed.returncode:
            raise InstallError('Codex MCP 목록 조회 실패. 기존 설정은 변경하지 않았습니다.')
        servers = json.loads(listed.stdout)
        if not isinstance(servers, list):
            raise ValueError()
    except (OSError, subprocess.TimeoutExpired, ValueError):
        raise InstallError('Codex CLI의 JSON 목록 기능을 확인할 수 없습니다.') from None
    results = []
    # Validate every collision before the first mutation.
    pending = []
    for name, config in additions.items():
        present = next((s for s in servers if s.get('name') == name), None)
        if present:
            transport = present.get('transport', {})
            matches = (transport.get('url') == config['url']) if 'url' in config else (
                transport.get('command') == config['command'] and transport.get('args', []) == config['args'])
            if not matches or present.get('enabled') is not True:
                raise InstallError('동일 이름의 다른/비활성 Codex 설정을 보존했습니다: ' + name)
            results.append({'name': name, 'status': 'already_registered'})
        else:
            pending.append((name, config))
    if pending:
        config_dir = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
        backup(config_dir / 'config.toml')
    for name, config in pending:
        args = [codex, 'mcp', 'add', name]
        args += ['--url', config['url']] if 'url' in config else ['--', config['command'], *config['args']]
        # OAuth, when requested, is interactive on the user's Mac. Never log credential output.
        result = subprocess.run(args)
        if result.returncode:
            raise InstallError('MCP 등록이 완료되지 않았습니다: ' + name)
        check = subprocess.run([codex, 'mcp', 'get', name, '--json'], capture_output=True, text=True, timeout=30)
        if check.returncode:
            raise InstallError('MCP 등록 상태 확인 실패: ' + name)
        value = json.loads(check.stdout)
        transport = value.get('transport', {})
        matched = transport.get('url') == config['url'] if 'url' in config else (
            transport.get('command') == config['command'] and transport.get('args', []) == config['args'])
        if not matched or value.get('enabled') is not True:
            raise InstallError('등록된 MCP 설정이 예상과 다릅니다: ' + name)
        results.append({'name': name, 'status': 'registered'})
    return results


def smoke_test(root=ROOT):
    requests = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18', 'clientInfo': {'name': 'atlas-installer', 'version': '1.4.0'}, 'capabilities': {}}},
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
        {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'atlas_status', 'arguments': {}}}
    ]
    result = subprocess.run([sys.executable, str(root / 'mcp_server.py')],
                            input=''.join(json.dumps(r) + '\n' for r in requests), capture_output=True, text=True, timeout=15)
    try:
        replies = [json.loads(line) for line in result.stdout.splitlines()]
        tools = replies[1]['result']['tools']
        status = json.loads(replies[2]['result']['content'][0]['text'])
        if result.returncode or len(replies) != 3 or len(tools) != 6 or status.get('readOnly') is not True:
            raise ValueError()
    except (ValueError, KeyError, IndexError):
        raise InstallError('ATLAS MCP 자체 검사 실패. 클라이언트 설정을 변경하지 않았습니다.') from None
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', choices=['auto', 'codex', 'claude', 'cursor', 'templates'], default='auto')
    parser.add_argument('--twelvedata', action='store_true', help='공식 원격 MCP도 등록. OAuth/제공자 쿼터 별도')
    args = parser.parse_args()
    if sys.platform != 'darwin' and args.client != 'templates':
        raise InstallError('자동 등록은 macOS 전용입니다. 다른 환경에서는 --client templates만 사용하세요.')
    status = smoke_test()
    templates = write_templates()
    codex = executable('codex')
    home = Path.home()
    client = args.client
    if client == 'auto':
        if codex:
            client = 'codex'
        elif (home / 'Library/Application Support/Claude/claude_desktop_config.json').exists() or Path('/Applications/Claude.app').exists():
            client = 'claude'
        elif (home / '.cursor/mcp.json').exists() or Path('/Applications/Cursor.app').exists():
            client = 'cursor'
        else:
            client = 'templates'
    additions = {LOCAL_NAME: local_config()}
    if args.twelvedata:
        if client not in ('codex', 'cursor'):
            raise InstallError('원격 MCP는 Codex/Cursor 자동 등록만 지원합니다. 공식 URL과 OAuth 안내는 MCP설계_설치.md를 보세요.')
        additions[REMOTE_NAME] = {'url': REMOTE_URL}
    if client == 'codex':
        if not codex:
            raise InstallError('Codex CLI가 없습니다. 생성된 설정 파일을 이용하세요.')
        results = register_codex(codex, additions)
    elif client in ('claude', 'cursor'):
        path = home / ('Library/Application Support/Claude/claude_desktop_config.json' if client == 'claude' else '.cursor/mcp.json')
        result, saved_backup = merge_json(path, additions)
        results = [{'name': name, 'status': result} for name in additions]
        if saved_backup:
            print('기존 설정 백업:', saved_backup)
    else:
        results = [{'name': LOCAL_NAME, 'status': 'template_only'}]
    atomic_json(templates / 'installation-status.json', {
        'checkedAt': datetime.now(timezone.utc).isoformat(), 'client': client, 'servers': results,
        'localStdioSmokeTest': 'passed', 'reportAvailable': status['reportAvailable'],
        'remoteAuthentication': '미검증', 'clientToolVisibility': '재시작 후 클라이언트에서 확인 필요'})
    print('ATLAS 조회 전용 MCP 자체 검사 통과 · 도구 5개')
    if client == 'templates':
        print('MCP 클라이언트를 찾지 못했습니다. 설치 완료가 아닌 설정 파일 생성 상태입니다.')
        print('설정 파일:', templates)
    else:
        print(client + '에 MCP 설정 등록 완료. 클라이언트를 재시작해 atlas_status를 호출하세요.')
    if args.twelvedata:
        print('Twelve Data는 제공자 로그인과 조회 권한 확인이 필요합니다. 등록만으로 인증 성공을 뜻하지 않습니다.')
        if client == 'codex':
            print('인증이 미완료이면 실행: codex mcp login ' + REMOTE_NAME)
    print('주문·계좌·수집 실행 도구는 등록하지 않습니다.')


if __name__ == '__main__':
    try:
        main()
    except (InstallError, OSError, subprocess.SubprocessError, ValueError) as exc:
        print(str(exc) if isinstance(exc, InstallError) else '설치 검증 실패. MCP설계_설치.md를 확인하세요.', file=sys.stderr)
        sys.exit(1)
