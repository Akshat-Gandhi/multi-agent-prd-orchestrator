from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from prd_planner.contracts.schemas import EventRecord, RunRecord, RunResponse


class SQLiteStore:
    def __init__(self, path: str) -> None:
        self.path = str(Path(path).resolve())
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    response_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    step TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def save_run(self, run: RunRecord) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO runs(run_id, trace_id, status, request_json, response_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status=excluded.status,
                    response_json=excluded.response_json
                """,
                (
                    run.run_id,
                    run.trace_id,
                    run.status,
                    run.request.model_dump_json(),
                    run.response.model_dump_json() if run.response else None,
                ),
            )

    def get_run(self, run_id: str) -> RunResponse | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT response_json FROM runs WHERE run_id=?", (run_id,)
            ).fetchone()
        if not row or not row[0]:
            return None
        return RunResponse.model_validate_json(row[0])

    def save_event(self, event: EventRecord) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO events(run_id, trace_id, agent_id, step, event_type, message, data_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.run_id,
                    event.trace_id,
                    event.agent_id,
                    event.step,
                    event.event_type,
                    event.message,
                    json.dumps(event.data),
                    event.created_at,
                ),
            )

    def get_events(self, run_id: str) -> list[EventRecord]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT run_id, trace_id, agent_id, step, event_type, message, data_json, created_at
                FROM events WHERE run_id=? ORDER BY id ASC
                """,
                (run_id,),
            ).fetchall()
        events: list[EventRecord] = []
        for row in rows:
            events.append(
                EventRecord(
                    run_id=row[0],
                    trace_id=row[1],
                    agent_id=row[2],
                    step=row[3],
                    event_type=row[4],
                    message=row[5],
                    data=json.loads(row[6]),
                    created_at=row[7],
                )
            )
        return events
