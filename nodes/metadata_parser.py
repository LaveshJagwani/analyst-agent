"""
Node 1: Metadata Intake & Parsing
Parses unstructured or structured metadata into a normalized dict.
"""

import json
from state import AnalysisState
from config import get_llm, wait_for_quota
from logger import trace, log


PARSE_PROMPT = """\
You are a business metadata parser. Given the user's input about their company,
extract structured metadata.

Return ONLY a valid JSON object with these fields (use null if unknown):
{{
  "industry": str or null,
  "business_model": str or null,
  "company_stage": str or null,
  "primary_goal": str or null,
  "region": str or null,
  "important_kpis": [list of strings] or [],
  "notes": str or null
}}

User input:
{input}
"""


def metadata_parser_node(state: AnalysisState) -> dict:
    """Parse raw metadata input into structured fields."""
    raw = state.get("raw_metadata_input")
    trace.record("metadata_parser", "start", {"raw_input_type": type(raw).__name__})

    # Case 1: No metadata provided
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        log.info("No metadata provided — skipping parsing.")
        trace.record("metadata_parser", "skip", "No metadata provided")
        return {"parsed_metadata": None}

    # Case 2: Already structured dict / JSON string
    if isinstance(raw, dict):
        trace.record("metadata_parser", "structured_input", raw)
        return {"parsed_metadata": raw}

    if isinstance(raw, str):
        # Try direct JSON parse first
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                trace.record("metadata_parser", "json_parsed", parsed)
                return {"parsed_metadata": parsed}
        except json.JSONDecodeError:
            pass

        # Case 3: Unstructured text → LLM parsing
        log.info("Parsing unstructured metadata with LLM...")
        wait_for_quota()
        llm = get_llm(temperature=0.0)
        prompt = PARSE_PROMPT.format(input=raw)
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
            
        content = content.strip()

        # Extract JSON from potential markdown code block
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        try:
            parsed = json.loads(content)
            trace.record("metadata_parser", "llm_parsed", parsed)
            return {"parsed_metadata": parsed}
        except json.JSONDecodeError:
            log.warning("LLM returned invalid JSON. Storing as notes.")
            trace.record("metadata_parser", "llm_parse_failed", content)
            return {"parsed_metadata": {"notes": raw}}

    # Fallback
    trace.record("metadata_parser", "fallback", str(raw))
    return {"parsed_metadata": {"notes": str(raw)}}
