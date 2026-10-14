# 실행·자동분석·복구

1. Python3.9+ / Node18+ 확인. `python3 server.py` 또는 `bash 서버로실행.command` 실행.
2. http://127.0.0.1:8765 의 조회·자동분석 화면에서 Twelve Data 키·예산 저장. 빈 키는 기존 키 유지.
3. 공식 거래상태 마스터를 준비해 서버 종료 후 `python3 research_cli.py import-universe /absolute/path/universe.json` 실행. 전체시장 키/마스터가 없으면6개 카드가 미산출/표본 상태인 것이 정상입니다.
4. 서버 재시작 후 범위 선택, 지금 양 시장 분석. 완료 후 상태·결과 새로고침. 데이터 API/추가 근거가 없으면 값을 추정하지 않습니다.
5. 자동실행: macOS에서 `python3 install_scheduler.py`. 오전08:30 미국(화~토) / 오후18:30 한국(월~금). 절전/종료 중 실행 보증 없음,3시간 보충·중복슬롯 방지. 해제는 `python3 install_scheduler.py --remove`.
6. 읽기전용 MCP: `python3 install_mcp.py --help`로 클라이언트 옵션 확인 후 등록. atlas_top10에는 KR/US와 value/legacy_technical/alpha_filters를 전달합니다. 실제 사용자 클라이언트 연결은 로컬에서 확인해야 합니다.

## API

`GET /api/research/rankings?market=KR&strategy=value&as_of=YYYY-MM-DD`

as_of는 선택사항, 저장된 market-close 날짜입니다. `format=csv`로 내보냅니다. Host/Origin 및 X-Atlas-Session 보호를 적용합니다. 세션은 서버가 열린 화면에 제공하며 Git·로그에 저장하지 않습니다. 코드/README에 세션·키를 하드코딩하지 마세요.

## 서버 없는 수동 분석

```bash
python3 research_cli.py run --market ALL
python3 research_cli.py analyze-file /absolute/path/normalized-dataset.json
python3 research_cli.py status
```

CLI는 종료해야 서버를 같은 runtime으로 실행할 수 있습니다. run의 exit2는 partial/failed이며 상태/수집 로그를 확인합니다. API 호출수 제한·키 없음·status 미확인은 성공으로 숨기지 않습니다.

## 복구

실패시 runtime/research의 reports·ranking-history와 last_success/last_verified를 보존합니다. unavailable 시 API는 이전 성공본을 과거 결과로 표시하고 최신 실패 이유를 반환합니다. 저장파일 손상시 서버를 종료하고 보고서를 백업한 뒤 검증된 스냅샷으로 복원합니다. 키/config를 공개 저장소에 올리지 마세요. 코드 rollback은 종료 후 이전 commit을 별도 clone으로 확인하고 기존 runtime을 백업한 뒤 수행합니다. 기존 runtime의 collector.lock은 파일 삭제 대신 실행중 프로세스를 정상 종료해 해제합니다.
