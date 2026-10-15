# Project03 실행 구조

| 파일 | 역할 |
| --- | --- |
| server.py | loopback HTTP, Host/Origin/session 보호, 기본 broker 비활성 |
| market_data.py | Twelve Data 고정 GET·캐시·예산·TTM·마감일봉·예약·상태 재확인 |
| universe.py | 외부 공식/계약 마스터의 ID·상태·날짜·시장 검증 |
| research_cli.py | master import, 정규화 데이터 분석, 수동 batch, 상태 |
| analyze.cjs | Python→Node JSON bridge, 공통 엔진과6개 순위 |
| src/engine.js | 기존70+30 계산·재무시점·동일 산식 percentile 캐시 |
| src/research.js | 공통추천 gate·10개 알파·위험·독립순위·커버리지 |
| rankings_store.py | 원자 발행·최근30개 이력·과거결과·CSV |
| src/read-ui.js | 키/조회 설정·6개 카드·계산 근거·CSV |
| src/app.js | 기존 스크리너/상세/모의 UI |
| mcp_server.py | 저장 자료 읽기 stdio MCP, atlas_top10 포함6개 도구 |
| install_mcp.py | 읽기전용 MCP 등록/자체검사, 사용자의 클라이언트 설정 |
| install_scheduler.py | macOS LaunchAgent로 로컬 서버 유지 |
| build.py / 시작.html | src를 단일 offline HTML로 묶는 생성물 |
| tests/ / .github/workflows/test.yml | 엔진·collector·HTTP·MCP·DOM·CI 빌드 검증 |

순서: master/지정 목록 → collector 고정GET → 정규화·TTM·상태 재확인 → Node의 동일70/30 + research.js → latest/reports + rankings.json 원자 발행 → UI/API/읽기전용 MCP.

MCP는 키/config/cache를 읽지 않으며 네트워크 조회·주문·설정 변경 도구가 없습니다. loopback HTTP는 /api/research/rankings에도 세션을 요구합니다. 계좌코드 broker.py/src/broker-ui.js는 원본 보존이며 자동으로 활성화하지 않습니다.

전략별 status와 최신 시도/과거 성공본은 분리합니다. 다른 시장의 기존 자료는 원래 기준일을 유지하며 새 날짜로 변조하지 않습니다. verified여도 저장결과로서 실시간 호가가 아니며7일 초과 결과는 stale·과거로 표시합니다. 실제 당일 마스터가 갱신되지 않으면 신규 whole-market verified를 발행하지 않습니다.
