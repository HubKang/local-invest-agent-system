# Local Invest Agent System

이 저장소는 로컬 투자 에이전트 시스템의 실행 프로그램을 관리한다.

## 목적

이 시스템은 GitHub Second Brain 저장소에 저장된 에이전트 역할 문서와 투자 지식 파일을 읽고, LM Studio에서 실행 중인 로컬 LLM을 호출하여 역할별 투자 에이전트를 실행하는 것을 목표로 한다.

## 전체 구조

- GPT: 시스템 설계자이자 최종 검토자
- Codex: 실행 프로그램과 관리화면 개발자
- LM Studio: 로컬 LLM 실행 환경
- local-invest-agent-brain: 에이전트 지식 저장소
- local-invest-agent-system: 에이전트 실행 프로그램

## 주요 기능

1. 설정 파일 읽기
2. Second Brain의 Markdown 파일 읽기
3. LM Studio 로컬 LLM 호출
4. 역할별 Agent 실행
5. Agent 결과 Markdown 저장
6. 향후 관리화면에서 Agent 제어

## 초기 실행 목표

초기 버전에서는 웹 관리화면을 만들기 전에 콘솔에서 다음 흐름을 먼저 구현한다.

1. 설정 파일 로딩
2. 오늘의 입력 파일 읽기
3. Agent 역할 문서 읽기
4. LM Studio 로컬 LLM 호출
5. 결과를 output 폴더에 Markdown으로 저장

## 주의사항

이 시스템은 투자 판단을 보조하기 위한 도구이다.
자동 매수, 자동 매도, 투자 실행 기능은 초기 버전에 포함하지 않는다.
최종 투자 판단은 반드시 사용자가 직접 수행한다.
