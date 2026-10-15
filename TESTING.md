# Project03 1.5.0 검증 기록

2026-10-15: **Python39개 + Node31개 = 총70개 통과**. 가상 공급자 응답과 합성 수학 벡터를 사용했으며 실제 최신 주가·전체시장 순위를 검증한 결과가 아닙니다.

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.cjs
python3 build.py
```

검증 범위:

- 원본32개 파일 SHA256 일치, 원본 이관 commit18395fc와 기능 수정 분리.
- 원본70/30·Wilder RSI/ATR/MACD·공시시점·TTM·미래데이터·분할후 이력·수집예산/캐시·예약중복·HTTP 세션 방어·기본주문 비활성 회귀.
- KR/US ×3종 독립순위·최대10·점수척도·동점 재현성·목록중복 허용.
- managed/halt/delisted/noncompliant/unknown·오래된 상태·전체유니버스 누락·합성자료의 full-market 표시 차단.
- 기술 목록의 재무부족은 null/위험평가불가. 알파 신고가253일/배당 미확보는 unavailable, 하한·상한·판별불가 개수로 표시.
- 한국시간 재무관측일과 미국 완료가격일 분리. 상태 마스터 기반 collector에서 관리종목은 HTTP 요청 전 제외하고6개 결과를 저장.
- API 인증/잘못된 시장·CSV formula 방어·MCP 저장자료 전용·키 비노출.
- 원자발행/실패후 이전순위 과거표시·신규결과없음·stale·최근30개 이력 보존.
- DOM에서6개 카드·부분상태·HTML escape·세션 헤더 확인. 기존 화면/백업/모의 기능 회귀.
- 별도 CLI analyze-file 가상입력 → 같은 Node engine →6개 저장 목록의 실행 경로 확인.
- Python compile, JavaScript 구문, mac command bash 구문, MCP installer stdio initialize/tools/status 자체검사 통과.
- .github/workflows/test.yml은 동일 Python/Node 검사와 build.py 재생성 일치 검사를 수행하도록 추가.

미검증: Twelve Data 실제 API키/구독·한국/미국 전시장 권한/실측 사용량·공식 halt/휴장 feed·공시 원자료/배당/기업행동 대사·수익성, 사용자 Mac의 실제 MCP 클라이언트·LaunchAgent/절전·Safari/Chrome 시각 결과. 이 환경의 headless Chromium 실행 바이너리가 없어 실제 브라우저 시각 검사는 수행하지 못했습니다. DOM 검사와 실제 HTTP/stdio 검사는 별도로 완료했습니다.
