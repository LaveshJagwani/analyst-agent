"""
LangGraph StateGraph — assembles the full analysis pipeline.
"""

from langgraph.graph import StateGraph, END
from state import AnalysisState

# Import node functions
from nodes.metadata_parser import metadata_parser_node
from nodes.schema_analyzer import schema_analyzer_node
from nodes.context_classifier import context_classifier_node
from nodes.analysis_planner import analysis_planner_node
from nodes.code_executor import code_executor_node
from nodes.signal_evaluator import signal_evaluator_node
from nodes.dynamic_router import dynamic_router_node, should_continue_exploration
from nodes.insight_validator import insight_validator_node
from nodes.strategy_generator import strategy_generator_node
from nodes.benchmark_node import benchmark_node, should_run_benchmark
from nodes.design_planner import design_planner_node
from nodes.presentation_generator import presentation_generator_node
from nodes.report_generator import report_generator_node


def build_graph() -> StateGraph:
    """Build and compile the analyst agent graph."""

    graph = StateGraph(AnalysisState)

    # ── Add nodes ─────────────────────────────────────────────────────────────
    graph.add_node("metadata_parser", metadata_parser_node)
    graph.add_node("schema_analyzer", schema_analyzer_node)
    graph.add_node("context_classifier", context_classifier_node)
    graph.add_node("analysis_planner", analysis_planner_node)
    graph.add_node("code_executor", code_executor_node)
    graph.add_node("signal_evaluator", signal_evaluator_node)
    graph.add_node("dynamic_router", dynamic_router_node)
    graph.add_node("insight_validator", insight_validator_node)
    graph.add_node("strategy_generator", strategy_generator_node)
    graph.add_node("benchmark", benchmark_node)
    graph.add_node("design_planner", design_planner_node)
    graph.add_node("presentation_generator", presentation_generator_node)
    graph.add_node("report_generator", report_generator_node)

    # ── Set entry point ───────────────────────────────────────────────────────
    graph.set_entry_point("metadata_parser")

    # ── Linear edges ──────────────────────────────────────────────────────────
    graph.add_edge("metadata_parser", "schema_analyzer")
    graph.add_edge("schema_analyzer", "context_classifier")
    graph.add_edge("context_classifier", "analysis_planner")
    graph.add_edge("analysis_planner", "code_executor")
    graph.add_edge("code_executor", "signal_evaluator")
    graph.add_edge("signal_evaluator", "dynamic_router")

    # ── Code execution loop (conditional) ─────────────────────────────────────
    graph.add_conditional_edges(
        "dynamic_router",
        should_continue_exploration,
        {
            "continue": "code_executor",   # loop back to execution
            "done": "insight_validator",    # proceed to final validation
        },
    )

    # ── Post-validation ───────────────────────────────────────────────────────
    graph.add_edge("insight_validator", "strategy_generator")

    # ── Benchmark conditional ─────────────────────────────────────────────────
    graph.add_conditional_edges(
        "strategy_generator",
        should_run_benchmark,
        {
            "run": "benchmark",
            "skip": "design_planner",
        },
    )
    graph.add_edge("benchmark", "design_planner")
    graph.add_edge("design_planner", "presentation_generator")
    graph.add_edge("presentation_generator", "report_generator")

    # ── End ────────────────────────────────────────────────────────────────────
    graph.add_edge("report_generator", END)

    return graph.compile()


# Pre-compiled graph instance
analyst_graph = build_graph()
