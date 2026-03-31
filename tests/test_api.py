import os

from fastapi.testclient import TestClient

os.environ["LLM_PROVIDER"] = "deterministic"
from prd_planner.api.app import app


client = TestClient(app)


def test_run_create_and_fetch_events():
    payload = {
        "prd_text": "Create a procurement workflow SaaS for mid-market companies with approval automation and analytics dashboards.",
        "domain": "procurement-tech",
    }
    create = client.post("/runs", json=payload)
    assert create.status_code == 200
    run = create.json()
    run_id = run["run_id"]

    status = client.get(f"/runs/{run_id}")
    assert status.status_code == 200
    assert status.json()["run_id"] == run_id

    events = client.get(f"/runs/{run_id}/events")
    assert events.status_code == 200
    assert len(events.json()) >= 1
