from src.config import load_config
from src.logger import get_logger


def main():
    config = load_config("config.yaml")
    logger = get_logger(config)

    logger.info("Local Invest Agent System started.")
    logger.info(f"App name: {config['app']['name']}")
    logger.info(f"LLM provider: {config['llm']['provider']}")
    logger.info(f"Brain repo path: {config['paths']['brain_repo_path']}")

    print("Local Invest Agent System")
    print("-------------------------")
    print(f"App name: {config['app']['name']}")
    print(f"LLM provider: {config['llm']['provider']}")
    print(f"Brain repo path: {config['paths']['brain_repo_path']}")
    print()
    print("3단계 기본 실행 구조가 준비되었습니다.")


if __name__ == "__main__":
    main()