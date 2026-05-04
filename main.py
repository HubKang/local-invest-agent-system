import argparse

from src.config import load_config
from src.logger import get_logger
from src.workflow import run_single_agent_workflow, run_debate_workflow


def main():
    parser = argparse.ArgumentParser(
        description="Local Invest Agent System"
    )

    parser.add_argument(
        "--workflow",
        default="single",
        choices=["single", "debate"],
        help="실행할 workflow입니다. single 또는 debate"
    )

    parser.add_argument(
        "--agent",
        default="research_agent",
        help="single workflow에서 실행할 agent 이름입니다."
    )

    parser.add_argument(
        "--task",
        default="오늘의 입력 데이터를 바탕으로 투자 후보 종목을 발굴하고, 후보 선정 이유와 근거 수준을 표로 정리하십시오.",
        help="single workflow에서 Agent에게 지시할 작업 내용입니다."
    )

    args = parser.parse_args()

    config = load_config("config.yaml")
    logger = get_logger(config)

    logger.info("Local Invest Agent System started.")
    logger.info(f"Selected workflow: {args.workflow}")

    print("Local Invest Agent System")
    print("-------------------------")
    print(f"Workflow: {args.workflow}")
    print()

    if args.workflow == "single":
        print(f"Agent: {args.agent}")
        print(f"Task: {args.task}")
        print()
        print("Single Agent를 실행합니다.")
        print()

        output_file = run_single_agent_workflow(
            config=config,
            agent_name=args.agent,
            task=args.task
        )

        logger.info(f"Single agent result saved: {output_file}")

        print()
        print("Single Agent 실행 완료!")
        print(f"결과 파일: {output_file}")

    elif args.workflow == "debate":
        print("Debate Workflow를 실행합니다.")
        print("Research → Analyst → Risk Manager → Debate Moderator 순서로 실행됩니다.")
        print("로컬 LLM 응답에 시간이 걸릴 수 있습니다.")
        print()

        output_file = run_debate_workflow(config=config)

        logger.info(f"Debate workflow final result saved: {output_file}")

        print()
        print("Debate Workflow 실행 완료!")
        print(f"최종 토론 결과 파일: {output_file}")


if __name__ == "__main__":
    main()