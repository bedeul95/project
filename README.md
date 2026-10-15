# Project03 — 퀀트 조회·분석 플랫폼

기존 Atlas Quant v1.4.0 실행 소스를 이관하고 한국·미국 각각 저평가 / 기존 보조지표 / 첨부 전략 TOP 10을 구현했습니다. 버전은 리서치·MCP **1.5.0**, 기존 70+30 계산 산식 **1.3.0**입니다.

**실제 최신 전체시장 순위를 검증한 상태는 아닙니다.** API 키·구독 권한·공식 거래상태/거래일 마스터·기업행동 보정 검증을 연결해야 합니다. 기본 지정 종목 수집만으로 전체시장 순위를 표시하지 않습니다. 출처가 확인되지 않은 거래상태는 추천 보류합니다.

현재 검토 브랜치: `feature/project03-top10-20261015`. main 직접 반영은 보류되어 있으며 PR 검토 후 병합합니다.

## 실행

Python 3.9+와 Node.js 18+가 필요하며 pip/npm 추가 패키지는 없습니다.

```bash
git clone --branch feature/project03-top10-20261015 https://github.com/bedeul95/project.git "$HOME/Project03"
python3 "$HOME/Project03/server.py"
```

기존 clone을 사용하는 경우 실행 중인 서버를 종료한 뒤 해당 폴더에서 `git pull --ff-only` 하고 `python3 server.py`로 다시 실행하세요. 기존 ZIP 설치 폴더와 새 clone은 별도 경로이며, 키·운영 데이터를 Git으로 이관하지 않습니다.

브라우저의 **조회·자동분석** 화면에서 Twelve Data 키와 호출 예산을 저장합니다. 서버 주소는 http://127.0.0.1:8765 입니다. 키는 로컬 `runtime/research/data-config.json`(0600)에 저장됩니다. 기본 서버는 계좌/주문 기능을 비활성화합니다.

## 구현 범위

| 기능 | 구현 내용 |
| --- | --- |
| 6개 순위 | KR/US × value / legacy_technical / alpha_filters, 각 최대10개 |
| 기존 점수 | 기업70·기술30·총점100 유지, 각 순위에 별도 100점 환산 |
| 첨부 전략 | 10개 자체 근사 규칙, 조건·관측값·출처·날짜, 판별불가와 미충족 구분 |
| 거래상태 | 거래정지·관리·폐지·상장요건 미충족·상태미확인 제외, 상태 마스터 재확인 |
| 데이터 상태 | 전체시장/표본 구분, 커버리지·제외 사유·위험·과거 저장 결과 표시 |
| 운영 | KST08:30 미국 / 18:30 한국 예약, 예산·캐시·중복슬롯 잠금 |
| 결과 | 6개 카드, 계산 근거 펼치기, CSV, 최근30개 이력, 실패시 이전 결과 보존 |
| API/MCP | 세션 보호 API, `atlas_top10` 저장결과 읽기 전용 MCP |

알파 점수는 신호당10점입니다. 판별불가 신호가 있으면 확인된 점수를 **하한**으로 표시하고 상한·판별불가 개수를 병기합니다. 완전평가로 집계하지 않습니다. 금융·REIT 등 별도 모델 대상은 보류합니다. 저평가 계산은 기존 엔진과 동일하며 업종 표본 부족시 시장 비교로 전환한 사실을 근거에 표시합니다.

## 전체시장 데이터 연결

상태·휴장 정보를 시세 존재만으로 추정하지 않습니다. 공식/계약 공급자 자료를 [유니버스 계약](docs/guide/UNIVERSE.md)의 JSON 형식으로 준비하고 **서버 종료 후** 가져옵니다.

```bash
python3 research_cli.py import-universe /absolute/path/universe.json
python3 server.py
```

이후 설정의 '거래상태 마스터 전체' 모드에서 예약/수동 수집합니다. 기본 호출 한도는 작은 표본용입니다. 전체시장 계약 범위와 총 비용을 확인한 뒤 예산을 명시적으로 설정해야 합니다. 현재 KIS/DART/SEC 자동 수집기, 실시간 거래정지 공급자, 자동 마스터 갱신은 미구현입니다. 거래상태 마스터는 공급자 파이프라인에서 최신으로 갱신해야 합니다.

이미 정규화된 가격·재무·상태 자료가 있으면 같은 엔진으로 직접 분석할 수 있습니다.

```bash
python3 research_cli.py analyze-file /absolute/path/normalized-dataset.json
```

완전한 유니버스, 분석일의 상태·공식 거래일, 전략별100% 자료 충족, 검증된 기업행동 보정 증거가 갖춰져야 `verified`를 표시합니다. 기존 Twelve Data 수집기는 분할 전 이력을 제거하는 보수적 정책을 유지하므로 전체 기업행동 보정 검증 완료로 간주하지 않습니다.

## 검증과 개발

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.cjs
python3 build.py
```

[인수인계](docs/development/HANDOFF.md) · [구조](docs/development/ARCHITECTURE.md) · [검증](TESTING.md) · [실행/복구](docs/guide/RUNBOOK.md) · [문서 목차](docs/README.md) · [후속 과제](docs/development/ROADMAP.md)
