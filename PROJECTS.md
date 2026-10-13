# 프로젝트 전체 안내

문서 점검일: 2026-10-14 (KST). 저장소 접근 결과와 실제 파일을 기준으로 작성했다.
각 저장소 루트의 `README.md`는 시작 안내, `docs/CODE_STRUCTURE.md`는 코드 지도,
`docs/DEVELOPMENT.md`와 `AGENTS.md`는 이어서 개발할 때 읽는 문서다.

| 저장소 | 프로젝트 속성 | 코드 기준 | 다음 작업 시작점 |
| --- | --- | --- | --- |
| [ChatGPT-Project01](https://github.com/bedeul95/ChatGPT-Project01) | 폐쇄망 인프라 자동화 포털 / Python·AWX·vCenter·React | main은 20260928.6. 최신 개발은 PR #11의 feature/ipam-vm-selection-filters-20260930 / 20261008.9 | 최신 기능 수정은 [PR #11](https://github.com/bedeul95/ChatGPT-Project01/pull/11) 브랜치에서 README → AGENTS → docs/DEVELOPMENT 순서로 확인 |
| [project002](https://github.com/bedeul95/project002) | BOTC 자동 이야기꾼 게임 / TypeScript·Socket.IO·Expo·SQLite | main | README → docs/CODE_STRUCTURE → docs/DEVELOPMENT |
| [project](https://github.com/bedeul95/project) | 코드가 없던 공개 예약 저장소. 이 안내 작성으로 문서 초기화 | main / 애플리케이션 미구현 | 프로젝트 목적과 기술 스택부터 확정 |
| [project-kiwi](https://github.com/bedeul95/project-kiwi) | 코드가 없던 비공개 예약 저장소. 이 안내 작성으로 문서 초기화 | main / 애플리케이션 미구현 | 이름만으로 Kiwi 서비스라고 가정하지 말고 목적부터 확정 |

## 브랜치와 작업 상태

- Project01 최신 작업을 `main`에 이미 들어간 기능으로 설명하지 않는다. 개발 브랜치의 코드 변경을 문서 작성 때문에 병합하거나 배포하지 않는다.
- Project02의 `playable`은 핵심 역할 데이터가 있다는 뜻이다. 모든 역할의 공식 판정이 완전 자동화되었다는 보증은 아니다.
- `project`와 `project-kiwi`에는 이번 문서 외 실행 코드·설정·테스트가 없다.
- 이전 대화에 등장한 프로젝트4는 현재 접근 가능한 저장소 목록에서 식별하지 못했다. 기존 4개 저장소를 프로젝트4로 임의 대응시키지 않는다. 정확한 저장소가 확인되면 이 표와 해당 저장소 문서를 함께 갱신한다.

## 다음 대화에서 개발을 이어가는 방법

저장소 URL과 작업할 기능을 지정하면 된다. 다음 작업자는 현재 HEAD와 미커밋 변경을 확인하고
그 저장소의 `AGENTS.md`·`docs/DEVELOPMENT.md`를 읽은 다음 관련 코드와 테스트를 연다.
이 문서는 대화 기억을 대신하는 지속적인 인덱스이며, 새로운 커밋의 사실이 이전 설명보다 우선한다.
현재 구현, 검증 결과, 운영 적용 여부를 별도로 기록한다.
