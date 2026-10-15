#!/usr/bin/env python3
"""Install only this local read-only server as a macOS login LaunchAgent."""
import os, plistlib, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
LABEL='com.atlas.quant.research'
if sys.platform!='darwin':sys.exit('이 설치 파일은 macOS에서만 실행합니다.')
agent=Path.home()/'Library'/'LaunchAgents'/(LABEL+'.plist')
domain='gui/'+str(os.getuid());service=domain+'/'+LABEL
if '--remove' in sys.argv:
 subprocess.run(['launchctl','bootout',service],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 if agent.exists():agent.unlink()
 print('ATLAS 자동 실행을 해제했습니다. 데이터·키·분석 기록은 보존했습니다.');sys.exit()
node=shutil.which('node') or next((str(p) for p in [Path('/opt/homebrew/bin/node'),Path('/usr/local/bin/node')] if p.is_file()),None)
if not node:sys.exit('Node.js 18+를 먼저 설치하세요. 설치 안내: README.md')
r=subprocess.run([node,'--version'],capture_output=True,text=True)
try:major=int(r.stdout.strip().lstrip('v').split('.')[0])
except ValueError:major=0
if major<18:sys.exit('Node.js 18+가 필요합니다.')
runtime=ROOT/'runtime';runtime.mkdir(exist_ok=True,mode=0o700)
agent.parent.mkdir(parents=True,exist_ok=True)
program=dict(Label=LABEL,ProgramArguments=[sys.executable,str(ROOT/'server.py'),'--no-open'],WorkingDirectory=str(ROOT),RunAtLoad=True,KeepAlive=True,ThrottleInterval=30,
 StandardOutPath=str(runtime/'scheduler.log'),StandardErrorPath=str(runtime/'scheduler-error.log'),
 EnvironmentVariables={'PATH':str(Path(node).parent)+':/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin'},ProcessType='Background')
with agent.open('wb') as f:plistlib.dump(program,f)
os.chmod(agent,0o600)
subprocess.run(['launchctl','bootout',service],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
r=subprocess.run(['launchctl','bootstrap',domain,str(agent)],capture_output=True,text=True)
if r.returncode:sys.exit('자동 실행 등록 실패. README의 수동 서버 실행을 사용하세요. '+r.stderr.strip())
print('자동 실행 등록 완료. 폴더를 이동하지 마세요. http://127.0.0.1:8765 에서 조회 설정을 저장하세요.')
print('이미 수동 서버를 열었다면 Ctrl+C로 종료하세요. 등록한 서버가 자동으로 다시 시작합니다.')
