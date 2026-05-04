# LM Studio 로컬 LLM에 질문을 보내고 답변을 받습니다.


from openai import OpenAI


class LLMClient:
    def __init__(self, config: dict):
        llm_config = config["llm"]

        self.client = OpenAI(
            base_url=llm_config["base_url"],
            api_key="lm-studio"
        )

        self.model = llm_config["model"]
        self.temperature = llm_config.get("temperature", 0.3)
        self.max_tokens = llm_config.get("max_tokens", 3000)

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )

        return response.choices[0].message.content