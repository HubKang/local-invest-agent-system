# 하나의 에이전트를 실행하고 결과를 output 폴더에 저장합니다.

from datetime import datetime
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