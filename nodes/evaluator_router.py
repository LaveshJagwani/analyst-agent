"""
Node 5b: Combined Evaluator & Router
LLM node (structured output) — evaluates execution outputs to extract business signals and decides whether to pivot/deep-dive or finish exploration.
"""

import json
from state import AnalysisState
from config import get_llm, wait_for_quota
from logger import trace, log


EVALUATOR_ROUTER_PROMPT = """\
You are a Principal Lead Business Analyst directing an autonomous analyst agent.
Your task is to analyze the most recent execution step's stdout, output values, and history to:
1. Identify any new critical signals or anomalies (strong correlations, variance skews, outliers, trends, data quality issues).
2. Decide whether to pivot to a deep-dive step (if a high-priority signal is found) or complete exploration.

---
### Business Context & Goals:
- Domain: {business_context}
- Industry / Domain: {industry}
- Primary Goal: {primary_goal}
- Focus KPIs: {kpis}
- Target Audience: {target_audience}
- Persistent rules (Playbook): {rules}

---
### Data Profile:
- Columns: {columns}
- Row count: {row_count}

---
### Analysis History (Steps Executed So Far):
{history}

---
### Mined Active Data Signals Queue (Before Current Step):
{active_signals}

---
### Sandbox Execution Results (Step: {step_title}):
- Code Run:
```python
{code}
```
- Console Stdout:
{stdout}
- Returned Value:
{result}

---
### Current Step Budget Status:
- Exploratory Steps Taken: {steps_taken}
- Max Deep-Dives Budget: {budget}

---
### Decision Guidelines:
1. **Pivot & Deep-Dive**: If you find an active signal (an anomaly, strong correlation, or trend segment) in the execution outputs or queue that directly impacts the **Primary Business Goal** or **Focus KPIs**, and the budget is not exhausted, you should design a custom deep-dive step. Give it a highly specific title, objective, and pandas/matplotlib methodology hint.
2. **Complete Exploration**: If you have fully investigated the primary goals, if there are no high-value active signals left, or if you have reached the step budget limit ({budget} steps), decide to complete the exploration phase.

Select ONE option. Return ONLY a JSON object in this format (no markdown, no extra explanation):
For Pivot & Deep-Dive:
{{
  "discovered_signals": [
    {{
      "metric": "name of column / KPI",
      "description": "brief description of the interesting signal, drop, spike, or correlation",
      "severity": "high" | "medium" | "low",
      "signal_type": "correlation" | "anomaly" | "trend" | "segment_skew" | "data_quality",
      "reasoning": "why does this signal warrant a deep-dive analysis?"
    }}
  ],
  "decision": "pivot",
  "next_step": {{
    "title": "A highly descriptive specific title (e.g. 'Paid Search ROI Segmented Decay Analysis')",
    "objective": "Exactly what business mystery we are trying to solve",
    "method": "The concrete pandas/seaborn/matplotlib code approach to execute"
  }},
  "reasoning": "Explain why this signal is high priority based on the goal."
}}

For Complete Exploration:
{{
  "discovered_signals": [
    {{
      "metric": "name of column / KPI",
      "description": "brief description of the interesting signal, drop, spike, or correlation",
      "severity": "high" | "medium" | "low",
      "signal_type": "correlation" | "anomaly" | "trend" | "segment_skew" | "data_quality",
      "reasoning": "why does this signal warrant a deep-dive analysis?"
    }}
  ],
  "decision": "complete",
  "reasoning": "Explain why the current findings are comprehensive or the budget is exhausted."
}}
"""


