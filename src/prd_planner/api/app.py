from __future__ import annotations

import asyncio
from threading import Thread
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(".env"), override=False)

from prd_planner.config.settings import settings
from prd_planner.contracts.schemas import RunLaunchResponse, RunRecord, RunRequest, RunResponse, RunStatusResponse
from prd_planner.graph.orchestrator import Orchestrator
from prd_planner.models.provider import ModelRegistry
from prd_planner.storage.sqlite_store import SQLiteStore


store = SQLiteStore(settings.db_path)
orchestrator = Orchestrator(store=store, model_registry=ModelRegistry())
app = FastAPI(title="PRD Planner PoC", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://multi-agent-prd-orchestrator-vercel.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict:
    return {
        "service": "prd-planner-poc",
        "message": "Send PRD text to POST /runs to trigger orchestration.",
        "quickstart": {
            "create_run": {
                "method": "POST",
                "path": "/runs",
                "json": {
                    "prd_text": "Build a B2B onboarding automation platform with workflow rules and analytics.",
                    "domain": "b2b-saas",
                    "constraints": ["SOC2-ready", "ship MVP in 8 weeks"],
                },
            },
            "read_run": "GET /runs/{run_id}",
            "read_events": "GET /runs/{run_id}/events",
            "docs": "/docs",
        },
    }


@app.post("/runs", response_model=RunResponse)
def create_run(request: RunRequest) -> RunResponse:
    return orchestrator.run(request)


@app.post("/runs/launch", response_model=RunLaunchResponse)
def launch_run(request: RunRequest) -> RunLaunchResponse:
    run = RunRecord(request=request)
    store.save_run(run)

    worker = Thread(target=orchestrator.run_from_record, args=(run,), daemon=True)
    worker.start()

    return RunLaunchResponse(run_id=run.run_id, trace_id=run.trace_id)


@app.get("/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: str) -> RunResponse:
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@app.get("/runs/{run_id}/status", response_model=RunStatusResponse)
def get_run_status(run_id: str) -> RunStatusResponse:
    status = store.get_run_status(run_id)
    if not status:
        raise HTTPException(status_code=404, detail="run not found")
    return status


@app.get("/runs/{run_id}/events")
def get_events(run_id: str) -> list[dict]:
    return [e.model_dump() for e in store.get_events(run_id)]


@app.websocket("/ws/runs/{run_id}")
async def run_updates(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()
    sent_count = 0
    try:
        while True:
            status = store.get_run_status(run_id)
            if status is None:
                await websocket.send_json({"type": "error", "message": "run not found"})
                return

            events = store.get_events(run_id)
            if sent_count == 0:
                await websocket.send_json(
                    {
                        "type": "snapshot",
                        "status": status.model_dump(),
                        "events": [event.model_dump() for event in events],
                    }
                )
                sent_count = len(events)
            elif len(events) > sent_count:
                for event in events[sent_count:]:
                    await websocket.send_json({"type": "event", "event": event.model_dump()})
                sent_count = len(events)

            if status.status != "running":
                run = store.get_run(run_id)
                await websocket.send_json(
                    {
                        "type": "completed",
                        "status": status.model_dump(),
                        "run": run.model_dump() if run else None,
                    }
                )
                return

            await asyncio.sleep(0.6)
    except WebSocketDisconnect:
        return
