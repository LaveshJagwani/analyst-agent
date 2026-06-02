"""
Node 5c: Dynamic Router / Pivot Engine
The main agentic branch node. Reviews active data signals, business metadata, and step history 
to decide whether to generate a custom deep-dive step (looping back) or finish exploration.
"""

import json
from state import AnalysisState
from config import get_llm, wait_for_quota
from logger import trace, log


ROUTER_PROMPT = """\
You are a Principal Lead Business Analyst. You are directing an autonomous, stateful agent that is exploring a dataset to extract deep, validated, non-obvious business insights.

Instead of running a pre-defined static checklist, you work dynamically: you explore, discover anomalies/signals, and decide whether to deep-dive, pivot, or finish.

---
### Business Context & Goals:
- Business context: {business_context}
- Industry / Domain: {industry}
- Primary Business Goal: {primary_goal}
- Focus KPIs: {kpis}
- Target Audience: {target_audience}
- persistent rules (Playbook): {rules}

---
### Data Profile:
- Columns: {columns}
- Row count: {row_count}

---
### Analysis History (Steps Executed So Far):
{history}

---
### Mined Active Data Signals Queue:
{active_signals}

---
### Current Step Budget Status:
- Exploratory Steps Taken: {steps_taken}
- Max Deep-Dives Budget: {budget}

---
### Decision Guidelines:
1. **Pivot & Deep-Dive**: If there is an active signal (an anomaly, strong correlation, or trend segment) that directly impacts the **Primary Business Goal** or **Focus KPIs**, and the budget is not exhausted, you should design a custom deep-dive step. Give it a highly specific title, objective, and pandas/matplotlib methodology hint.
2. **Complete Exploration**: If you have fully investigated the primary goals, if there are no high-value active signals left, or if you have reached the step budget limit ({budget} steps), decide to complete the exploration phase.

Select ONE option. Return ONLY a JSON object in this format (no markdown, no extra explanation):
For Pivot & Deep-Dive:
{{
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
  "decision": "complete",
  "reasoning": "Explain why the current findings are comprehensive or the budget is exhausted."
}}
"""


def dynamic_router_node(state: AnalysisState) -> dict:
    """Decide agentic branching: generate next step or proceed to insights validation."""
    trace.record("dynamic_router", "start")

    idx = state.get("current_step_index", 0)
    budget = state.get("max_steps_budget", 5)
    history = state.get("history_steps", [])
    active_signals = state.get("active_signals", [])
    plan = list(state.get("analysis_plan", []))

    # Guardrail check: if we already ran max budget steps, auto-complete
    if len(history) >= budget:
        log.info("Step budget reached (%d/%d). Terminating exploration loop.", len(history), budget)
        trace.record("dynamic_router", "budget_exhausted", {"taken": len(history), "budget": budget})
        return {"decision_route": "complete"}

    # Prepare inputs for prompt
    schema = state.get("schema", {})
    summary = state.get("dataframe_summary", {})
    metadata = state.get("parsed_metadata") or {}
    business_context = state.get("business_context", "Generic")

    history_str = "\n".join([f"- Step {h['id']}: {h['title']} (Mined {h['mined_signals']} signals)" for h in history])
    if not history_str:
        history_str = "No steps executed yet."

    # Filter/format signals list
    signals_str = ""
    for s in active_signals:
        signals_str += f"- [{s.get('signal_type', 'info').upper()} (Severity: {s.get('severity')})] metric '{s.get('metric')}': {s.get('description')} (Reasoning: {s.get('reasoning')})\n"
    if not signals_str:
        signals_str = "No active signals found in the queue."

    prompt = ROUTER_PROMPT.format(
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
        steps_taken=len(history),
        budget=budget
    )

    wait_for_quota()
    llm = get_llm(temperature=0.2)
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

    try:
        decision_data = json.loads(content)
        decision = decision_data.get("decision", "complete")
        reasoning = decision_data.get("reasoning", "")
    except Exception as exc:
        log.error("Failed to parse dynamic router decision JSON: %s. Defaulting to complete.", exc)
        decision = "complete"
        reasoning = "JSON parsing failure fallback"
        decision_data = {}

    log.info("Dynamic Router Decision: %s. Reasoning: %s", decision.upper(), reasoning)

    if decision == "pivot" and "next_step" in decision_data:
        next_step_raw = decision_data["next_step"]
        # Generate clean ID and step structure
        next_id = len(plan) + 1
        new_step = {
            "id": next_id,
            "title": next_step_raw.get("title", f"Dynamic Deep Dive {next_id}"),
            "objective": next_step_raw.get("objective", "Deeper segmentation check"),
            "method": next_step_raw.get("method", "Standard descriptive plot")
        }
        
        # Append to our runtime plan list
        plan.append(new_step)

        trace.record("dynamic_router", "pivot", {
            "new_step": new_step,
            "reasoning": reasoning
        })

        return {
            "analysis_plan": plan,
            "decision_route": "pivot"
        }

    trace.record("dynamic_router", "complete", {"reasoning": reasoning})
    return {
        "decision_route": "complete"
    }


def should_continue_exploration(state: AnalysisState) -> str:
    """Conditional edge router: loops back to execution or completes exploration."""
    # We retrieve the custom variable set by the dynamic router node
    # Since nodes write directly to state, we can return the decision_route
    # which is either 'pivot' or 'complete'
    # Wait, we need to ensure the router returned this in its payload!
    # Let's check how the dynamic_router node returns it:
    # It returns 'decision_route' along with plan updates.
    # But since LangGraph merges node outputs into the state, we should have
    # a dedicated flag or we can read the history vs budget to make it deterministic,
    # OR we can just write the 'decision_route' directly in state.py!
    # Wait, in state.py we did not add 'decision_route' directly, but TypedDict in python allows total=False keys,
    # or we can read state.get("analysis_plan") and current_step_index.
    # Let's make it robust:
    idx = state.get("current_step_index", 0)
    plan = state.get("analysis_plan", [])
    
    # If the step index is less than the plan length, it means the router added a new step
    # and we need to execute it!
    if idx < len(plan):
        return "continue"
        
    return "done"
