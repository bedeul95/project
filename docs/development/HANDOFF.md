# Project03 개발 인수인계 — 1.5.0

2026-10-15: 원본 ZIP의32개 파일을 SOURCE_INDEX의 SHA256과 대조하여 이관했습니다. 원본 이관 commit `18395fc`와 후속 기능 변경을 분리합니다. 원본 README는 docs/reference/ORIGINAL_README.md, 원본 해시는 SOURCE_INDEX.md에 보존합니다. 원본 키/runtime은 가져오지 않았습니다.

## 완료

- 기존 기업70+기술30 산식 유지. engine screen에 가격 기준일을 별도로 전달하여 미국 전일 가격과 한국시간 재무 관측일을 함께 처리합니다. 날짜 없는 기존 호출의 동작은 유지합니다.
- 업종/시장 percentile 분포를 캐시하고 이진 탐색하여 큰 유니버스에서 반복 전체 검색을 줄입니다.
- research.js는6개 독립 순위를 계산합니다. state gate를 먼저 적용한 종목으로 업종 비교하고 재무 누락시 null, 알파 unavailable/미충족을 구분합니다. 신호당10점의 하한·상한과 상관 경고를 반환합니다.
- master 모드는 runtime/universe.json의 거래 가능한 보통주를 수집합니다. 발행 직전 상태 파일을 재확인하며 stale/unknown/managed/halt/delisted를 차단합니다.
- rankings_store.py는6개 목록을 한 JSON으로 원자적 교체하고 last_success/last_verified·최근30개 이력을 유지합니다. unavailable시 과거 결과·실패 원인을 표시합니다.
- API 세션 보호, 6개 카드·조건 근거·CSV, 읽기 전용 atlas_top10 MCP, 기존 예약·중복슬롯·예산·캐시 연결.
- CLI import-universe / analyze-file / run / status. 서버와 CLI의 단일 프로세스 잠금을 유지합니다.

## 실제 데이터 연결의 남은 과제

API키/구독·전 시장 가격/재무 권한·공식 status/holiday 공급자와 자동 마스터 갱신은 실측하지 않았습니다. collector가 제공하는 것은 Twelve Data 지정종목 또는 가져온 master 기반 조회입니다. KIS/DART/SEC 직접 수집, 정밀 공시 대사, 전체 기업행동 보정·금융업 모델·배당 히스토리 수집은 후속입니다. 외부 공급자 정규화 JSON을 CLI로 분석할 수 있습니다.

verified는 전 시장 마스터/당일 상태·달력·기업행동 검증·전략100% 완전평가가 모두 필요합니다. default watchlist와 현재 collector만으로 이를 달성했다고 보고하지 않습니다. 알파 판별불가가 있으면 점수는 하한으로 표시하고 coverage에서 완전평가로 집계하지 않습니다.

## 검증

[TESTING](../../TESTING.md)의 실행 명령과 실제 검사 범위를 확인하세요. 가짜 공급자 응답/합성 수학 벡터·로컬 HTTP·stdio/MCP·DOM을 검증했습니다. 실제 시세/인증/수익성, macOS LaunchAgent·Safari/Chrome 실제 화면은 미검증입니다.

변경시 src를 수정하고 build.py로 시작.html을 생성한 뒤 CHECKSUMS를 갱신합니다. 새 API/설정/보류 정책과 sourceStatus를 함께 갱신하세요. 키·운영 DB·runtime을 Git에 저장하지 않습니다. broker는 보존 코드이며 기본 계좌/주문은 비활성입니다.
