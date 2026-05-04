from datetime import datetime
from pathlib import Path
from typing import Tuple
import re
import shutil

from src.file_store import read_text_file, write_text_file
from src.agent_runner import build_agent_prompt
from src.llm_client import LLMClient
from src.logger import get_logger


HANDOFF_OPEN_TAG = "<HANDOFF_PACKET>"
HANDOFF_CLOSE_TAG = "</HANDOFF_PACKET>"


def ensure_not_empty(name: str, content: str) -> None:
    """
    빈 응답이 저장되는 문제를 방지합니다.
    """
    if content is None or content.strip() == "":
        raise ValueError(f"{name} is empty.")


def get_today_string() -> str:
    """
    오늘 날짜 문자열을 반환합니다.
    """
    return datetime.now().strftime("%Y-%m-%d")


def get_today_output_dir(config: dict) -> Path:
    """
    오늘 날짜 기준 system output 디렉터리를 반환합니다.
    """
    today = get_today_string()
    output_dir = Path(config["paths"]["output_dir"]) / today
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def get_today_brain_daily_dir(config: dict) -> Path:
    """
    오늘 날짜 기준 Second Brain daily 디렉터리를 반환합니다.

    예:
    ../local-invest-agent-brain/daily/2026-05-04
    """
    today = get_today_string()
    brain_repo_path = Path(config["paths"]["brain_repo_path"])
    daily_dir = brain_repo_path / "daily" / today
    daily_dir.mkdir(parents=True, exist_ok=True)
    return daily_dir


def extract_handoff(result: str, agent_name: str) -> str:
    """
    Agent 결과에서 <HANDOFF_PACKET>...</HANDOFF_PACKET> 구간만 추출합니다.

    중요:
    - Handoff 추출 실패 시 full report를 대신 사용하지 않습니다.
    - full report를 handoff로 넘기면 뒤 단계 context가 폭증하기 때문입니다.
    """
    ensure_not_empty(f"{agent_name} full result", result)

    pattern = re.compile(
        rf"{re.escape(HANDOFF_OPEN_TAG)}(.*?){re.escape(HANDOFF_CLOSE_TAG)}",
        re.DOTALL | re.IGNORECASE,
    )

    match = pattern.search(result)

    if not match:
        raise ValueError(
            f"{agent_name} result does not contain a valid HANDOFF_PACKET block. "
            f"Expected tags: {HANDOFF_OPEN_TAG} ... {HANDOFF_CLOSE_TAG}"
        )

    handoff = match.group(1).strip()
    ensure_not_empty(f"{agent_name} handoff packet", handoff)

    return handoff


def repair_handoff_packet(
    config: dict,
    agent_name: str,
    full_result: str,
    handoff_schema: str,
) -> str:
    """
    Agent가 <HANDOFF_PACKET> 태그를 누락했을 때,
    full_result를 바탕으로 Handoff Packet만 다시 생성합니다.

    이 함수는 full report 전체를 다음 Agent에게 넘기는 문제를 방지하기 위한
    안전장치입니다.
    """
    logger = get_logger(config)

    logger.warning(
        f"[{agent_name}] Handoff packet not found. "
        f"Trying to repair handoff packet from full result."
    )

    system_prompt = """
당신은 Agent 결과에서 다음 단계로 넘길 Handoff Packet만 재작성하는 보조자입니다.
새로운 분석을 추가하지 말고, 제공된 원문에서 핵심 정보만 추출하십시오.
반드시 요청된 표 형식만 출력하십시오.
"""

    user_prompt = f"""
아래는 {agent_name}가 생성한 전체 결과입니다.
하지만 <HANDOFF_PACKET> 태그가 누락되었습니다.

아래 전체 결과를 바탕으로 다음 단계에 넘길 Handoff Packet만 다시 작성하십시오.

[요구되는 Handoff 형식]
{handoff_schema}

[작성 규칙]
- 표만 작성하십시오.
- 설명 문단을 추가하지 마십시오.
- <HANDOFF_PACKET> 태그는 쓰지 마십시오.
- 원문에 없는 내용을 새로 지어내지 마십시오.
- 매수/매도 명령을 쓰지 마십시오.

[전체 결과]
{full_result}
"""

    llm = LLMClient(config)
    repaired = llm.chat(system_prompt, user_prompt)

    ensure_not_empty(f"{agent_name} repaired handoff packet", repaired)

    logger.info(
        f"[{agent_name}] Repaired handoff packet length: "
        f"{len(repaired)} characters"
    )
    logger.info(
        f"[{agent_name}] Repaired handoff preview: "
        f"{repaired[:200].replace(chr(10), ' ')}"
    )

    return repaired.strip()


