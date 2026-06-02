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
from tools.pptx_exporter import export_pptx
from tools.data_loader import detect_source_type

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
FRONTEND_DIR = Path(__file__).parent / "frontend" / "dist"
if FRONTEND_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

# ── In-memory run store ───────────────────────────────────────────────────────
# run_id -> {"status": "running"|"done"|"error", "events": [...], "result": {...}}
runs: dict[str, dict] = {}


# ── SSE helpers ───────────────────────────────────────────────────────────────

def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _run_analysis(
    run_id: str,
    csv_path: str,
    source_type: str,
    source_config: dict,
    metadata: Optional[str],
    benchmark: bool,
):
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
            "source_type": source_type,
            "source_config": source_config,
            "raw_metadata_input": metadata,
            "benchmark_enabled": benchmark,
            "execution_results": {},
            "generated_charts": [],
            "parquet_path": None,
            "trace_log": [],
        }

        # stream_mode="updates" yields {node_name: state_delta} per node execution.
        # This gives us exact node identity without heuristic key-checking.
        accumulated = dict(initial_state)
        final_state = accumulated

        for chunk in analyst_graph.stream(initial_state, stream_mode="updates", config={"recursion_limit": 100}):
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

        # Enrich insights with visual "Insight Provenance" data proofs
        raw_insights = final_state.get("validated_insights", [])
        enriched_insights = []
        for ins in raw_insights:
            enriched_ins = dict(ins)
            supporting_str = str(ins.get("supporting_data", ""))
            
            step_id_found = None
            for part in supporting_str.split():
                clean_part = "".join(c for c in part if c.isdigit())
                if clean_part:
                    step_id_found = clean_part
                    break
            
            if not step_id_found and "_" in supporting_str:
                for part in supporting_str.split("_"):
                    clean_part = "".join(c for c in part if c.isdigit())
                    if clean_part:
                        step_id_found = clean_part
                        break
                        
            if step_id_found and step_id_found in execution_results:
                step_res = execution_results[step_id_found]
                enriched_ins["data_proof"] = {
                    "code": step_res.get("code", ""),
                    "stdout": step_res.get("stdout", "")[:1000]
                }
            else:
                enriched_ins["data_proof"] = None
                
            enriched_insights.append(enriched_ins)

        result = {
            "business_context": final_state.get("business_context", ""),
            "parsed_metadata": final_state.get("parsed_metadata", {}),
            "schema_summary": {
                "row_count": final_state.get("dataframe_summary", {}).get("row_count", 0),
                "column_count": final_state.get("dataframe_summary", {}).get("column_count", 0),
                "numeric_columns": final_state.get("schema", {}).get("numeric_columns", []),
                "categorical_columns": final_state.get("schema", {}).get("categorical_columns", []),
                "source_type": final_state.get("dataframe_summary", {}).get("source_type", source_type),
            },
            "analysis_plan": final_state.get("analysis_plan", []),
            "insights": enriched_insights,
            "recommendations": final_state.get("recommendations", []),
            "charts": chart_urls,
            "step_titles": step_titles,
            "benchmark": final_state.get("benchmark_results"),
            "presentation": final_state.get("presentation_payload", {}),
            "executive_report": final_state.get("executive_report", ""),
        }

        # Save full result to disk
        result_path = OUTPUT_DIR / f"result_{run_id}.json"
        result_path.write_text(json.dumps(result, indent=2, default=str))

        # Generate Presentation PPTX
        pptx_path = OUTPUT_DIR / f"presentation_{run_id}.pptx"
        try:
            pres_payload = final_state.get("presentation_payload", {})
            export_pptx({"presentation": pres_payload}, pptx_path, charts_dir=CHARTS_DIR)
            result["presentation_url"] = f"/presentation/{run_id}"
        except Exception as pe:
            log.error("Failed to generate PPTX for run %s: %s", run_id, str(pe))

        run["result"] = result
        run["status"] = "done"
        push("done", {"message": "Analysis complete!"})

    except Exception as e:
        log.error("Analysis failed for run %s: %s", run_id, str(e))
        run["status"] = "error"
        push("error", {"message": str(e)})

    finally:
        # Clean up only the raw original upload file
        if csv_path:
            try:
                os.unlink(csv_path)
            except Exception:
                pass
        # Store the Parquet file path in runs dictionary for persistent chat Q&A
        if "accumulated" in locals() and accumulated.get("parquet_path"):
            run["parquet_path"] = accumulated["parquet_path"]
        elif "final_state" in locals() and final_state.get("parquet_path"):
            run["parquet_path"] = final_state["parquet_path"]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/analyze")
