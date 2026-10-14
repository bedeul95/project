# Project03 원본 코드 구조

아래는 분석한 원본 atlas-quant-mac-v1.4.0.zip의 구조다. 이 Git tree에 실행 코드가 있는 것으로 읽지 않는다.

| 원본 파일 | 책임 | 진입점 |
| --- | --- | --- |
| server.py | loopback HTTP·Host/Origin/세션·READ API·collector 시작 | Handler.do_GET/do_POST, main |
| market_data.py | Twelve Data 허용 GET·크레딧 예산·완료 일봉·재무 캐시·TTM·보고서·예약 | Collector, normalize, ttm_snapshots, completed_date |
| analyze.cjs | Python→Node JSON 점수 계산 bridge | stdin data/asOf/config → Q.validate/Q.screen → analysis JSON |
| src/engine.js | 기업70+기술30·필터·지표·연구 백테스트/모의 주문 | validate, config, snapshot, flow, technical, screen, backtest, paperOrder |
| src/app.js | 스크리너/기업 상세·관심목록·백업·모의 화면 | 공통 engine 결과/브라우저 상태 조합 |
| src/read-ui.js | 조회 설정·실행/상태·수집본 적용 UI | read API + 화면 상태 |
| mcp_server.py | 저장된 분석 읽기 stdio MCP; 공급자 호출/주문 없음 | Reader, Server, tools/list, tools/call |
| install_mcp.py | 로컬 MCP 설정 설치 | 프로젝트 경로를 MCP 클라이언트 설정에 등록 |
| broker.py / src/broker-ui.js | 이전 KIS 계좌/주문 어댑터와 UI 보존 | 기본 조회 제품에서 활성화하지 않음 |
| build.py / 시작.html | JS/CSS를 독립 HTML로 조립 | 시작.html은 생성 결과; src가 수정 원본 |
| install_scheduler.py / 자동분석설치.command | macOS LaunchAgent 등록 | 설치 폴더 경로와 runtime 로그 |
| tests/ | 수집/HTTP/MCP·엔진·DOM 모의 회귀 | Python unittest / Node 내장 test |

## 흐름

브라우저 read-ui → loopback server → Collector 허용 GET → 일봉/재무 정규화·캐시·예산 →
analyze.cjs → 같은 engine70/30 → latest/report JSON → UI 또는 read-only MCP.
MCP는 저장된 자료를 읽으며 새로운 공급자 호출·설정 쓰기·매매를 수행하지 않는다.
src는 UI/계산 원본, 시작.html은 build.py 결과다. broker 어댑터 보존과 실제 활성 계좌 연동은 다르다.
재무 API 관측 시점이 실제 공시 시점으로 확인되지 않으면 과거 백테스트를 제한한다.