def run_single_agent_workflow(config: dict, agent_name: str, task: str) -> str:
    """
    단일 Agent 실행용 workflow입니다.

    사용 예:
    python main.py --workflow single --agent research_agent
    """
    logger = get_logger(config)

    today_input_file = config["paths"]["today_input_file"]
    today_input = read_text_file(today_input_file)

    logger.info(f"[{agent_name}] Single agent workflow started.")
    logger.info(f"[{agent_name}] Today input length: {len(today_input)} characters")

    system_prompt, user_prompt = build_agent_prompt(
        brain_repo_path=config["paths"]["brain_repo_path"],
        agent_name=agent_name,
        task=task,
        today_input=today_input,
    )

    logger.info(f"[{agent_name}] System prompt length: {len(system_prompt)} characters")
    logger.info(f"[{agent_name}] User prompt length: {len(user_prompt)} characters")

    llm = LLMClient(config)
    result = llm.chat(system_prompt, user_prompt)

    ensure_not_empty(agent_name, result)

    output_dir = get_today_output_dir(config)
    output_file = output_dir / f"{agent_name}_result.md"

    write_text_file(str(output_file), result)

    logger.info(f"[{agent_name}] Single agent result saved: {output_file}")
    logger.info(f"[{agent_name}] Result length: {len(result)} characters")

    return str(output_file)


def run_agent_with_context(
    config: dict,
    agent_name: str,
    task: str,
    context: str,
    output_file_name: str,
    handoff_file_name: str,
    handoff_schema: str | None = None,
) -> Tuple[str, str, str, str]:
    """
    하나의 Agent를 실행합니다.

    반환값:
    - full_file_path
    - handoff_file_path
    - full_result
    - handoff_packet
    """
    logger = get_logger(config)

    logger.info(f"[{agent_name}] Agent execution started.")
    logger.info(f"[{agent_name}] Context length: {len(context)} characters")
    logger.info(f"[{agent_name}] Task length: {len(task)} characters")

    system_prompt, user_prompt = build_agent_prompt(
        brain_repo_path=config["paths"]["brain_repo_path"],
        agent_name=agent_name,
        task=task,
        today_input=context,
    )

    logger.info(f"[{agent_name}] System prompt length: {len(system_prompt)} characters")
    logger.info(f"[{agent_name}] User prompt length: {len(user_prompt)} characters")

    llm = LLMClient(config)
    full_result = llm.chat(system_prompt, user_prompt)

    ensure_not_empty(f"{agent_name} full result", full_result)

    try:
        handoff_packet = extract_handoff(full_result, agent_name)
    except ValueError as error:
        logger.warning(f"[{agent_name}] {error}")

        if handoff_schema is None:
            raise

        handoff_packet = repair_handoff_packet(
            config=config,
            agent_name=agent_name,
            full_result=full_result,
            handoff_schema=handoff_schema,
        )

    ensure_not_empty(f"{agent_name} handoff packet", handoff_packet)

    output_dir = get_today_output_dir(config)

    full_file = output_dir / output_file_name
    handoff_file = output_dir / handoff_file_name

    write_text_file(str(full_file), full_result)
    write_text_file(str(handoff_file), handoff_packet)

    logger.info(f"[{agent_name}] Full result saved: {full_file}")
    logger.info(f"[{agent_name}] Handoff packet saved: {handoff_file}")
    logger.info(f"[{agent_name}] Full result length: {len(full_result)} characters")
    logger.info(f"[{agent_name}] Handoff packet length: {len(handoff_packet)} characters")
    logger.info(
        f"[{agent_name}] Handoff preview: "
        f"{handoff_packet[:200].replace(chr(10), ' ')}"
    )

    return str(full_file), str(handoff_file), full_result, handoff_packet


