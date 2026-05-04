# agent md 파일과 오늘의 입력 데이터를 합쳐서 LLM에게 보낼 프롬프트를 만듭니다.


from pathlib import Path
from src.file_store import read_text_file


def build_agent_prompt(
    brain_repo_path: str,
    agent_name: str,
    task: str,
    today_input: str
) -> tuple[str, str]:
    brain_path = Path(brain_repo_path)

    agent_file = brain_path / "agents" / f"{agent_name}.md"

    agent_definition = read_text_file(str(agent_file))

    system_prompt = f"""
당신은 로컬 투자 에이전트 시스템의 역할 기반 Agent입니다.

아래 Agent Definition을 반드시 따르십시오.

[Agent Definition]
{agent_definition}

[공통 안전 원칙]
- 자동 매수 또는 자동 매도를 지시하지 마십시오.
- 확정 수익을 암시하지 마십시오.
- 근거와 추측을 구분하십시오.
- 최종 판단은 사용자가 직접 수행합니다.
"""

    user_prompt = f"""
[오늘의 입력 데이터]
{today_input}

[수행할 작업]
{task}
"""

    return system_prompt, user_prompt
