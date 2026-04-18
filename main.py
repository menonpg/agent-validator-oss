"""
Agent Validator — FastAPI entrypoint
"""
import os
import tempfile
import asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid

from engine.validator import Validator
from engine.rule_loader import RuleLoader
from engine.report import ReportCard

import json as _json

# A2A Agent Card — static, served from env/config
AGENT_CARD = {
    "name": "Agent Validator",
    "description": (
        "Validates AI agent repositories against enterprise compliance standards. "
        "Checks 33 rules across security, structure, governance, safety, and A2A protocol compliance."
    ),
    "version": "1.1.0",
    "url": os.getenv("SERVICE_URL", "https://agent-validator-hvky63ls3a-uc.a.run.app"),
    "capabilities": {
        "streaming": False,
        "pushNotifications": False,
    },
    "skills": [
        {
            "id": "validate-agent",
            "name": "Validate Agent Repository",
            "description": (
                "Clone and validate a GitHub agent repository against 29 compliance rules "
                "covering security, structure, governance, safety, and A2A protocol."
            ),
            "inputModes": ["text"],
            "outputModes": ["text"],
            "examples": [
                "validate https://github.com/org/repo/tree/main",
            ],
        }
    ],
    "authentication": {
        "schemes": ["none"],
    },
    "provider": {
        "organization": "The Menon Lab",
        "url": "https://themenonlab.com",
    },
}

app = FastAPI(title="Agent Validator", version="1.1.0")

# CORS — allow GitHub Pages and direct browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # public API — wide open is fine
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# Load rules at startup
RULES_DIR = Path(__file__).parent / "rules"
RULES_VERSION = os.getenv("RULES_VERSION", "v1.0.0")
GCP_PROJECT = os.getenv("GCP_PROJECT_ID", "soulmate-489217")
rule_loader = RuleLoader(RULES_DIR)
rules = rule_loader.load_all()

# In-memory job store
jobs: dict[str, dict] = {}


class SubmitRequest(BaseModel):
    repo_url: str
    branch: str | None = None
    submitter: str = "anonymous"
    team: str = "unknown"



# ── A2A Protocol Endpoints ───────────────────────────────────────────────────

@app.get("/.well-known/agent.json")
def agent_card():
    """Google A2A Agent Card — enables orchestrator discovery."""
    return JSONResponse(content=AGENT_CARD)


class A2ARequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: dict | None = None
    id: str | None = None


@app.post("/a2a")
async def a2a_endpoint(req: A2ARequest, background_tasks: BackgroundTasks):
    """
    Google A2A JSON-RPC 2.0 endpoint.
    Supports: tasks/send
    Returns: job_id — poll GET /validate/{job_id} for result.
    Added: 2026-03-19
    """
    if req.method not in ("tasks/send",):
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method not found: {req.method}"},
                "id": req.id,
            },
        )

    # Parse repo_url from A2A message parts
    params = req.params or {}
    message = params.get("message", {})
    parts = message.get("parts", [])
    text = " ".join(p.get("text", "") for p in parts if "text" in p)

    # Extract github URL from text
    import re
    url_match = re.search(r"https://github\.com/[^\s]+", text)
    if not url_match:
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32602, "message": "No GitHub URL found in message parts"},
                "id": req.id,
            },
        )

    repo_url = url_match.group(0)
    task_id = params.get("id", str(uuid.uuid4()))
    job_id = str(uuid.uuid4())

    # Queue validation job (same engine as /validate)
    jobs[job_id] = {"status": "submitted", "a2a_task_id": task_id, "repo_url": repo_url}
    background_tasks.add_task(_run_validation, job_id, repo_url, "a2a", "a2a-orchestrator", None)

    return JSONResponse(content={
        "jsonrpc": "2.0",
        "result": {
            "id": task_id,
            "status": {"state": "submitted"},
            "metadata": {"job_id": job_id, "poll_url": f"/validate/{job_id}"},
        },
        "id": req.id,
    })

@app.get("/health")
def health():
    return {
        "status": "ok",
        "rules_version": RULES_VERSION,
        "rules_loaded": len(rules),
        "hard_gates": len([r for r in rules if r.tier == "HARD"]),
        "soft_gates": len([r for r in rules if r.tier == "SOFT"]),
        "quality_checks": len([r for r in rules if r.tier == "QUALITY"]),
    }