def run_final_agent(
    config: dict,
    agent_name: str,
    context: str,
    task: str,
    output_file_name: str,
) -> str:
    """
    최종 결과만 생성하는 Agent 실행 함수입니다.

    Debate Moderator, Knowledge Curator처럼
    별도 Handoff Packet이 필요 없는 Agent에 사용합니다.
    """
    logger = get_logger(config)

    logger.info(f"[{agent_name}] Final agent execution started.")
    logger.info(f"[{agent_name}] Context length: {len(context)} characters")
    logger.info(f"[{agent_name}] Task length: {len(task)} characters")

    system_prompt, user_prompt = build_agent_prompt(
        brain_repo_path=config["paths"]["brain_repo_path"],
        agent_name=agent_name,
        task=task,
        today_input=context,
    )

    logger.info(f"[{agent_name}] System prompt length: {len(system_prompt)} characters")
    logger.info(f"[{agent_name}] User prompt length: {len(user_prompt)} characters")

    llm = LLMClient(config)
    result = llm.chat(system_prompt, user_prompt)

    ensure_not_empty(f"{agent_name} result", result)

    output_dir = get_today_output_dir(config)
    output_file = output_dir / output_file_name

    write_text_file(str(output_file), result)

    logger.info(f"[{agent_name}] Final agent result saved: {output_file}")
    logger.info(f"[{agent_name}] Final agent result length: {len(result)} characters")
    logger.info(
        f"[{agent_name}] Final agent preview: "
        f"{result[:200].replace(chr(10), ' ')}"
    )

    return str(output_file)


def run_final_debate_agent(
    config: dict,
    context: str,
    task: str,
    output_file_name: str,
) -> str:
    """
    Debate Moderator Agent 실행 함수입니다.
    """
    return run_final_agent(
        config=config,
        agent_name="debate_moderator_agent",
        context=context,
        task=task,
        output_file_name=output_file_name,
    )


def create_daily_readme(
    config: dict,
    brain_daily_dir: Path,
    copied_files: list[str],
) -> str:
    """
    Second Brain daily 폴더에 README.md를 생성합니다.
    """
    today = get_today_string()

    file_list = "\n".join([f"- {file_name}" for file_name in copied_files])

    content = f"""# Daily Agent Report Archive - {today}

이 폴더는 {today}에 실행된 로컬 투자 에이전트 회의 결과를 저장합니다.

## 포함된 파일

{file_list}

## 파일 설명

- `01_research_agent_full.md`: Research Agent의 상세 후보 발굴 보고서
- `01_research_agent_handoff.md`: Analyst Agent에게 전달된 Research 핵심 패킷
- `02_analyst_agent_full.md`: Analyst Agent의 상세 분석 보고서
- `02_analyst_agent_handoff.md`: Risk Manager Agent에게 전달된 Analyst 핵심 패킷
- `03_risk_manager_agent_full.md`: Risk Manager Agent의 상세 리스크 검토 보고서
- `03_risk_manager_agent_handoff.md`: Debate Moderator Agent에게 전달된 Risk 핵심 패킷
- `04_debate_moderator_agent_result.md`: 최종 투자 회의 정리 결과
- `05_knowledge_curator_agent_result.md`: 재사용 가능한 인사이트와 지식 후보 정리 결과

## 주의사항

이 폴더의 내용은 투자 판단을 보조하기 위한 기록입니다.
최종 투자 판단과 매매 실행은 반드시 사용자가 직접 수행해야 합니다.

Knowledge Curator가 제안한 내용은 아직 검증된 규칙이 아니라 업데이트 후보입니다.
검토 없이 `validated` 또는 `rules` 폴더에 자동 반영하지 마십시오.
"""

    readme_file = brain_daily_dir / "README.md"
    write_text_file(str(readme_file), content)

    return str(readme_file)


def copy_output_to_brain_daily(config: dict) -> str:
    """
    system output/YYYY-MM-DD 폴더의 결과 파일을
    brain_repo_path/daily/YYYY-MM-DD 폴더로 복사합니다.

    아직 Git commit/push는 수행하지 않습니다.
    """
    logger = get_logger(config)

    output_dir = get_today_output_dir(config)
    brain_daily_dir = get_today_brain_daily_dir(config)

    if not output_dir.exists():
        raise FileNotFoundError(f"Output directory not found: {output_dir}")

    copied_files: list[str] = []

    for source_file in sorted(output_dir.glob("*.md")):
        if source_file.name == "README.md":
            continue

        target_file = brain_daily_dir / source_file.name
        shutil.copy2(source_file, target_file)
        copied_files.append(source_file.name)

        logger.info(f"[brain_daily] Copied: {source_file} -> {target_file}")

    if not copied_files:
        raise ValueError(f"No markdown files found to copy in: {output_dir}")

    readme_file = create_daily_readme(
        config=config,
        brain_daily_dir=brain_daily_dir,
        copied_files=copied_files,
    )

    logger.info(f"[brain_daily] README created: {readme_file}")
    logger.info(f"[brain_daily] Copied output files to: {brain_daily_dir}")

    return str(brain_daily_dir)