async def analyze(
    csv_file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    benchmark: bool = Form(False),
    table_name: Optional[str] = Form(None),
):
    """
    Start an analysis run.
    Accepts CSV, Excel (.xlsx/.xls), Parquet, and SQLite (.db/.sqlite/.sqlite3) files.
    Returns a run_id for streaming and results.
    """
    filename = csv_file.filename or ""
    try:
        source_type = detect_source_type(filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Preserve the original extension so data_loader can read it correctly
    ext = os.path.splitext(filename)[-1].lower()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    content = await csv_file.read()
    tmp.write(content)
    tmp.close()

    # Build source-specific config
    source_config: dict = {"path": tmp.name}
    if source_type == "sqlite" and table_name:
        source_config["table"] = table_name

    run_id = str(uuid.uuid4())
    runs[run_id] = {
        "status": "running",
        "events": [],
        "result": None,
        "source_type": source_type,
        "source_config": source_config,
        "metadata": metadata,
        "benchmark": benchmark
    }

    # Run in background thread (graph is synchronous/blocking)
    thread = threading.Thread(
        target=_run_analysis,
        args=(run_id, tmp.name, source_type, source_config, metadata, benchmark),
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


@app.get("/presentation/{run_id}")
async def get_presentation(run_id: str):
    """Download the generated PowerPoint presentation."""
    pptx_path = OUTPUT_DIR / f"presentation_{run_id}.pptx"
    if not pptx_path.exists():
        raise HTTPException(status_code=404, detail="Presentation not found or not yet generated.")
    return FileResponse(
        path=pptx_path,
        filename=f"Analysis_Report_{run_id[:8]}.pptx",
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )


from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str


@app.post("/api/chat/{run_id}")
async def chat(run_id: str, request: ChatRequest):
    """
    Interactive Chat Q&A: Runs conversational Python code in the sandbox 
    against the preserved standardized Parquet dataset snapshot to answer questions.
    """
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found.")
    run = runs[run_id]
    
    parquet_path = run.get("parquet_path")
    if not parquet_path or not os.path.exists(parquet_path):
        raise HTTPException(
            status_code=400, 
            detail="No active dataset session found for this run."
        )

    from config import get_llm, wait_for_quota
    from tools.sandbox_executor import execute_python
    import pandas as pd
    
    try:
        # Load small preview to extract accurate schema to guide the LLM
        df = pd.read_parquet(parquet_path)
        columns_str = str(list(df.columns))
        numeric_cols = list(df.select_dtypes(include="number").columns)
        date_cols = list(df.select_dtypes(include="datetime").columns)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read dataset: {e}")

    # Step 1: Prompt LLM to write the query Python script
    code_prompt = f"""\
You are an expert Python data analyst. Write a clean Python code snippet to query the pre-loaded pandas DataFrame `df` and help answer the user's question.

User Question: {request.message}

DataFrame Info:
- Columns: {columns_str}
- Numeric Columns: {numeric_cols}
- Date Columns: {date_cols}

RULES:
- Assign the key result, answer value, or formatted summary to a variable called `result`.
- If a chart is requested or highly useful to answer their question, use plt.figure() to plot it and add titles/labels. Do NOT call plt.show().
- Use plt.tight_layout() before plotting ends.
- Print clean, helpful intermediate values to stdout using print().
- Return ONLY executable Python code. No explanations, no markdown code fences, no generic chat comments.
"""
    wait_for_quota()
    llm = get_llm(temperature=0.1)
    
    try:
        code_response = llm.invoke(code_prompt)
        code = code_response.content.strip()
        
        if code.startswith("```"):
            lines = code.split("\n")
            code = "\n".join(lines[1:])
            if code.endswith("```"):
                code = code[:-3].strip()
                
        # Generate a unique chat step ID so charts don't overwrite analysis ones
        chat_step_id = f"chat_{uuid.uuid4().hex[:8]}"

        # Execute code in sandbox
        exec_result = execute_python.invoke({
            "code": code,
            "parquet_path": parquet_path,
            "step_id": chat_step_id
        })
    except Exception as ce:
        raise HTTPException(status_code=500, detail=f"Query execution initialization failed: {ce}")

    stdout = exec_result.get("stdout", "")
    res_val = str(exec_result.get("result", ""))
    charts = exec_result.get("charts", [])
    error = exec_result.get("error")

    # Step 2: Formulate the conversational explanation based on execution stdout/result/charts
    explain_prompt = f"""\
You are an elite boardroom business advisor. Formulate a direct, professional, conversational answer to the user's question using the outputs of the Python script that was executed against the dataset.

User Question: {request.message}
Executed Code:
```python
{code}
```
Console Outputs (Stdout):
{stdout}
Returned Value:
{res_val}
Error (if any):
{error}

INSTRUCTIONS:
- Explain what the numbers show clearly and factually.
- Do not use exclamation marks.
- If there is an error, explain it politely and suggest what they can query instead.
- If a chart was successfully generated, mention that the visualization is displayed.
- Keep your response direct, precise, and conversational.
"""
    wait_for_quota()
    explain_response = llm.invoke(explain_prompt)
    answer = explain_response.content.strip()

    # Re-map chart path to web URL
    chart_urls = []
    for c in charts:
        fname = Path(c["path"]).name
        chart_urls.append({
            "url": f"/charts/{fname}",
            "title": c.get("title", "Chat Chart")
        })

    return JSONResponse({
        "answer": answer,
        "charts": chart_urls,
        "error": error
    })


@app.post("/api/sync/{run_id}")
async def sync_database(run_id: str):
    """
    Active Sync: Triggers a fresh database sync and analysis run
    for SQLite database sources, refreshing the active session results.
    """
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found.")
    run = runs[run_id]

    source_type = run.get("source_type")
    source_config = run.get("source_config")
    metadata = run.get("metadata")
    benchmark = run.get("benchmark")

    if source_type != "sqlite":
        raise HTTPException(
            status_code=400, 
            detail="Active syncing is only supported for database (SQLite) sources."
        )

    # Re-trigger a fresh background thread run utilizing the exact same config
    new_run_id = str(uuid.uuid4())
    runs[new_run_id] = {
        "status": "running",
        "events": [],
        "result": None,
        "source_type": source_type,
        "source_config": source_config,
        "metadata": metadata,
        "benchmark": benchmark
    }

    # Run in background
    thread = threading.Thread(
        target=_run_analysis,
        args=(new_run_id, source_config.get("path"), source_type, source_config, metadata, benchmark),
        daemon=True,
    )
    thread.start()

    return JSONResponse({
        "message": "Sync triggered successfully.",
        "new_run_id": new_run_id
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