def evaluator_router_node(state: AnalysisState) -> dict:
    """Evaluate step outputs and route: extract signals and decide next analysis step."""
    results = state.get("execution_results", {})
    idx = state.get("current_step_index", 0)
    budget = state.get("max_steps_budget", 5)
    history = list(state.get("history_steps", []))
    active_signals = list(state.get("active_signals", []))
    plan = list(state.get("analysis_plan", []))

    # Retrieve step results
    step_key = str(idx)
    if step_key not in results:
        log.warning("No execution result found for step index %s, skipping evaluator router evaluation.", step_key)
        return {}

    step_data = results[step_key]
    trace.record("evaluator_router", "start", {"step": step_data.get("title")})

    # Prepare inputs for the prompt
    schema = state.get("schema", {})
    summary = state.get("dataframe_summary", {})
    metadata = state.get("parsed_metadata") or {}
    business_context = state.get("business_context", "Generic")

    history_str = "\n".join([f"- Step {h['id']}: {h['title']} (Mined {h['mined_signals']} signals)" for h in history])
    if not history_str:
        history_str = "No steps executed yet."

    signals_str = ""
    for s in active_signals:
        signals_str += f"- [{s.get('signal_type', 'info').upper()} (Severity: {s.get('severity')})] metric '{s.get('metric')}': {s.get('description')} (Reasoning: {s.get('reasoning')})\n"
    if not signals_str:
        signals_str = "No active signals found in the queue."

    code = step_data.get("code", "")
    stdout = step_data.get("stdout", "")
    result_val = str(step_data.get("result", ""))

    # Truncate stdout/result to protect tokens
    if len(stdout) > 2000:
        stdout = stdout[:1000] + "\n... [TRUNCATED] ...\n" + stdout[-1000:]

    prompt = EVALUATOR_ROUTER_PROMPT.format(
        business_context=business_context,
        industry=metadata.get("industry", "Generic"),
        primary_goal=metadata.get("primary_goal", "Extract general trends"),
        kpis=", ".join(metadata.get("important_kpis", ["Revenue", "Volume"])),
        target_audience=metadata.get("target_audience", "Not specified"),
        rules=", ".join(metadata.get("playbook_rules", ["None"])),
        columns=list(schema.get("columns", {}).keys()),
        row_count=summary.get("row_count", "unknown"),
        history=history_str,
        active_signals=signals_str,
        step_title=step_data.get("title", ""),
        code=code,
        stdout=stdout,
        result=result_val[:1000],
        steps_taken=len(history),
        budget=budget
    )

    # Call LLM
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

        decision_data = json.loads(content)
    except Exception as exc:
        log.error("Failed to parse evaluator router response JSON: %s. Defaulting to complete.", exc)
        decision_data = {"decision": "complete", "discovered_signals": [], "reasoning": "Fallback on parsing error"}

    # Process discovered signals
    new_signals = decision_data.get("discovered_signals", [])
    if not isinstance(new_signals, list):
        new_signals = []

    # Tag and append signals
    for sig in new_signals:
        sig["discovered_in_step"] = step_data.get("title")
        active_signals.append(sig)

    # Append to step history
    history.append({
        "id": idx,
        "title": step_data.get("title"),
        "objective": step_data.get("objective"),
        "mined_signals": len(new_signals)
    })

    # Evaluate decision
    decision = decision_data.get("decision", "complete")
    reasoning = decision_data.get("reasoning", "")
    log.info("Evaluator Router Step %d mined %d signals. Decision: %s. Reasoning: %s", idx, len(new_signals), decision.upper(), reasoning)

    if decision == "pivot" and "next_step" in decision_data and len(history) < budget:
        next_step_raw = decision_data["next_step"]
        next_id = len(plan) + 1
        new_step = {
            "id": next_id,
            "title": next_step_raw.get("title", f"Dynamic Deep Dive {next_id}"),
            "objective": next_step_raw.get("objective", "Deeper segmentation check"),
            "method": next_step_raw.get("method", "Standard descriptive plot")
        }
        plan.append(new_step)

        trace.record("evaluator_router", "pivot", {
            "new_step": new_step,
            "reasoning": reasoning,
            "new_signals_count": len(new_signals),
            "total_active_signals": len(active_signals)
        })

        return {
            "analysis_plan": plan,
            "active_signals": active_signals,
            "history_steps": history,
            "decision_route": "pivot"
        }

    # Default complete exploration path
    trace.record("evaluator_router", "complete", {
        "reasoning": reasoning,
        "new_signals_count": len(new_signals),
        "total_active_signals": len(active_signals)
    })

    return {
        "active_signals": active_signals,
        "history_steps": history,
        "decision_route": "complete"
    }


def should_continue_exploration(state: AnalysisState) -> str:
    """Conditional edge: decide whether to loop back to execution or complete exploration."""
    idx = state.get("current_step_index", 0)
    plan = state.get("analysis_plan", [])
    
    # If the step index is less than the plan length, it means evaluator_router
    # added a new deep-dive step, so we continue. Otherwise, we are done.
    if idx < len(plan):
        return "continue"
    return "done"