def run_debate_workflow(config: dict) -> str:
    """
    Research → Analyst → Risk Manager → Debate Moderator → Knowledge Curator 순서로 실행합니다.

    핵심 구조:
    - Research, Analyst, Risk Manager는 Full Report와 Handoff Packet을 함께 생성합니다.
    - Full Report는 보관용입니다.
    - 다음 Agent에게는 Handoff Packet만 전달합니다.
    - Handoff 태그 누락 시 repair_handoff_packet()으로 복구합니다.
    - Debate Moderator는 Handoff Packet만 비교합니다.
    - Knowledge Curator는 최종 회의 결과를 재사용 가능한 지식 후보로 정리합니다.
    - 마지막으로 output 결과를 Second Brain daily 폴더로 복사합니다.
    """
    logger = get_logger(config)

    logger.info("[debate_workflow] Debate workflow started.")

    today_input_file = config["paths"]["today_input_file"]
    today_input = read_text_file(today_input_file)

    logger.info(f"[debate_workflow] Today input length: {len(today_input)} characters")

    # ------------------------------------------------------------------
    # 1. Research Agent
    # ------------------------------------------------------------------
    research_handoff_schema = """
| 종목 | 섹터 | 후보 선정 이유 | 근거 수준 | Analyst 확인 항목 |
|---|---|---|---|---|
"""

    research_task = f"""
오늘의 입력 데이터를 바탕으로 투자 후보 종목을 발굴하십시오.

반드시 아래 형식을 정확히 지키십시오.

# Full Report

다음 내용을 포함하여 상세 분석하십시오.

1. 시장 요약
2. 섹터별 흐름
3. 후보 종목별 선정 이유
4. 거래대금 특징
5. 근거 수준
6. 추가 확인 필요 사항

{HANDOFF_OPEN_TAG}

{research_handoff_schema}

{HANDOFF_CLOSE_TAG}

중요:
- 반드시 {HANDOFF_OPEN_TAG} 태그를 출력하십시오.
- 반드시 {HANDOFF_CLOSE_TAG} 닫는 태그를 출력하십시오.
- 태그를 누락하면 결과는 실패로 간주됩니다.
- Handoff Packet 안에는 표만 작성하십시오.
- 매수 추천은 하지 마십시오.
- 근거와 추측을 구분하십시오.
- 근거 수준은 A/B/C/D 중 하나로 표시하십시오.
- Full Report는 상세하게 작성하십시오.
"""

    (
        research_full_file,
        research_handoff_file,
        research_full,
        research_handoff,
    ) = run_agent_with_context(
        config=config,
        agent_name="research_agent",
        task=research_task,
        context=today_input,
        output_file_name="01_research_agent_full.md",
        handoff_file_name="01_research_agent_handoff.md",
        handoff_schema=research_handoff_schema,
    )

    # ------------------------------------------------------------------
    # 2. Analyst Agent
    # ------------------------------------------------------------------
    analyst_handoff_schema = """
| 종목 | Analyst 분류 | 긍정 근거 | 불확실성 | 손절 기준 후보 | Risk 확인 항목 |
|---|---|---|---|---|---|
"""

    analyst_context = f"""
[오늘의 원본 입력 데이터]
{today_input}

[Research Agent Handoff Packet]
{research_handoff}
"""

    analyst_task = f"""
Research Agent의 Handoff Packet을 바탕으로 후보 종목을 분석하십시오.

반드시 아래 형식을 정확히 지키십시오.

# Full Report

다음 내용을 포함하여 상세 분석하십시오.

1. 종목별 투자 검토 가능성
2. 차트 위치 해석
3. 거래대금 의미
4. 진입 조건
5. 관망 조건
6. 손절 기준 후보
7. 불확실성
8. 후속 확인 조건

{HANDOFF_OPEN_TAG}

{analyst_handoff_schema}

{HANDOFF_CLOSE_TAG}

중요:
- 반드시 {HANDOFF_OPEN_TAG} 태그를 출력하십시오.
- 반드시 {HANDOFF_CLOSE_TAG} 닫는 태그를 출력하십시오.
- 태그를 누락하면 결과는 실패로 간주됩니다.
- Handoff Packet 안에는 표만 작성하십시오.
- 최종 매수 판단을 내리지 마십시오.
- Analyst 분류는 검토 가능, 조건부 관심, 관망, 제외 중 하나로 작성하십시오.
- 손절 기준이 불명확하면 긍정 판단하지 마십시오.
- Full Report는 상세하게 작성하십시오.
"""

    (
        analyst_full_file,
        analyst_handoff_file,
        analyst_full,
        analyst_handoff,
    ) = run_agent_with_context(
        config=config,
        agent_name="analyst_agent",
        task=analyst_task,
        context=analyst_context,
        output_file_name="02_analyst_agent_full.md",
        handoff_file_name="02_analyst_agent_handoff.md",
        handoff_schema=analyst_handoff_schema,
    )

    # ------------------------------------------------------------------
    # 3. Risk Manager Agent
    # ------------------------------------------------------------------
    risk_handoff_schema = """
| 종목 | 주요 리스크 | 반대 논리 | 리스크 등급 | 제외 여부 | Debate 반영 사항 |
|---|---|---|---|---|---|
"""

    risk_context = f"""
[오늘의 원본 입력 데이터]
{today_input}

[Research Agent Handoff Packet]
{research_handoff}

[Analyst Agent Handoff Packet]
{analyst_handoff}
"""

    risk_task = f"""
Research Agent와 Analyst Agent의 Handoff Packet을 바탕으로 리스크를 검토하십시오.

반드시 아래 형식을 정확히 지키십시오.

# Full Report

다음 내용을 포함하여 상세 분석하십시오.

1. 종목별 손실 가능성
2. 반대 시나리오
3. 손절 기준 적정성
4. 고점 추격 위험
5. 재료 소멸 가능성
6. 시장 지수와의 충돌 가능성
7. 투자 검토를 보류해야 하는 조건

{HANDOFF_OPEN_TAG}

{risk_handoff_schema}

{HANDOFF_CLOSE_TAG}

중요:
- 반드시 {HANDOFF_OPEN_TAG} 태그를 출력하십시오.
- 반드시 {HANDOFF_CLOSE_TAG} 닫는 태그를 출력하십시오.
- 태그를 누락하면 결과는 실패로 간주됩니다.
- Handoff Packet 안에는 표만 작성하십시오.
- 리스크 등급은 Low, Medium, High, Critical 중 하나로 작성하십시오.
- 손절 기준이 불명확하면 High 이상으로 분류하십시오.
- High 또는 Critical 종목은 Debate에서 관심 분류가 어렵다는 점을 명시하십시오.
- 매수 또는 매도 명령을 내리지 마십시오.
- Full Report는 상세하게 작성하십시오.
"""

    (
        risk_full_file,
        risk_handoff_file,
        risk_full,
        risk_handoff,
    ) = run_agent_with_context(
        config=config,
        agent_name="risk_manager_agent",
        task=risk_task,
        context=risk_context,
        output_file_name="03_risk_manager_agent_full.md",
        handoff_file_name="03_risk_manager_agent_handoff.md",
        handoff_schema=risk_handoff_schema,
    )

    # ------------------------------------------------------------------
    # 4. Debate Moderator Agent
    # ------------------------------------------------------------------
    debate_context = f"""
[Research Agent Handoff Packet]
{research_handoff}

[Analyst Agent Handoff Packet]
{analyst_handoff}

[Risk Manager Agent Handoff Packet]
{risk_handoff}

[상세 보고서 파일 경로]
- Research Full Report: {research_full_file}
- Research Handoff: {research_handoff_file}
- Analyst Full Report: {analyst_full_file}
- Analyst Handoff: {analyst_handoff_file}
- Risk Full Report: {risk_full_file}
- Risk Handoff: {risk_handoff_file}
"""

    debate_task = """
세 Agent의 Handoff Packet을 비교하여 최종 토론 결과를 작성하십시오.

반드시 아래 형식을 지키십시오.

# Debate Result

## 1. 최종 분류

| 종목 | Research 핵심 | Analyst 핵심 | Risk 핵심 | 최종 분류 | 이유 |
|---|---|---|---|---|---|

## 2. 의견 충돌 지점

| 종목 | 충돌 내용 | 최종 판단 |
|---|---|---|

## 3. 주요 리스크

| 종목 | 핵심 리스크 | 사용자 확인 필요 사항 |
|---|---|---|

## 4. 사용자 확인 질문

- 질문 1:
- 질문 2:
- 질문 3:

## 5. 상세 보고서 참조

- Research Full Report:
- Analyst Full Report:
- Risk Full Report:

작성 규칙:
- 최종 분류는 관심, 조건부 관심, 관망, 제외 중 하나만 사용하십시오.
- Risk Manager가 High 또는 Critical로 분류한 종목은 관심으로 분류하지 마십시오.
- 근거가 부족한 종목은 관망 또는 제외로 분류하십시오.
- 매수 또는 매도 명령을 내리지 마십시오.
- 최종 판단은 사용자가 직접 수행해야 한다는 점을 명시하십시오.
- 표는 끝까지 완성하십시오.
"""

    debate_file = run_final_debate_agent(
        config=config,
        context=debate_context,
        task=debate_task,
        output_file_name="04_debate_moderator_agent_result.md",
    )

    logger.info(f"[debate_workflow] Final debate result saved: {debate_file}")

    debate_result = read_text_file(debate_file)

    # ------------------------------------------------------------------
    # 5. Knowledge Curator Agent
    # ------------------------------------------------------------------
    knowledge_context = f"""
[오늘의 원본 입력 데이터]
{today_input}

[Research Agent Handoff Packet]
{research_handoff}

[Analyst Agent Handoff Packet]
{analyst_handoff}

[Risk Manager Agent Handoff Packet]
{risk_handoff}

[Debate Moderator 최종 결과]
{debate_result}

[상세 보고서 파일 경로]
- Research Full Report: {research_full_file}
- Research Handoff: {research_handoff_file}
- Analyst Full Report: {analyst_full_file}
- Analyst Handoff: {analyst_handoff_file}
- Risk Full Report: {risk_full_file}
- Risk Handoff: {risk_handoff_file}
- Debate Result: {debate_file}
"""

    knowledge_task = """
오늘 생성된 투자 에이전트 회의 결과를 바탕으로 재사용 가능한 지식을 정리하십시오.

반드시 아래 형식을 지키십시오.

# Knowledge Curator Result

## 1. Reusable Insights

오늘 결과에서 반복 활용 가능한 투자 인사이트를 정리하십시오.

| 인사이트 | 근거 | 활용 조건 | 주의사항 |
|---|---|---|---|

## 2. Rule Update Candidates

전략 또는 원칙 파일에 반영할 만한 수정 후보를 작성하십시오.

| 대상 파일 | 수정 후보 | 수정 이유 | 우선순위 |
|---|---|---|---|

대상 파일 예:
- strategies/volume_500b_pullback.md
- strategies/leading_sector_strategy.md
- strategies/closing_bet_strategy.md
- rules/risk_policy.md
- rules/no_trade_conditions.md

## 3. Failed Reasoning Patterns

오늘 결과에서 주의해야 할 잘못된 판단 패턴 또는 취약한 판단을 정리하십시오.

| 판단 패턴 | 문제점 | 재발 방지 방법 |
|---|---|---|

## 4. Tomorrow Checklist

다음 거래일 또는 다음 분석에서 확인할 체크리스트를 작성하십시오.

- 체크 1:
- 체크 2:
- 체크 3:
- 체크 4:
- 체크 5:

## 5. Second Brain Update Suggestions

Second Brain에 반영할 제안을 작성하십시오.
단, 아직 검증되지 않은 내용은 confirmed rule로 저장하지 말고 candidate로만 제안하십시오.

작성 규칙:
- 하루짜리 추측을 검증된 지식처럼 말하지 마십시오.
- 투자 실행 지시를 하지 마십시오.
- 재사용 가능한 지식과 단기 관찰을 구분하십시오.
- 실패 사례를 숨기지 마십시오.
- 최종 판단은 사용자가 직접 수행해야 한다는 점을 명시하십시오.
"""

    knowledge_file = run_final_agent(
        config=config,
        agent_name="knowledge_curator_agent",
        context=knowledge_context,
        task=knowledge_task,
        output_file_name="05_knowledge_curator_agent_result.md",
    )

    logger.info(f"[debate_workflow] Knowledge curator result saved: {knowledge_file}")

    # ------------------------------------------------------------------
    # 6. Copy output files to Second Brain daily folder
    # ------------------------------------------------------------------
    brain_daily_dir = copy_output_to_brain_daily(config=config)

    logger.info(f"[debate_workflow] Brain daily directory saved: {brain_daily_dir}")
    logger.info("[debate_workflow] Debate workflow completed.")

    return knowledge_file