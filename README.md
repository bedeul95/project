# Project03 — 퀀트 조회·분석 플랫폼

맥미니에서 한국/미국 지정 종목 시세·재무를 조회하고 기업70+기술30으로 분석한다.

> **개발 재개:** [AGENTS](AGENTS.md) → [HANDOFF](docs/development/HANDOFF.md) → [상세 구조](docs/development/ARCHITECTURE.md) → [후속 과제](docs/development/ROADMAP.md).
> 전체 프로젝트 [PROJECTS](PROJECTS.md) · 전체 문서 [docs/README](docs/README.md) · 구조화 정보 [project.json](project.json).

## 현재 기준

| 항목 | 내용 |
| --- | --- |
| 현재 저장소 | https://github.com/bedeul95/project |
| 목표 저장소 이름 | Project03-Quant-Research — URL 이름 변경 미완료 |
| 브랜치 | main |
| 버전/자료 | 원본 패키지 1.4.0 / 계산 엔진 1.3.0 |
| 문서 기준 | 2026-10-14 / 정리 전 HEAD 803fdec842d75d7f543c608e033e235bece0058a |
| 상태 | 원본 atlas-quant-mac-v1.4.0.zip을 분석했다. 이 공개 저장소에는 문서/원본 인덱스만 있고 실행 소스는 아직 이관하지 않았다. |

## 기능과 이어서 개발할 위치

| 영역 | 확인한 구현 | 후속 시작점 |
| --- | --- | --- |
| 수집 | Twelve Data 조회·캐시·예산·TTM·예약 | market_data.py |
| 분석 | 기업70+기술30·가시성/자료 제한 | engine.js, analyze.cjs |
| 조회 MCP | 저장된 분석만 stdio 조회·version1.4.0 | mcp_server.py |
| 제외 범위 | 계좌/주문 기본 비활성·실제 인증 미검증 | broker 어댑터를 켜지 않기 |

## 실행·구조·현재 과제

- [개요](docs/guide/OVERVIEW.md): 기능/제품 범위와 실제 확인 근거
- [설정](docs/guide/CONFIGURATION.md): 환경변수·상태 파일·보존 정책
- [실행 가이드](docs/guide/RUNBOOK.md): 시작/배포/검증/복구 단계
- [구조 분석](docs/development/STRUCTURE_AUDIT.md): 실제 정리와 디렉터리 이동 의존성
- [파일 목록](docs/reference/SOURCE_INDEX.md) · [함수/심볼](docs/reference/SYMBOLS.md)
- [이름 변경/참조 전환](docs/reference/REPOSITORY_NAMING.md): actual/target URL과 절차

다음 작업자는 branch/HEAD와 현재 코드를 다시 확인한다. 구현된 코드·로컬 검사·운영 적용 여부를 각각 기록한다.
