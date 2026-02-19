"""
FastAPI wrapper for the Autonomous Data Analyst Agent.
Provides upload, SSE streaming, results retrieval, and chart serving.
"""

import os
import sys
import uuid
import json
import asyncio
import tempfile
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Add project root to path so imports work
sys.path.insert(0, str(Path(__file__).parent))

from config import CHARTS_DIR, OUTPUT_DIR

app = FastAPI(title="Autonomous Data Analyst API", version="1.0.0")

# ── CORS (allow frontend to call from any origin) ─────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Serve charts directory ────────────────────────────────────────────────────
app.mount("/charts", StaticFiles(directory=str(CHARTS_DIR)), name="charts")

# ── Serve frontend ────────────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

# ── In-memory run store ───────────────────────────────────────────────────────
# run_id -> {"status": "running"|"done"|"error", "events": [...], "result": {...}}
runs: dict[str, dict] = {}


# ── SSE helpers ───────────────────────────────────────────────────────────────

def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _run_analysis(run_id: str, csv_path: str, metadata: Optional[str], benchmark: bool):
    """Execute the graph in a background thread and push SSE events."""
    from graph import analyst_graph
    from logger import log

    run = runs[run_id]

    def push(event_type: str, payload: dict):
        run["events"].append({"type": event_type, **payload})

    try:
        push("status", {"node": "start", "message": "Pipeline started"})

        initial_state = {
            "file_path": csv_path,
            "raw_metadata_input": metadata,
            "benchmark_enabled": benchmark,
            "execution_results": {},
            "generated_charts": [],
            "trace_log": [],
        }

        # stream_mode="updates" yields {node_name: state_delta} per node execution.
        # This gives us exact node identity without heuristic key-checking.
        accumulated = dict(initial_state)
        final_state = accumulated

        for chunk in analyst_graph.stream(initial_state, stream_mode="updates"):
            # chunk is {node_name: {state_keys_updated...}}
            for node_name, delta in chunk.items():
                accumulated.update(delta)
                final_state = accumulated

                if node_name == "code_executor":
                    step_idx = delta.get("current_step_index", accumulated.get("current_step_index", 0))
                    plan = accumulated.get("analysis_plan", [])
                    total = len(plan)
                    title = plan[step_idx - 1]["title"] if plan and 0 < step_idx <= total else "Code Execution"
                    push("node_progress", {
                        "node": "code_executor",
                        "step": step_idx,
                        "total": total,
                        "step_title": title,
                        "message": f"Step {step_idx}/{total}: {title}",
                    })
                else:
                    push("node_complete", {
                        "node": node_name,
                        "message": f"✓ {node_name.replace('_', ' ').title()}",
                    })

        if final_state is None:
            raise RuntimeError("Graph produced no output.")

        # Build chart URL list and a step-title lookup for the UI
        charts = final_state.get("generated_charts", [])
        execution_results = final_state.get("execution_results", {})

        # step_id -> title map (for chart description in UI)
        step_titles = {
            sid: r.get("title", f"Step {sid}")
            for sid, r in execution_results.items()
        }

        # Build chart list with metadata
        chart_urls = []
        from pathlib import Path as _Path
        for p in charts:
            fname = _Path(str(p)).name
            parts = fname.split("_")
            sid = parts[1] if len(parts) >= 2 and parts[0] == "step" else ""
            chart_urls.append({
                "url": f"/charts/{fname}",
                "step_id": sid,
                "step_title": step_titles.get(sid, ""),
            })

        result = {
            "business_context": final_state.get("business_context", ""),
            "parsed_metadata": final_state.get("parsed_metadata", {}),
            "schema_summary": {
                "row_count": final_state.get("dataframe_summary", {}).get("row_count", 0),
                "column_count": final_state.get("dataframe_summary", {}).get("column_count", 0),
                "numeric_columns": final_state.get("schema", {}).get("numeric_columns", []),
                "categorical_columns": final_state.get("schema", {}).get("categorical_columns", []),
            },
            "analysis_plan": final_state.get("analysis_plan", []),
            "insights": final_state.get("validated_insights", []),
            "recommendations": final_state.get("recommendations", []),
            "charts": chart_urls,
            "step_titles": step_titles,
            "benchmark": final_state.get("benchmark_results"),
            "presentation": final_state.get("presentation_payload", {}),
        }

        # Save full result to disk
        result_path = OUTPUT_DIR / f"result_{run_id}.json"
        result_path.write_text(json.dumps(result, indent=2, default=str))

        run["result"] = result
        run["status"] = "done"
        push("done", {"message": "Analysis complete!"})

    except Exception as e:
        log.error("Analysis failed for run %s: %s", run_id, str(e))
        run["status"] = "error"
        push("error", {"message": str(e)})

    finally:
        # Clean up temp CSV
        try:
            os.unlink(csv_path)
        except Exception:
            pass


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/analyze")
async def analyze(
    csv_file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    benchmark: bool = Form(False),
):
    """Start an analysis run. Returns a run_id for streaming and results."""
    if not csv_file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    # Save CSV to a temp file
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    content = await csv_file.read()
    tmp.write(content)
    tmp.close()

    run_id = str(uuid.uuid4())
    runs[run_id] = {"status": "running", "events": [], "result": None}

    # Run in background thread (graph is synchronous/blocking)
    thread = threading.Thread(
        target=_run_analysis,
        args=(run_id, tmp.name, metadata, benchmark),
        daemon=True,
    )
    thread.start()

    return JSONResponse({"run_id": run_id})


@app.get("/stream/{run_id}")
async def stream_events(run_id: str):
    """SSE endpoint: streams node completion events for a given run."""
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found.")

    async def event_generator():
        sent = 0
        while True:
            run = runs[run_id]
            events = run["events"]

            # Send any new events
            while sent < len(events):
                yield _sse_event(events[sent])
                sent += 1

            if run["status"] in ("done", "error"):
                break

            await asyncio.sleep(0.3)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/results/{run_id}")
async def get_results(run_id: str):
    """Return the full result payload for a completed run."""
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found.")
    run = runs[run_id]
    if run["status"] == "running":
        return JSONResponse({"status": "running"})
    if run["status"] == "error":
        return JSONResponse({"status": "error", "events": run["events"]})
    return JSONResponse({"status": "done", "result": run["result"]})


@app.get("/export/pptx/{run_id}")
async def export_pptx(run_id: str):
    """Generate and return a styled .pptx file for a completed run."""
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found.")
    run = runs[run_id]
    if run["status"] != "done":
        raise HTTPException(status_code=400, detail="Run is not complete yet.")

    result = run["result"]
    out_path = OUTPUT_DIR / f"presentation_{run_id}.pptx"

    # Always regenerate (delete stale cache)
    if out_path.exists():
        out_path.unlink()

    try:
        from tools.pptx_exporter import export_pptx as _export
        _export(result, out_path, charts_dir=CHARTS_DIR)
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=f"PPTX generation failed: {e}\n{traceback.format_exc()}")

    filename = (result.get("presentation") or {}).get("title", "AnalystReport")
    # Sanitise filename
    safe_name = "".join(c for c in filename if c.isalnum() or c in " _-").strip()
    safe_name = safe_name.replace(" ", "_") or "AnalystReport"

    return FileResponse(
        path=str(out_path),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=f"{safe_name}.pptx",
    )


@app.get("/")
async def root():
    """Redirect root to the frontend."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/ui/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
