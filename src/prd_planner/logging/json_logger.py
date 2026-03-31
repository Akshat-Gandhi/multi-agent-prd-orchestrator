from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any


LOGGER_NAME = "prd_planner"
LOG_FILE = os.getenv("LOG_FILE", "logs/prd_planner.jsonl")


def get_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(stream_handler)

        log_path = Path(LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(file_handler)

        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log_event(event: dict[str, Any]) -> None:
    get_logger().info(json.dumps(event, ensure_ascii=True, sort_keys=True))
