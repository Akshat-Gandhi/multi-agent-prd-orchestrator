from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    db_path: str = str(Path(os.getenv("DB_PATH", "runs.sqlite3")).resolve())
    min_agent_score: int = int(os.getenv("MIN_AGENT_SCORE", "70"))
    max_retries_per_agent: int = int(os.getenv("MAX_RETRIES_PER_AGENT", "1"))


settings = Settings()
