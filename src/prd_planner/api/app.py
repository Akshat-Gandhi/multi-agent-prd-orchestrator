from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(".env"), override=False)

from prd_planner.config.settings import settings
from prd_planner.contracts.schemas import RunRequest, RunResponse
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


@app.get("/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: str) -> RunResponse:
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@app.get("/runs/{run_id}/events")
def get_events(run_id: str) -> list[dict]:
    return [e.model_dump() for e in store.get_events(run_id)]
