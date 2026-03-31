# PRD Planner Agents

Turn a raw product PRD into a structured execution plan using a LangGraph orchestrator + specialized sub-agents.

## Overview

This project runs a multi-agent workflow:
1. `Planner Orchestrator` ingests the PRD and plans research tasks.
2. `Market Agent` gathers market context (Exa MCP primary, Exa API fallback).
3. `Competitor Agent` gathers competitor signals.
4. `Browser Agent` gathers browser evidence (MCP-enabled with safe fallback).
5. `Synthesis` generates a typed `ExecutionPlan` (Pydantic-validated).
6. `Quality Gate` marks run as `success | degraded | failed`.
7. All runs/events are persisted and logged.

## Tech Stack

- Python 3.10+
- FastAPI + Uvicorn
- LangGraph (orchestrator graph)
- LangChain Core (`PydanticOutputParser`)
- Pydantic (contracts and validation)
- Ollama / OpenAI via provider abstraction (`LLMManager`)
- Exa MCP + Exa HTTP API fallback
- Browser MCP integration + local fallback
- SQLite (run/event persistence)
- JSONL structured logs
- python-dotenv (`.env` auto-load)

## Project Structure

- `src/prd_planner/api/` FastAPI app and endpoints
- `src/prd_planner/graph/` orchestration logic and state transitions
- `src/prd_planner/agents/` market, competitor, browser agents
- `src/prd_planner/tools/` Exa + Browser MCP clients and fallbacks
- `src/prd_planner/models/` LLM manager/provider adapters
- `src/prd_planner/storage/` SQLite store
- `src/prd_planner/contracts/` Pydantic schemas/contracts
- `scripts/run_api.sh` start server
- `scripts/send_prd.py` helper to submit PRD

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
./scripts/run_api.sh
```

Open:
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/`

## API

- `POST /runs` -> starts a run and returns final run payload
- `GET /runs/{run_id}` -> returns status, plan, scores, citations
- `GET /runs/{run_id}/events` -> returns full event timeline

### Example: Start a run

```bash
curl -sS -X POST http://127.0.0.1:8000/runs \
  -H "Content-Type: application/json" \
  -d '{
    "prd_text": "Build a procurement automation SaaS for mid-market teams with policy approvals and spend analytics.",
    "domain": "procurement-tech",
    "constraints": ["SOC2-ready", "MVP in 8 weeks"]
  }' | jq
```

### Example: Inspect run

```bash
curl -sS http://127.0.0.1:8000/runs/<run_id> | jq
curl -sS http://127.0.0.1:8000/runs/<run_id>/events | jq
```

## Configuration (`.env`)

The app auto-loads `.env` via `python-dotenv` at startup.

### LLM

```bash
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen3.5:0.8b
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_TIMEOUT_S=300
OLLAMA_THINK=false
OLLAMA_NUM_PREDICT=1024

# optional tracing
DEBUG_LLM_TRACE=true
LLM_TRACE_PREVIEW_CHARS=180
```

### Exa (Market + Competitor)

```bash
EXA_API_KEY=your_exa_key
EXA_MCP_URL=https://mcp.exa.ai/mcp
EXA_API_BASE_URL=https://api.exa.ai
EXA_TIMEOUT_S=45
EXA_NUM_RESULTS=1
```

Behavior:
- Primary path: Exa MCP
- Fallback path: Exa HTTP API
- If no `EXA_API_KEY`, dummy responses are used

### Browser MCP (optional)

```bash
PLAYWRIGHT_MCP_URL=
PLAYWRIGHT_MCP_API_KEY=
PLAYWRIGHT_MCP_TIMEOUT_S=60
PLAYWRIGHT_MCP_OPEN_TOOL=browser_open_page
PLAYWRIGHT_MCP_EXTRACT_TOOL=browser_extract_facts
PLAYWRIGHT_MCP_CLOSE_TOOL=browser_close_page
```

If missing/invalid, browser tool falls back to local dummy client.

## Persistence and Logs

- SQLite DB: `runs.sqlite3`
- JSON logs: `logs/prd_planner.jsonl`

Useful checks:

```bash
sqlite3 runs.sqlite3 "select run_id,status,trace_id from runs order by rowid desc limit 5;"
sqlite3 runs.sqlite3 "select agent_id,step,event_type,message from events where run_id='<run_id>' order by id;"
tail -n 80 logs/prd_planner.jsonl
```

## Common Failure Mode

If run status is `failed` with `execution plan missing`, synthesis output did not satisfy strict `ExecutionPlan` schema. Check:

```bash
curl -sS http://127.0.0.1:8000/runs/<run_id>/events | jq '.[] | select(.step=="synthesize_plan")'
```

## Debug

```bash
PYTHONPATH=src python -m debugpy --listen 0.0.0.0:5678 -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Set breakpoints in:
- `src/prd_planner/graph/orchestrator.py`
- `src/prd_planner/agents/market/agent.py`
- `src/prd_planner/agents/competitor/agent.py`
- `src/prd_planner/agents/browser/agent.py`