@app.get("/gcp-metrics")
async def gcp_metrics():
    """Return Cloud Run service metrics + cost estimates for the observability dashboard."""
    try:
        import google.auth
        import google.auth.transport.requests
        from google.cloud import monitoring_v3
        from google.protobuf.timestamp_pb2 import Timestamp
        import time

        # Get credentials via metadata server (works on Cloud Run automatically)
        creds, project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/monitoring.read",
                    "https://www.googleapis.com/auth/cloud-platform"]
        )
        creds.refresh(google.auth.transport.requests.Request())

        client = monitoring_v3.MetricServiceClient(credentials=creds)
        project_name = f"projects/{GCP_PROJECT}"

        now = time.time()
        mtd_start = datetime(datetime.now(timezone.utc).year,
                             datetime.now(timezone.utc).month, 1,
                             tzinfo=timezone.utc).timestamp()
        week_start = now - 7 * 86400

        def query_metric(metric_type, start_ts, reducer="REDUCE_SUM"):
            interval = monitoring_v3.TimeInterval(
                start_time={"seconds": int(start_ts)},
                end_time={"seconds": int(now)},
            )
            aggregation = monitoring_v3.Aggregation(
                alignment_period={"seconds": int(now - start_ts) + 1},
                per_series_aligner=monitoring_v3.Aggregation.Aligner.ALIGN_SUM,
                cross_series_reducer=getattr(
                    monitoring_v3.Aggregation.Reducer, f"REDUCE_{reducer.upper()}"
                    if not reducer.startswith("REDUCE_") else reducer
                ),
                group_by_fields=["resource.labels.service_name"],
            )
            try:
                results = client.list_time_series(
                    request={
                        "name": project_name,
                        "filter": f'metric.type="{metric_type}" AND resource.type="cloud_run_revision"',
                        "interval": interval,
                        "aggregation": aggregation,
                    }
                )
                total = 0.0
                for ts in results:
                    for pt in ts.points:
                        v = pt.value
                        total += (v.int64_value or v.double_value or 0)
                return total
            except Exception:
                return 0.0

        # Requests
        req_mtd  = query_metric("run.googleapis.com/request_count", mtd_start)
        req_7d   = query_metric("run.googleapis.com/request_count", week_start)

        # Instance seconds (billable compute)
        inst_mtd = query_metric("run.googleapis.com/container/billable_instance_time", mtd_start)
        inst_7d  = query_metric("run.googleapis.com/container/billable_instance_time", week_start)

        # Cost estimates (us-central1 pricing)
        FREE_REQ    = 2_000_000
        FREE_CPU_S  = 180_000   # vCPU-seconds
        FREE_MEM_S  = 360_000   # GB-seconds
        PRICE_REQ   = 0.40 / 1_000_000   # per request
        PRICE_CPU   = 0.000024            # per vCPU-second (1 vCPU assumed)
        PRICE_MEM   = 0.0000025           # per GB-second (0.5 GB assumed)

        billable_req = max(0, req_mtd - FREE_REQ)
        cpu_s = inst_mtd        # 1 vCPU per instance
        mem_s = inst_mtd * 0.5  # 0.5 GB per instance
        billable_cpu = max(0, cpu_s - FREE_CPU_S)
        billable_mem = max(0, mem_s - FREE_MEM_S)

        cost_req = billable_req * PRICE_REQ
        cost_cpu = billable_cpu * PRICE_CPU
        cost_mem = billable_mem * PRICE_MEM
        cost_total = cost_req + cost_cpu + cost_mem

        def fmt_cost(c):
            return "< $0.001" if c < 0.001 else f"${c:.4f}"

        def fmt_seconds(s):
            if s < 1:   return "0.0s"
            if s < 60:  return f"{s:.1f}s"
            return f"{s/60:.1f}m"

        services = [{
            "name": "agent-validator",
            "region": "us-central1",
            "cpu": "1 vCPU",
            "memory": "512 MB",
            "req_mtd":  int(req_mtd),
            "req_7d":   int(req_7d),
            "inst_mtd": fmt_seconds(inst_mtd),
            "inst_7d":  fmt_seconds(inst_7d),
            "est_cost": fmt_cost(cost_total),
        }]

        return {
            "project": GCP_PROJECT,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "services": services,
            "cost_breakdown": {
                "requests": fmt_cost(cost_req),
                "cpu":      fmt_cost(cost_cpu),
                "memory":   fmt_cost(cost_mem),
                "total":    fmt_cost(cost_total),
            },
            "pricing_ref": {
                "requests":    "$0.40 / M (2M free)",
                "cpu":         "$0.000024 / vCPU-s (180K free)",
                "memory":      "$0.0000025 / GB-s (360K free)",
                "networking":  "Free (same region)",
            }
        }

    except Exception as e:
        # Return graceful fallback so the UI still renders
        return {
            "project": GCP_PROJECT,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
            "services": [{
                "name": "agent-validator",
                "region": "us-central1",
                "cpu": "1 vCPU",
                "memory": "512 MB",
                "req_mtd": "—", "req_7d": "—",
                "inst_mtd": "—", "inst_7d": "—",
                "est_cost": "—",
            }],
            "cost_breakdown": {"requests":"—","cpu":"—","memory":"—","total":"—"},
            "pricing_ref": {
                "requests":    "$0.40 / M (2M free)",
                "cpu":         "$0.000024 / vCPU-s (180K free)",
                "memory":      "$0.0000025 / GB-s (360K free)",
                "networking":  "Free (same region)",
            }
        }


@app.post("/validate")
async def submit(req: SubmitRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "queued", "repo_url": req.repo_url, "report": None}
    background_tasks.add_task(_run_validation, job_id, req)
    return {"job_id": job_id, "status": "queued"}


@app.get("/validate/{job_id}")
def get_result(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


async def _run_validation(job_id: str, req: SubmitRequest):
    jobs[job_id]["status"] = "running"
    try:
        validator = Validator(rules=rules, rules_version=RULES_VERSION)
        report = await validator.validate(
            repo_url=req.repo_url,
            branch=req.branch,
            submitter=req.submitter,
            team=req.team,
        )
        jobs[job_id]["status"] = "done"
        jobs[job_id]["report"] = report.to_dict()
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


# Serve UI
app.mount("/", StaticFiles(directory="ui", html=True), name="ui")
