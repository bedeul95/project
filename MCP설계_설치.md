# ATLAS 1.4.0 · MCP 검토와 설치

2026-10-06 공식 문서를 확인해 수정했습니다. 앱의 플러그인 검색에 없다는 이유만으로 주식 MCP가 없거나 설치 불가능하다고 판단하면 안 됩니다. Twelve Data와 한국투자증권은 공식 MCP를 제공합니다. 현재 목적은 계좌 연결 전의 조회·분석이며, 필요한 연결을 아래처럼 구성합니다.

| 연결 | 역할 | 이번 버전 상태 | 인증/추가 호출 |
|---|---|---|---|
| ATLAS 조회 전용 MCP | 저장된 70/30 점수·PER/PBR·거래량·제외 사유·일봉 조회 | 서버 구현·설치 스크립트·자동 테스트 포함 | 데이터 키를 읽지 않음, 외부 API 호출 0 |
| Twelve Data 공식 원격 MCP | AI 대화에서 시세·재무·보조지표를 추가 조회 | 공식 URL 등록 옵션 포함, 실제 로그인은 미완료 | Twelve Data OAuth/자료 이용권한, 대화 중 조회는 추가 쿼터 사용 가능 |
| KIS Code Assistant 공식 MCP | 한국투자 API 검색·호출 코드 작성 | 공식 설치 방식 확인, 개발 보조용 선택 사항 | ATLAS 분석에 필요하지 않아 기본 등록하지 않음 |
| KIS Trading 공식 MCP | 증권 API 실행, 계좌·주문 포함 | 계좌 연결 단계로 보류 | 증권사 인증/계좌 필요 |
| DART·KRX 원자료, 다른 시세 제공사 | 공시 대사·한국 시장 자료 보완 | 향후 REST 어댑터 과제 | 이 패키지에서 MCP/어댑터 설치 완료로 표시하지 않음 |

MCP는 AI가 도구를 호출하는 연결 규약입니다. 매일 수집하는 프로그램의 REST API나 예약 실행을 대체하지 않습니다. 기존 수집 → 동일 70/30 엔진 → `latest.json` 저장 흐름을 유지하고, ATLAS MCP는 그 결과만 읽습니다. 웹 서버를 종료해도 저장된 보고서 조회는 가능합니다. 스케줄러는 별도로 실행되어야 다음 보고서가 만들어집니다.

## 맥미니에서 설치

1. Python 3.9+를 설치하고 ZIP을 풉니다. 점수 계산과 자동 분석에는 기존처럼 Node.js 18+도 필요합니다. ATLAS MCP 자체에는 추가 pip/npm 패키지가 없습니다.
2. 기존 버전을 사용 중이면 서버/자동 분석을 먼저 종료하고 기존 `runtime` 폴더를 개인 백업하세요. 새 프로그램 폴더로 옮기면 이전 `runtime`을 같은 위치에 복원하고 자동 분석 등록 및 MCP 등록 경로도 갱신해야 합니다. 키가 들어 있는 runtime은 외부로 보내지 마세요.
3. **MCP설치.command**를 실행합니다. Finder에서 제한되면 터미널에 `bash `를 입력하고 파일을 끌어놓아 실행합니다.
4. 설치기는 stdio 프로세스를 실제 실행해 도구5개/상태 조회를 검사하고, Codex CLI → 기존 Claude Desktop → 기존 Cursor 순으로 첫 클라이언트 하나에 등록합니다. 여러 클라이언트에 무조건 설치하지 않습니다.
5. 기존 클라이언트를 찾지 못하면 `runtime/mcp`에 설정 파일만 생성하고 **설치 완료가 아닌 템플릿 상태**라고 표시합니다. 사용하는 클라이언트의 MCP 설정에 `local-mcp.json`의 서버 항목을 병합하세요. Codex에는 `codex-local.toml`의 항목을 기존 설정과 중복되지 않게 추가할 수 있습니다.
6. 클라이언트를 재시작하고 `atlas_status`를 호출해 도구가 실제 보이는지 확인합니다. 보고서가 없다면 웹 프로그램의 **조회·자동분석**에서 먼저 수집하세요. 합성 예제를 실제 수집본인 것처럼 반환하지 않습니다.

클라이언트를 직접 지정하려면 프로젝트 폴더의 터미널에서 실행합니다.

```bash
python3 install_mcp.py --client codex
python3 install_mcp.py --client claude
python3 install_mcp.py --client cursor
```

Codex CLI가 없어도 데스크톱 앱의 설정에서 STDIO 서버를 직접 등록할 수 있습니다. 생성된 설정의 Python 절대 경로와 `args`를 사용하세요. 로컬 MCP는 해당 맥의 프로세스로 실행해야 하며 원격 웹 서비스에서 로컬 경로를 직접 열 수는 없습니다. 등록할 폴더를 이후 옮기지 마세요.

설치기는 기존 JSON 설정의 다른 서버/환경설정을 유지하고 변경 전 백업을 권한600으로 보관합니다. Codex는 공식 CLI로 등록하고 등록 결과를 다시 읽어 확인합니다. 같은 이름의 다른 설정이나 비활성 설정이 있으면 덮어쓰지 않고 중단합니다. 설정 파일이 손상됐거나 심볼릭 링크인 경우도 중단합니다. `installation-status.json`은 등록/템플릿/자체 검사를 구분하며 클라이언트의 실제 도구 표시와 원격 인증 성공을 주장하지 않습니다.

## Twelve Data 추가 연결

