"""
Node 5b: Signal Evaluator
Analyzes execution outputs (stdout and return values) to mine for statistical 
anomalies, segment skews, high correlations, and spikes, updating the active signals queue.
"""

import json
from state import AnalysisState
from config import get_llm, wait_for_quota
from logger import trace, log

EVALUATOR_PROMPT = """\
You are an expert data auditor. Your role is to read the code, printed stdout, and raw return values of a completed analysis step, and extract "signals" or "anomalies" that merit deeper investigation.

Business Context: {business_context}
Step Executed: {step_title}
Objective: {step_objective}
Code Executed:
```python
{code}
```

Console Output (Stdout):
{stdout}

Returned Value:
{result}

Identify any:
1. Strong correlations (positive or negative > 0.5)
2. Segments with high variance, outliers, or high volumes
3. Sudden spikes, drops, or seasonal anomalies over time
4. Columns with extremely high missing ratios or poor data quality

Return a list of identified signals. Format each signal as a structured JSON object. 
Return ONLY a JSON array, no extra text, in this format:
[
  {{
    "metric": "name of column / KPI",
    "description": "brief description of the interesting signal, drop, spike, or correlation",
    "severity": "high" | "medium" | "low",
    "signal_type": "correlation" | "anomaly" | "trend" | "segment_skew" | "data_quality",
    "reasoning": "why does this signal warrant a deep-dive analysis?"
  }}
]
"""

def signal_evaluator_node(state: AnalysisState) -> dict:
    """Analyze the most recent step's stdout/results to extract business signals."""
    results = state.get("execution_results", {})
    idx = state.get("current_step_index", 0)
    
    # We want the results of the step that was just executed
    step_key = str(idx)
    if step_key not in results:
        log.warning("No execution result found for step index %s, skipping signal evaluation.", step_key)
        return {}

    step_data = results[step_key]
    trace.record("signal_evaluator", "start", {"step": step_data.get("title")})

    # Prepare inputs for the LLM
    business_context = state.get("business_context", "Generic")
    code = step_data.get("code", "")
    stdout = step_data.get("stdout", "")
    result_val = str(step_data.get("result", ""))
    
    # Limit stdout size to prevent token blowing
    if len(stdout) > 2000:
        stdout = stdout[:1000] + "\n... [TRUNCATED] ...\n" + stdout[-1000:]
        
    prompt = EVALUATOR_PROMPT.format(
        business_context=business_context,
        step_title=step_data.get("title", ""),
        step_objective=step_data.get("objective", ""),
        code=code,
        stdout=stdout,
        result=result_val[:1000]
    )

    wait_for_quota()
    llm = get_llm(temperature=0.1)
    
    try:
        response = llm.invoke(prompt)
        content = response.content
        if isinstance(content, list):
            content = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in content])
        
        content = content.strip()
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        new_signals = json.loads(content)
        if not isinstance(new_signals, list):
            new_signals = []
            
        log.info("Signal Evaluator mined %d new signals from execution output.", len(new_signals))
        
    except Exception as exc:
        log.error("Signal Evaluator parsing failed: %s. Defaulting to empty list.", exc)
        new_signals = []

    # Update global active signals list
    active_signals = list(state.get("active_signals", []))
    
    # Append the new signals and tag them with their source step
    for sig in new_signals:
        sig["discovered_in_step"] = step_data.get("title")
        active_signals.append(sig)

    # Store history of execution step details
    history = list(state.get("history_steps", []))
    history.append({
        "id": idx,
        "title": step_data.get("title"),
        "objective": step_data.get("objective"),
        "mined_signals": len(new_signals)
    })

    trace.record("signal_evaluator", "complete", {
        "new_signals_count": len(new_signals),
        "total_active_signals": len(active_signals)
    })

    return {
        "active_signals": active_signals,
        "history_steps": history
    }
