# 보고서 저장 기능을 담당합니다.

from src.file_store import write_text_file


def save_markdown_report(file_path: str, content: str) -> None:
    write_text_file(file_path, content)