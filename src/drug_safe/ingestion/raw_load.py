"""Turn a raw openFDA JSONL file into rows for raw.openfda_adverse_events.

Each line is the envelope written by RawWriter. A line that is not a JSON object,
or that has no string `_ingest_id` or `_fetched_at`, is returned with a reason
and is not a row. This module does not call BigQuery. Appending is the caller's
job: concatenate the rows from each file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RejectedLine:
    line_number: int
    reason: str
    text: str


@dataclass(frozen=True)
class RawLoad:
    rows: list[dict]
    rejected: list[RejectedLine]

    @property
    def records_received(self) -> int:
        return len(self.rows)

    @property
    def records_rejected(self) -> int:
        return len(self.rejected)


def parse_line(line: str, line_number: int) -> dict | RejectedLine:
    """Return one table row, or a rejection. The payload object is not copied."""
    if line.strip() == "":
        return RejectedLine(line_number, "empty line", line)
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError:
        return RejectedLine(line_number, "invalid json", line)
    if not isinstance(parsed, dict):
        return RejectedLine(line_number, "line is not an object", line)
    field_error = _required_field_error(parsed)
    if field_error is not None:
        return RejectedLine(line_number, field_error, line)
    return {
        "_ingest_id": parsed["_ingest_id"],
        "_source_url": parsed.get("_source_url"),
        "_fetched_at": parsed["_fetched_at"],
        "payload": parsed.get("payload"),
    }


def load_jsonl(text: str) -> RawLoad:
    """Parse a whole JSONL document. A trailing newline does not add a row."""
    rows: list[dict] = []
    rejected: list[RejectedLine] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        item = parse_line(line, line_number)
        if isinstance(item, RejectedLine):
            rejected.append(item)
        else:
            rows.append(item)
    return RawLoad(rows, rejected)


def load_path(path: str | Path) -> RawLoad:
    """Read one local JSONL file. The caller appends the rows to a destination."""
    return load_jsonl(Path(path).read_text(encoding="utf-8"))


def _required_field_error(record: dict) -> str | None:
    for key in ("_ingest_id", "_fetched_at"):
        value = record.get(key)
        if value is None or value == "":
            return f"missing {key}"
        if not isinstance(value, str):
            return f"{key} is not a string"
    return None
