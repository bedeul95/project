# Project03 설정과 상태

원본 실행 환경 Python3.9+·Node18+, loopback127.0.0.1:8765, 추가 pip/npm 패키지 없음.
runtime/research/data-config.json은 API 키와 조회/예산 설정(권한600, 암호화 저장 아님),
latest.json·reports·cache는 결과/수집 자료다. 키/runtime을 Git에 포함하지 않는다.
기본 KST08:30 미국(화~토),18:30 한국(월~금);1회 모드는 저녁 양시장이다.
매일1~2회는 배치 횟수이며 공급자 HTTP 요청1~2개를 뜻하지 않는다.
기본 재무캐시24시간·실행/일별 크레딧 한도·최근30개 보고서를 확인한다.
실제 공급자 권한과 크레딧 단가는 계약/응답으로 확인해야 한다.
기본 데이터는 합성 예제이며 실제 주가·성과로 표시하지 않는다.

## 1.5.0 추가

- universeMode: watchlist(default) / master. 마스터 경로는 runtime/research/universe.json로 고정합니다. [계약](UNIVERSE.md)을 확인하세요.
- rankings.json: 최신6개 시도·last_success·last_verified, ranking-history: 최근30개 원자 스냅샷.
- maxCreditsPerRun 범위1~10,000,000, maxCreditsPerDay1~20,000,000. 기본1500/3000은 유지합니다. 높은 상한은 계약 전 시장 수집용이며 자동으로 예산을 높이지 않습니다.
- strategy별 전체시장 verified 게이트:100%완전평가, 당일 상태/마스터·공식 달력·기업행동 검증. 일반 collector는 split-consistent-only입니다.
- alpha defaults: 눌림목±3%, 거래대금2배, RSI30, 업종표본5, 확정배당2%, 재무결산200일. Research.generate의 alphaConfig 인자로 조정하며 산출결과에 설정을 저장합니다. UI설정/API설정 항목으로 노출하지 않았습니다.