기본 ATLAS 연결만으로 저장된 분석을 AI에 질문할 수 있습니다. 대화 중 제공자 자료를 추가 조회하고 싶을 때 **TwelveData연결.command**를 실행합니다. 자동 등록은 Codex CLI 또는 Cursor를 지원합니다. Claude 등 다른 지원 클라이언트에서는 공식 원격 URL을 직접 등록합니다.

```text
https://mcp.twelvedata.com/mcp
```

Twelve Data 공식 원격 서버는 제공자 로그인으로 연결하는 방식입니다. 키를 소스나 MCP 설정에 붙여 넣지 않습니다. 클라이언트에서 OAuth 인증을 완료하고 조회 도구가 실제 나타나는지 확인해야 합니다. Codex 인증이 미완료인 경우:

```bash
codex mcp login atlas-twelvedata
```

연결을 확인하는 질문 예: “Twelve Data에서 AAPL의 최근 일봉을 조회해줘.” 한국 자료·재무 이력 등은 구독/거래소/종목별 권한을 확인해야 합니다. **공식 MCP의 직접 조회는 ATLAS의 실행당·일별 크레딧 한도 밖에서 발생**하므로, 매일1~2회 배치 원칙을 엄격히 유지하려면 ATLAS 조회 전용 MCP만 사용하세요. 추가 데이터 조회를 점수/보고서에 자동 섞지 않습니다. 원격 제공자 도구 목록은 제공자가 운영하며 ATLAS의 로컬 조회 전용 보장과 동일하게 취급하지 않습니다.

## 제공하는 도구

| 도구 | 입력 | 결과 |
|---|---|---|
| atlas_status | 없음 | 보고서/점수 존재 여부, 자료 출처·분석일, 저장 상태 |
| atlas_rankings | market=ALL/KR/US, limit=1~100, candidatesOnly | 총점 순위, 기업70/기술30, PER/PBR 등, 가격일·제외 사유 |
| atlas_stock_analysis | id | 한 기업의 상세 점수·지표·거래량·위험 사유 |
| atlas_price_history | id, limit=1~250 | 보고서에 저장된 완료 OHLCV 일봉 |
| atlas_collection_history | limit=1~30 | 수집 기록, 성공/실패 상태, 기록된 크레딧 |

예: “atlas_rankings로 미국 기업 상위10개를 보여주고 PER/PBR과 제외 사유를 설명해줘.” 이어서 반환된 id로 기업 상세를 요청합니다. `candidate`는 보고서의 분석일 당시 판정이고, `candidateUsableNow`는 현재 가격일 기준7일 초과/날짜 미확인/미래 날짜를 보류한 값입니다. `candidatesOnly=true`는 현재 사용 가능한 후보만 반환합니다. 최신 보고서라도 실시간 시세는 아니며 고득점이 검증된 투자 수익률을 뜻하지 않습니다.

이 버전에는 뉴스·산업 성장 전망·컨센서스를 반영하는 독립 평가 모듈이 없습니다. AI가 그럴듯한 설명을 붙여 점수에 이미 반영됐다고 표현하면 안 됩니다. 미래 성장 평가는 현재 TTM 매출/영업이익 추이 수준입니다. 공시 관측일 기반 자료의 과거 백테스트 차단도 유지합니다.

## 구현 범위

Python 표준 라이브러리로 newline JSON-RPC stdio 서버를 구현했습니다. MCP legacy2025-06-18(2025-03-26/2024-11-05 협상 호환)을 제공합니다. 2026-07-28의 새 stateless 규격을 지원한다고 광고하지 않습니다. dual-era 클라이언트의 `server/discover`에는 명시적 legacy 오류를 반환하므로 initialize 협상으로 전환할 수 있습니다. modern 전용 클라이언트는 이 버전에서 지원하지 않습니다.

도구는 고정된 research 폴더의 `latest.json`과 `collection-state.json`만 읽습니다. 키 설정·원시 캐시·증권 파일을 읽거나 임의 경로/URL을 실행하지 않습니다. 네트워크 포트/외부 공개/주문·계좌·파일쓰기·수집 실행 도구를 제공하지 않습니다. 읽는 두 파일의 심볼릭 링크는 거부하고, 메시지64KiB/보고서16MiB/조회 행·일봉 수를 제한합니다. 원본에 예상하지 않은 필드가 있어도 반환용 필드만 선택합니다. MCP 클라이언트에는 조회 결과가 전달되므로 자료 이용권한과 공유 범위는 사용 중인 클라이언트 기준으로 관리하세요.

KIS 코딩도우미는 나중에 KIS 조회 어댑터를 개발할 때 선택할 수 있습니다. 공식 문서의 Node/npx 방식은 `@koreainvestment/kis-code-assistant-mcp`입니다. 이 버전은 패키지를 내려받거나 실행하지 않았으며, 공식 트레이딩 MCP의 주문 도구도 등록하지 않습니다.

## 공식 근거 · 확인일2026-10-06

- Twelve Data 공식 MCP, 원격 URL·OAuth·Codex 설정: https://github.com/twelvedata/mcp
- 한국투자증권 MCP 구분: https://apiportal.koreainvestment.com/tools
- KIS 공식 연결 설명: https://github.com/koreainvestment/open-trading-api/tree/main/MCP
- Codex MCP 등록/인증: https://learn.chatgpt.com/docs/extend/mcp?surface=cli
- MCP legacy stdio: https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
- MCP 새/이전 규격 호환: https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio

공식 문서 검토와 로컬 구현 검증을 완료했습니다. 실제 맥미니의 클라이언트 등록·Twelve Data OAuth·실제 제공자 응답은 아직 검증하지 않았습니다. 프로그램 ZIP 제공과 사용자 기기에 설치 완료를 구분합니다.
