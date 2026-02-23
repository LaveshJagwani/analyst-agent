"""
Global state definition and data models for the Analyst Agent.
"""

from __future__ import annotations
from typing import TypedDict, Optional
from pydantic import BaseModel, Field


# ── Pydantic data models ─────────────────────────────────────────────────────

class ParsedMetadata(BaseModel):
    """Structured representation of user-supplied business metadata."""
    industry: Optional[str] = None
    business_model: Optional[str] = None
    company_stage: Optional[str] = None
    primary_goal: Optional[str] = None
    region: Optional[str] = None
    important_kpis: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


class AnalysisStep(BaseModel):
    """A single step in the analysis plan."""
    id: int
    title: str
    objective: str
    method: str


class Insight(BaseModel):
    """A validated business insight."""
    title: str
    description: str
    metric_value: Optional[str] = None
    confidence: str = "medium"  # low | medium | high
    supporting_data: Optional[str] = None


class Recommendation(BaseModel):
    """A strategic recommendation."""
    action: str
    rationale: str
    expected_impact: str
    risk: str
    suggested_next_step: str


class Slide(BaseModel):
    """A single slide in the presentation payload."""
    title: str
    content: list[str]
    chart_reference: Optional[str] = None
    speaker_notes: Optional[str] = None


# ── LangGraph State ──────────────────────────────────────────────────────────

class AnalysisState(TypedDict, total=False):
    """Global state persisted across all LangGraph nodes."""

    # Inputs
    file_path: str
    raw_metadata_input: Optional[str | dict]
    parsed_metadata: Optional[dict]

    # Schema & data profile
    dataframe_summary: dict        # row_count, columns list, sample rows, etc.
    schema: dict                   # column types, missing %, date/num/cat lists

    # Context
    business_context: str          # Sales | Marketing | SaaS | Churn | Finance | Inventory | Generic

    # Analysis plan
    analysis_plan: list[dict]
    current_step_index: int

    # Execution
    execution_results: dict        # step_id -> result dict
    generated_charts: list[str]    # file paths of saved charts

    # Insights & strategy
    validated_insights: list[dict]
    recommendations: list[dict]

    # Benchmarking
    benchmark_enabled: bool
    benchmark_results: Optional[dict]

    # Presentation
    presentation_payload: Optional[dict]
    presentation_design: Optional[dict]

    # Logging
    trace_log: list[dict]
