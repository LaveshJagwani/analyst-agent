"""
Node 3: Business Context Classifier
LLM node — classifies the dataset into a business domain.
"""

from state import AnalysisState
from config import get_llm, wait_for_quota
from logger import trace, log

VALID_CONTEXTS = ["Sales", "Marketing", "SaaS", "Churn", "Finance", "Inventory", "Generic"]

CLASSIFY_PROMPT = """\
You are a business context classifier. Given a dataset schema and optional metadata,
classify the business domain of this data into EXACTLY ONE of:
{contexts}

Dataset columns: {columns}
Column types: {col_types}
Sample data: {sample}

{metadata_section}

Reply with ONLY the category name, nothing else.
"""


def context_classifier_node(state: AnalysisState) -> dict:
    """Classify the business context using schema + metadata."""
    trace.record("context_classifier", "start")

    schema = state.get("schema", {})
    summary = state.get("dataframe_summary", {})
    metadata = state.get("parsed_metadata")

    # If metadata explicitly provides industry, map it
    if metadata and metadata.get("industry"):
        industry = metadata["industry"].strip().title()
        # Try to match to a valid context
        for ctx in VALID_CONTEXTS:
            if ctx.lower() in industry.lower() or industry.lower() in ctx.lower():
                log.info("Business context from metadata: %s", ctx)
                trace.record("context_classifier", "from_metadata", ctx)
                return {"business_context": ctx}

    # Otherwise, ask the LLM
    metadata_section = ""
    if metadata:
        metadata_section = f"Business metadata: {metadata}"

    columns = list(schema.get("columns", {}).keys())
    col_types = schema.get("columns", {})
    sample = summary.get("sample_rows", [])[:3]

    prompt = CLASSIFY_PROMPT.format(
        contexts=", ".join(VALID_CONTEXTS),
        columns=columns,
        col_types=col_types,
        sample=sample,
        metadata_section=metadata_section,
    )

    wait_for_quota()
    llm = get_llm(temperature=0.0)
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
        
    context = content.strip()

    # Validate
    matched = None
    for ctx in VALID_CONTEXTS:
        if ctx.lower() == context.lower():
            matched = ctx
            break
    if not matched:
        log.warning("LLM returned '%s', defaulting to Generic.", context)
        matched = "Generic"

    log.info("Business context classified: %s", matched)
    trace.record("context_classifier", "classified", matched)
    return {"business_context": matched}
