from datetime import datetime
from pathlib import Path

from src.file_store import read_text_file, write_text_file
from src.agent_runner import build_agent_prompt
from src.llm_client import LLMClient


def run_single_agent_workflow(config: dict, agent_name: str, task: str) -> str:
    today_input_file = config["paths"]["today_input_file"]
    today_input = read_text_file(today_input_file)

    system_prompt, user_prompt = build_agent_prompt(
        brain_repo_path=config["paths"]["brain_repo_path"],
        agent_name=agent_name,
        task=task,
        today_input=today_input
    )

    llm = LLMClient(config)
    result = llm.chat(system_prompt, user_prompt)

    today = datetime.now().strftime("%Y-%m-%d")
    output_file = f"{config['paths']['output_dir']}/{today}/{agent_name}_result.md"

    write_text_file(output_file, result)

    return output_file


def run_agent_with_context(
    config: dict,
    agent_name: str,
    task: str,
    context: str,
    output_file_name: str
) -> tuple[str, str]:
    """
    하나의 Agent를 실행하고 결과 파일 경로와 결과 내용을 함께 반환합니다.
    """

    system_prompt, user_prompt = build_agent_prompt(
        brain_repo_path=config["paths"]["brain_repo_path"],
        agent_name=agent_name,
        task=task,
        today_input=context
    )

    llm = LLMClient(config)
    result = llm.chat(system_prompt, user_prompt)

    today = datetime.now().strftime("%Y-%m-%d")
    output_dir = Path(config["paths"]["output_dir"]) / today
    output_file = output_dir / output_file_name

    write_text_file(str(output_file), result)

    return str(output_file), result


def run_debate_workflow(config: dict) -> str:
    """
    Research → Analyst → Risk Manager → Debate Moderator 순서로 실행합니다.
    각 Agent의 결과는 다음 Agent의 입력으로 전달됩니다.
    """

    today_input_file = config["paths"]["today_input_file"]
    today_input = read_text_file(today_input_file)

    # 1. Research Agent 실행
    research_task = """
오늘의 입력 데이터를 바탕으로 투자 후보 종목을 발굴하십시오.

요구사항:
1. 후보 종목을 표로 정리하십시오.
2. 후보 선정 이유를 작성하십시오.
3. 근거 수준을 A/B/C/D로 표시하십시오.
4. 매수 추천은 하지 마십시오.
5. Analyst Agent가 후속 분석할 수 있도록 정보를 구조화하십시오.
6. 전체 답변은 1000자 내외로 작성하십시오.
"""

    research_file, research_result = run_agent_with_context(
        config=config,
        agent_name="research_agent",
        task=research_task,
        context=today_input,
        output_file_name="01_research_agent_result.md"
    )

    # 2. Analyst Agent 실행
    analyst_context = f"""
[오늘의 원본 입력 데이터]
{today_input}

[Research Agent 결과]
{research_result}
"""

    analyst_task = """
Research Agent가 제시한 후보 종목을 분석하십시오.

요구사항:
1. 각 후보의 투자 검토 가능성을 평가하십시오.
2. 차트 위치, 거래대금 특징, 재료 지속성, 후속 확인 조건을 정리하십시오.
3. 진입 조건과 관망 조건을 구분하십시오.
4. 손절 기준이 불명확한 종목은 긍정 판단하지 마십시오.
5. 최종 분류는 검토 가능, 조건부 관심, 관망, 제외 중 하나로 작성하십시오.
6. 전체 답변은 1000자 내외로 작성하십시오.
"""

    analyst_file, analyst_result = run_agent_with_context(
        config=config,
        agent_name="analyst_agent",
        task=analyst_task,
        context=analyst_context,
        output_file_name="02_analyst_agent_result.md"
    )

    # 3. Risk Manager Agent 실행
    risk_context = f"""
[오늘의 원본 입력 데이터]
{today_input}

[Research Agent 결과]
{research_result}

[Analyst Agent 결과]
{analyst_result}
"""

    risk_task = """
Research Agent와 Analyst Agent의 의견을 바탕으로 리스크를 검토하십시오.

요구사항:
1. 각 후보 종목의 손실 가능성을 먼저 검토하십시오.
2. 손절 기준이 명확한지 확인하십시오.
3. 고점 추격 위험, 재료 소멸 위험, 시장 지수와의 충돌 가능성을 검토하십시오.
4. 반드시 반대 논리를 작성하십시오.
5. 리스크 등급은 Low, Medium, High, Critical 중 하나로 작성하십시오.
6. Critical 종목은 최종 검토 대상에서 제외해야 한다고 표시하십시오.
7. 전체 답변은 1200자 내외로 작성하십시오.
"""

    risk_file, risk_result = run_agent_with_context(
        config=config,
        agent_name="risk_manager_agent",
        task=risk_task,
        context=risk_context,
        output_file_name="03_risk_manager_agent_result.md"
    )

    # 4. Debate Moderator Agent 실행
    debate_context = f"""
[오늘의 원본 입력 데이터]
{today_input}

[Research Agent 결과]
{research_result}

[Analyst Agent 결과]
{analyst_result}

[Risk Manager Agent 결과]
{risk_result}
"""

    debate_task = """
Research Agent, Analyst Agent, Risk Manager Agent의 의견을 비교하여 최종 토론 결과를 정리하십시오.

요구사항:
1. 세 Agent의 공통 의견을 정리하십시오.
2. 의견 충돌 지점을 정리하십시오.
3. 근거가 약한 주장을 제거하십시오.
4. Risk Manager의 경고를 반드시 반영하십시오.
5. 최종 분류는 관심, 조건부 관심, 관망, 제외 중 하나로 작성하십시오.
6. 매수 또는 매도 명령을 내리지 마십시오.
7. 다음 단계에서 사용자가 확인해야 할 질문을 작성하십시오.
"""

    debate_file, debate_result = run_agent_with_context(
        config=config,
        agent_name="debate_moderator_agent",
        task=debate_task,
        context=debate_context,
        output_file_name="04_debate_moderator_agent_result.md"
    )

    return debate_file