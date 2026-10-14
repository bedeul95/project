# Project03 구조 정리 분석

현재 Git은 문서 전용이다. 원본에는 Python HTTP/collector/broker/MCP와 Node engine/UI/build/test가 있다.
실행 진입점·설치 command의 __file__/root와 Node require 경로가 연결되므로 backend/frontend 강제 이동은 이관 후 별도 수정한다.
문서/원본 인덱스·번호 메타데이터를 공통 구조로 만들었다. 원본 runtime/API 키를 공개 Git에 복사하지 않았다.
소스 이관 때 src(원본)·시작.html(생성 결과)·tests·runtime(운영 제외)·mac command(설치 경로)를 분리해 설명한다.
