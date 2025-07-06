import logging
from pathlib import Path


class LogFilter(logging.Filter):
    def __init__(self, name: str) -> None:
        self._name = name

    def filter(self, record) -> bool:
        if self._name == record.name:
            return True
        return False


def setup_logging(
    log_file: str | Path, level: str = "INFO", name_filter: str | None = None
) -> None:
    log_file = str(log_file)
    level = level.upper()

    logger = logging.getLogger()
    logger.setLevel(level)

    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s @ %(levelname)s - %(funcName)s:%(lineno)d : %(message)s"
    )

    file_handler = logging.FileHandler(log_file, mode="w", encoding="UTF-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    if name_filter is not None:
        file_handler.addFilter(LogFilter(name_filter))
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    if name_filter is not None:
        console_handler.addFilter(LogFilter(name_filter))
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
