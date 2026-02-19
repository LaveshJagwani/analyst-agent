"""
Execution trace logger for the Analyst Agent.
Logs every node's actions to a JSON trace file and console.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from config import TRACE_DIR

# ── Console logger ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("analyst_agent")


class TraceLogger:
    """Append-only JSON-lines trace file for full execution audit."""

    def __init__(self):
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.path = TRACE_DIR / f"trace_{ts}.jsonl"
        self.entries: list[dict] = []
        log.info("Trace file: %s", self.path)

    def record(self, node: str, event: str, data: dict | str | None = None):
        """Record a trace entry."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node": node,
            "event": event,
            "data": data,
        }
        self.entries.append(entry)
        # Append to file immediately so nothing is lost on crash
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        log.info("[%s] %s", node, event)

    def get_entries(self) -> list[dict]:
        return list(self.entries)


# Singleton instance used by all nodes
trace = TraceLogger()
