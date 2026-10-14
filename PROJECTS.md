# Project01~04 — 전체 프로젝트

번호는 고정 식별자이며 소제목은 기능 설명이다. 저장소 URL 이름 변경은 아직 미완료다.
현재 연결은 아래 실제 저장소를 사용하며, 목표 이름의 새 URL이 존재한다고 가정하지 않는다.
정리일: 2026-10-14. 프로젝트03 번호는 이번 정리에서 퀀트 프로젝트에 배정했고,
프로젝트04는 이전 사용자의 AMS 업로드 지정에 맞췄다.

| 번호 · 소제목 | 현재 저장소 | 통일할 저장소 이름 | 현재 개발 기준 |
| --- | --- | --- | --- |
| 01 · 인프라 자동화·자산·IP 관리 | [ChatGPT-Project01](https://github.com/bedeul95/ChatGPT-Project01) | Project01-Infra-Automation | 최신 코드 PR #11 / 20261008.9; main은 20260928.6 |
| 02 · BOTC 자동 이야기꾼 게임 | [project002](https://github.com/bedeul95/project002) | Project02-BOTC-AutoST | main / TypeScript 게임 서버 + Expo |
| 03 · 퀀트 조회·분석 플랫폼 | [project](https://github.com/bedeul95/project) | Project03-Quant-Research | 실행 소스/6개TOP10 구현; 실제 전체시장 feed 연결 대기 |
| 04 · AMS Syslog 전송·로그 보관 | [project-kiwi](https://github.com/bedeul95/project-kiwi) | Project04-AMS-Forwarding | 원본 AMS 4.1 스크립트와 설정 예제 |

## 공통 문서 구조

| 위치 | 읽는 목적 |
| --- | --- |
| README.md | 프로젝트 요약·현재 코드/검증/배포 상태 |
| project.json | 번호·제목·실제/목표 저장소·브랜치·버전·문서 경로의 구조화 정보 |
| AGENTS.md | 다음 개발자가 읽을 규칙과 인수인계 진입점 |
| docs/README.md | 모든 문서의 중앙 목차 |
| docs/guide/ | 개요·설정·실행/운영 가이드 |
| docs/development/ | 구조·인수인계·우선 과제·구조 개선 판단 |
| docs/reference/ | 전체 파일·함수/심볼·원본 대응 목록 |
| docs/archive/ | 기존 설명·설계 사본·과거 작업 기록 |

01/02 실행 코드는 해당 프로젝트의 현재 디렉터리 계약을 따른다. 공통 번호 체계를 맞추기 위해
애플리케이션 코드·데이터 스키마를 한 디렉터리 규칙으로 강제 변환하지 않는다.
현재 구조의 책임과 바꾸려면 함께 수정할 경로는 각 프로젝트 STRUCTURE_AUDIT에 기록했다.

## 다음 개발자의 시작 순서

실제 저장소/branch/HEAD 확인 → README → AGENTS → docs/development/HANDOFF →
ARCHITECTURE → 해당 기능 파일/테스트 → ROADMAP의 완료 조건 순서로 읽는다.
새 작업 결과에 코드 구현·로컬 검증·운영 적용 상태를 각각 기록한다.
루트 이름만 보고 다른 프로젝트의 기능·키·DB·배포 명령을 재사용하지 않는다.
