# config.yaml 읽기
# → LM Studio 주소 확인
# → 로컬 LLM 호출
# → 응답 출력

from src.config import load_config
from src.llm_client import LLMClient


def main():
    config = load_config("config.yaml")

    llm = LLMClient(config)

    system_prompt = """
당신은 로컬 LLM 연결 테스트를 수행하는 assistant입니다.
짧고 명확하게 답변하십시오.
"""

    user_prompt = """
LM Studio Local Server 연결 테스트입니다.
'연결 성공'이라는 표현을 포함해서 한 문장으로 답변해 주세요.
"""

    response = llm.chat(system_prompt, user_prompt)

    print("LM Studio 연결 테스트 성공!")
    print("-------------------------")
    print(response)


if __name__ == "__main__":
    main()