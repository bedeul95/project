# 저장소 이름·소제목 통일과 URL 전환

## 실제 상태

README 제목·번호·project.json·전체 인덱스는 통일했다. 저장소 URL 이름/description 설정 변경은
현재 연결의 기능에 없고 브라우저 설정 접근이 타임아웃되어 실행하지 못했다.
아래는 구체적인 변경 대상과 검증 절차다. rename 완료라고 표시하지 않는다.

| 기존 name | 목표 name | 소제목 |
| --- | --- | --- |
| ChatGPT-Project01 | Project01-Infra-Automation | Project01 — 인프라 자동화·자산·IP 관리 |
| project002 | Project02-BOTC-AutoST | Project02 — BOTC 자동 이야기꾼 게임 |
| project | Project03-Quant-Research | Project03 — 퀀트 조회·분석 플랫폼 |
| project-kiwi | Project04-AMS-Forwarding | Project04 — AMS Syslog 전송·로그 보관 |

## 이름 변경 실행 절차

GitHub CLI가 설치되고 bedeul95의 저장소 관리 권한으로 인증된 환경에서 실행한다.
공식 명령: [rename](https://cli.github.com/manual/gh_repo_rename), [description 편집](https://cli.github.com/manual/gh_repo_edit).

```bash
gh repo rename Project01-Infra-Automation --repo bedeul95/ChatGPT-Project01 --yes
gh repo rename Project02-BOTC-AutoST --repo bedeul95/project002 --yes
gh repo rename Project03-Quant-Research --repo bedeul95/project --yes
gh repo rename Project04-AMS-Forwarding --repo bedeul95/project-kiwi --yes
gh repo edit bedeul95/Project01-Infra-Automation --description 'Project01 | 인프라 자동화·자산·IP 관리'
gh repo edit bedeul95/Project02-BOTC-AutoST --description 'Project02 | BOTC 자동 이야기꾼 게임'
gh repo edit bedeul95/Project03-Quant-Research --description 'Project03 | 퀀트 조회·분석 플랫폼'
gh repo edit bedeul95/Project04-AMS-Forwarding --description 'Project04 | AMS Syslog 전송·로그 보관'
```

동일 목표 이름이 이미 있으면 덮어쓰거나 삭제하지 않는다. 기존/변경 후 저장소 ID가 같은지 확인한다.
이름 변경은 프로젝트01 최신 개발 PR을 병합하는 작업과 별개다.

## 참조와 실행 의존성

- Project01: AWX SCM URL·문서 링크·반입/download 경로·로컬 origin을 확인한다. 운영 AWX 설정은 운영 적용 작업 때 따로 수정한다.
- Project02: scripts/deploy/go-live-project02.sh의 저장소 확인은 구/신 URL을 모두 허용하도록 준비한다. 이미 설치된 구버전 스크립트는 먼저 현재 origin에서 업데이트를 받아야 한다.
- Project03: 원본 설치 폴더를 옮기면 macOS LaunchAgent 경로도 다시 등록해야 한다. GitHub rename과 로컬 폴더 이동을 같은 작업으로 취급하지 않는다.
- Project04: 스크립트는 실제 배포 위치에서 servers.conf/.ams_forwarding을 찾는다. 저장소 이름으로 운영 경로를 바꾸지 않는다.

변경 후 clone/pull·main/개발 branch·PR·문서 링크를 확인하고 project.json의 actualRepository와
repositoryRenameStatus, PROJECTS의 실제 링크를 함께 갱신한다. 목표 이름의 URL로 미리 치환하지 않는다.
