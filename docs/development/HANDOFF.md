# Project03 상세 개발 인수인계

1. current Git에는 개발 문서/원본 분석 인덱스만 있다. 다음 코드 작업은 먼저 원본1.4.0을 확인해 소스 이관 기준을 정한다.
2. frontend engine1.3.0·read MCP1.4.0·package1.4.0의 혼합 버전을 일괄 성공/최신 엔진으로 설명하지 않는다.
3. 기업안정70: 가치20·질20·안전20·성장10, 기술30: 거래량/횡보10·추세8·RSI/MACD6·ATR/볼린저6.
4. 필터/자료 누락·공시 관측일·완료 일봉·분할 이후80일 제한이 점수보다 우선한다. 누락을0이나 연환산으로 채우지 않는다.
5. Python collector는 cache/호출 예산·TwelveData fixed GET·시간대를 처리하고 Node engine은 UI/서버 동일 계산을 맡는다.
6. 4개 연속 분기 TTM, 전년 비교8분기·actual available date·retained market 자료 시각을 보존한다.
7. 전부 실패하면 이전 결과 유지, 부분 성공은 해당 배치의 성공 종목만 교체하고 미수집 이유를 표시한다.
8. macOS 예약은 실행 중인 서버가 검사하며 잠자기/종료를 깨우지 않는다. 동일슬롯/폴더중복·3시간내 보충 경계를 유지한다.
9. loopback Host/Origin/session·키 비노출·runtime 권한을 유지한다. MCP Reader는 저장 결과만 읽으며 collector 실행/주문 도구를 추가하지 않는다.
10. broker KIS 어댑터는 보존 코드다. 현재 우선은 계좌 없이 조회/분석이고 HTTP 주문 기본 비활성을 유지한다.
11. 수정 순서: market_data 정규화/예산 → engine 계산 → analyze bridge → read UI → saved-result MCP → 해당 tests.
12. 소스 수정 시 build.py로 시작.html을 다시 만들고 원본 해시/버전·테스트·실제 API 검증 여부를 각각 기록한다.

## 후속 우선순위

소스 Git 이관/버전 표기 → API 실제 최소표본 KR/US 권한/필드 → 공시 원자료/휴장 캘린더 →
MCP 실제 클라이언트 handshake → macOS 예약·재시작·브라우저 확인 순서다.
지정종목 순위를 전체 시장 순위로 해석하거나 검증 전 점수를 수익 보증으로 표현하지 않는다.

## 이번 구조 정리의 검증 범위

원본 ZIP의 파일/해시·Python 함수/클래스·주요 HTTP/collector/MCP/engine 선언을 확인하고 문서 링크/project.json을 검사했다. 원본 코드의 Git 이관·빌드/테스트·실제 API/계좌/주문 실행은 하지 않았다.
