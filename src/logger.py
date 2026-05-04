# 프로그램 실행 기록을 logs/app.log에 저장합니다.

import logging
from pathlib import Path


def get_logger(config: dict) -> logging.Logger:
    log_dir = Path(config["paths"].get("log_dir", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("local-invest-agent")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    log_file = log_dir / "app.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    stream_handler = logging.StreamHandler()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger