# Project03 실행/이관 가이드

현재 Git 저장소만 clone해서는 실행할 수 없다. 분석한 원본 ZIP을 별도로 풀고 그 폴더에서 실행한다.

```bash
python3 server.py --no-schedule
python3 build.py
node --test tests/*.test.cjs
python3 -m unittest discover -s tests -p 'test_*.py'
```

서버 주소127.0.0.1:8765. 키 없이 live 연결 성공이라고 하지 않는다.
자동분석설치.command는 macOS LaunchAgent를 등록하며 설치 경로가 바뀌면 재등록한다.
read-only MCP 설치/버전 협상은 원본 MCP설계_설치.md와 mcp_server.py를 함께 읽는다.
소스 이관 전에 프로젝트 공개 범위·최종 유지 브랜치·runtime/키 제외·원본 해시를 확인한다.
실제 계좌 연동/주문은 별도 후속 작업이며 이관 과정에서 활성화하지 않는다.
