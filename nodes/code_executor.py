"""
Node 5: Code Execution Loop
Tool-using LLM node — generates and executes Python code for each analysis step.
"""

import json
from state import AnalysisState
from config import get_llm, wait_for_quota
from tools.sandbox_executor import execute_python
from logger import trace, log


CODE_GEN_PROMPT = """\
You are a Python data analyst. Write executable Python code for this analysis step.

Step: {title}
Objective: {objective}
Method hint: {method}

The variable `df` is a pre-loaded pandas DataFrame with columns:
{columns}

Numeric columns: {numeric_cols}
Date columns: {date_cols}

RULES:
- Use pandas, numpy, matplotlib, seaborn only.
- Assign the key result (number, dict, or small dataframe) to a variable called `result`.
- If creating a chart, use plt.figure() and give it a descriptive title.
- Use plt.tight_layout() before the end.
- Do NOT call plt.show().
- Handle potential errors (e.g., missing columns) gracefully.
- Print important intermediate values.

Return ONLY the Python code, no markdown, no explanation.
"""


def code_executor_node(state: AnalysisState) -> dict:
    """Execute the current analysis step by generating and running Python code."""
    plan = state.get("analysis_plan", [])
    idx = state.get("current_step_index", 0)
    schema = state.get("schema", {})

    if idx >= len(plan):
        trace.record("code_executor", "all_steps_done")
        return {}

    step = plan[idx]
    step_id = step.get("id", idx + 1)
    log.info("Executing step %d/%d: %s", idx + 1, len(plan), step.get("title"))
    trace.record("code_executor", "step_start", step)

    # Generate code
    prompt = CODE_GEN_PROMPT.format(
        title=step.get("title", ""),
        objective=step.get("objective", ""),
        method=step.get("method", ""),
        columns=list(schema.get("columns", {}).keys()),
        numeric_cols=schema.get("numeric_columns", []),
        date_cols=schema.get("date_columns", []),
    )

    wait_for_quota()
    llm = get_llm(temperature=0.1)
    response = llm.invoke(prompt)
    
    content = response.content
    if isinstance(content, list):
        # Handle list content (common with Gemini)
        text_parts = []
        for part in content:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                text_parts.append(part["text"])
        content = "".join(text_parts)
    
    if not isinstance(content, str):
        content = str(content)
        
    code = content.strip()

    # Strip markdown code fences if present
    if code.startswith("```"):
        lines = code.split("\n")
        code = "\n".join(lines[1:])
        if code.endswith("```"):
            code = code[:-3].strip()

    trace.record("code_executor", "generated_code", code)

    # Execute
    exec_result = execute_python.invoke({
        "code": code,
        "parquet_path": state["parquet_path"],
        "step_id": step_id,
    })

    trace.record("code_executor", "execution_result", {
        "stdout": exec_result.get("stdout", "")[:500],
        "result": str(exec_result.get("result", ""))[:500],
        "charts": exec_result.get("charts", []),
        "error": exec_result.get("error"),
    })

    if exec_result.get("error"):
        log.warning("Step %d execution error: %s", step_id, exec_result["error"][:200])

    # Update state
    results = dict(state.get("execution_results", {}))
    results[str(step_id)] = {
        "title": step.get("title"),
        "code": code,
        "stdout": exec_result.get("stdout", ""),
        "result": exec_result.get("result"),
        "error": exec_result.get("error"),
        "charts": exec_result.get("charts", []), # This is now a list of dicts
    }

    # Maintain a global flat list of paths for legacy reasons/simplicity in some tools
    new_chart_paths = [c["path"] if isinstance(c, dict) else c for c in exec_result.get("charts", [])]
    charts = list(state.get("generated_charts", []))
    charts.extend(new_chart_paths)

    return {
        "execution_results": results,
        "generated_charts": charts,
        "current_step_index": idx + 1,
    }


def should_continue_execution(state: AnalysisState) -> str:
    """Conditional edge: loop back or proceed to validation."""
    idx = state.get("current_step_index", 0)
    plan = state.get("analysis_plan", [])
    if idx < len(plan):
        return "continue"
    return "done"
