# 거래상태·거래일 마스터와 정규화 데이터 계약

## 상태 마스터

`research_cli.py import-universe FILE`은 서버/collector가 종료된 상태에서 실행합니다. 운영 폴더가 다르면 `--runtime-dir /absolute/path/runtime/research`를 command 앞에 넣습니다. CLI와 서버가 같은 폴더를 사용해야 합니다. importer는 날짜·ID·MIC·상태를 검증하고 원자적으로 `universe.json`을 저장합니다.

아래는 형식 설명용 **가상 입력**이며 실제 거래상태 자료가 아닙니다. source/calendarSource에 실제 공급자와 스냅샷 식별자를 넣고 최신 날짜로 갱신해야 합니다. complete=true는 실제 전체 유니버스 건수를 대사한 경우에만 설정합니다.

```json
{
  "schemaVersion": 1,
  "markets": {
    "KR": {
      "complete": false,
      "source": "EXAMPLE ONLY - exchange snapshot identifier",
      "calendarSource": "EXAMPLE ONLY - official completed session snapshot",
      "asOf": "2026-10-15",
      "expectedMarketDate": "2026-10-14",
      "entries": [{
        "id": "KR-005930-XKRX",
        "symbol": "005930",
        "mic": "XKRX",
        "status": "unknown",
        "statusAsOf": "2026-10-15",
        "securityType": "Common Stock",
        "source": "EXAMPLE ONLY - status feed snapshot"
      }]
    }
  }
}
```

- 시장: KR(KOSPI/KOSDAQ: XKRX/XKOS), US(XNAS/XNYS/XASE). KONEX는 전체시장 정책에서 제외합니다.
- 상태: active / halt / managed / delisted / noncompliant / unknown. active·Common Stock만 수집하며 나머지는 제외 건수로 남깁니다.
- 정규 ID: `시장-코드-MIC`; 한국 코드는 문자열6자리, 미국 티커는 대문자입니다. 각 시장1~20,000개, 중복ID 금지.
- expectedMarketDate는 공급자의 실제 거래일/휴장/DST 완료세션으로 결정합니다. weekday 추정을 공식 달력으로 표시하지 않습니다.
- statusAsOf가 분석일 마스터보다 과거이면 보류합니다. source는 인증정보·키·쿼리 URL을 포함하지 않습니다.
- 상태는 날짜 단위 계약입니다. 장중 실시간 halt 확인 기능을 구현한 것으로 해석하지 않습니다.
- 분석일 마스터가 오래되면 전체시장 verified 금지, 대상 상태가 오래되면 추천 보류합니다. 갱신은 공급자 파이프라인의 책임이며 현재 자동 공급자 downloader는 없습니다.

## 선택적 확정 배당 입력

마스터 entry 또는 정규화 stock의 `dividend` 필드를 다음처럼 제공합니다. 수익률은 0~1 비율, 지급률은 TTM 지급액/동기간 이익으로 공급자가 계산하고 confirmed는 과거 확정 지급 이력만 의미합니다.

```json
{"confirmed":true,"availableAt":"2026-10-15","asOf":"2026-10-14","yield":0.03,"yearsPaid":3,"payoutRatio":0.4,"source":"EXAMPLE ONLY - confirmed dividend snapshot"}
```

현재 Twelve Data collector에는 배당 히스토리 요청을 추가하지 않았습니다. 자료 미제공시 배당 신호는 unavailable이며 0점 미충족으로 바꾸지 않습니다. 최소3년 연속 지급 확인은 공급자에서 검증해 yearsPaid로 제공합니다.

## 정규화 가격·재무 직접 분석

`research_cli.py analyze-file FILE`은 `engine.js.validate`의 schemaVersion1 입력을 받습니다. 기존 `예제데이터.json`은 **synthetic=true인 가상 예제**입니다. 실제 데이터로 표기하지 않습니다.

추가 필드:

| 필드 | 의미 |
| --- | --- |
| analysisAsOf | 관측/분석 기준일, 미래 금지 |
| collectedAt | CLI가 실제 실행시각으로 설정 |
| universe.KR / universe.US | 위 markets 내부 메타데이터 |
| priceAdjustmentPolicy | 실제 분할·배당 등 가격/거래량/주식수 대사를 마친 공급자만 corporate-actions-verified 지정 |
| stocks[].dividend | 선택적 확정 배당 내역 |

stock당 OHLCV25~2,500개, 전체 최대20,000종목, Node 입력 최대512MiB, 처리시간 최대600초입니다. 전략 공통80개 완료 일봉, 신고가253개를 요구합니다. 일반 collector는400개 이력을 요청합니다. 실측 거래대금이 없으면 종가×거래량 근사치임을 신호 근거에 명시합니다.

보통주+현재 상태가 확인되어도 금융업/REIT는 보류합니다. 현재 전체시장 eligible 분모에서 금융업은 별도 모델 미충족으로 남으므로 full coverage를 달성하려면 향후 별도 모델/정책 버전이 필요합니다. 신규상장·자료부족도 완전평가로 집계하지 않습니다. 이 보수적 게이트는 전 종목 분석 성공을 과장하지 않기 위한 초기 정책입니다.

기업 점수는 기존70점 산식을 공유하고 새 순위에서는 필요한 구성자료100%·최근200일 이내 결산을 요구합니다. 기간 선택과 수정공시는 availableAt 기준입니다. 관측자료는 과거 공시일 검증 자료와 구분하며 기존 백테스트 차단 정책을 유지합니다. 200일은 초기 정책이며 회계주기별 후속 조정이 필요합니다.

리스크: ATR/종가>6%, 관측 최대252일 낙폭>40%, 부채/CFO>8, 이자보상<2 또는 최근 이벤트면 높음. ATR>3%, 낙폭>20% 또는 부채/CFO>4이면 보통, 나머지는 낮음. 필수 자료 미확보시 평가불가입니다. 낮음은 안전/수익 보증이 아닙니다.
