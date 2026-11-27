"""Append parsed openFDA rows and one audit record.

`raw_load` decides which lines are rows. This module only adds those rows to
`raw.openfda_adverse_events` and one row to `audit.pipeline_runs`. A second
call adds more rows and leaves the earlier rows in place. The BigQuery client
is built only inside `BigQueryRowWriter`. Tests pass a fake writer instead.
"""

from __future__ import annotations

import json
from typing import Protocol

from drug_safe.common.audit import AuditRecord
from drug_safe.ingestion.raw_load import RawLoad, load_path

RAW_TABLE = "raw.openfda_adverse_events"
AUDIT_TABLE = "audit.pipeline_runs"
# Streaming insert treats a dict as a RECORD. These columns are JSON.
JSON_COLUMNS = {
    RAW_TABLE: ("payload",),
    AUDIT_TABLE: ("parameters", "output_files"),
}


class RowWriter(Protocol):
    """Adds rows to a table. Implementations must not delete or replace existing rows."""

    def append(self, table: str, rows: list[dict]) -> None:
        """Add `rows` to `table`."""


def rows_for_streaming_insert(table: str, rows: list[dict]) -> list[dict]:
    """Copy `rows` and encode this table's JSON columns as strings.

    `insert_rows_json` rejects a dict in a JSON column with "not a record".
    The caller's row objects are left unchanged.
    """
    columns = JSON_COLUMNS.get(table, ())
    encoded: list[dict] = []
    for row in rows:
        item = dict(row)
        for key in columns:
            value = item.get(key)
            if value is not None and not isinstance(value, str):
                item[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
        encoded.append(item)
    return encoded


def audit_row(record: AuditRecord) -> dict:
    """One `audit.pipeline_runs` row. Counts come from the record as it stands."""
    return {
        "run_id": record.run_id,
        "pipeline": record.pipeline,
        "actor": record.actor,
        "source": record.source,
        "parameters": record.parameters,
        "started_at": record.started_at,
        "ended_at": record.ended_at,
        "status": record.status,
        "records_expected": record.records_expected,
        "records_received": record.records_received,
        "records_rejected": record.records_rejected,
        "reconciled": record.reconciled,
        "output_files": record.output_files,
        "error": record.error,
    }


def append_load(load: RawLoad, audit: AuditRecord, writer: RowWriter) -> None:
    """Copy this load's counts onto `audit`, then append the raw rows and one audit row.

    The raw rows are the same dicts `load` holds, including `payload`. An empty
    load still writes the audit row so a run that rejected every line is recorded.
    """
    audit.records_received = load.records_received
    audit.records_rejected = load.records_rejected
    if load.rows:
        writer.append(RAW_TABLE, load.rows)
    writer.append(AUDIT_TABLE, [audit_row(audit)])


def append_run(audit: AuditRecord, writer: RowWriter) -> None:
    """Append every local file on this run, then one audit row.

    The counts already on `audit` come from the API. A report with no
    safetyreportid never enters the file, so those rejects must stay.
    `append_load` replaces both counts with one file's parse result and writes
    an audit row per call. A run may have several part files and must write one
    audit row, so this function parses the files and only moves lines that fail
    parsing from received to rejected.
    """
    rows: list[dict] = []
    file_rejected = 0
    for item in audit.output_files:
        path = str(item["path"])
        if path.startswith("gs://"):
            raise ValueError(
                "append_run reads a local JSONL file. "
                "A gs:// object is loaded by a later batch step."
            )
        load = load_path(path)
        rows.extend(load.rows)
        file_rejected += load.records_rejected
    if file_rejected > audit.records_received:
        raise ValueError(
            f"file parser rejected {file_rejected} lines "
            f"but the run received {audit.records_received}"
        )
    audit.records_received -= file_rejected
    audit.records_rejected += file_rejected
    if rows:
        writer.append(RAW_TABLE, rows)
    writer.append(AUDIT_TABLE, [audit_row(audit)])


class BigQueryRowWriter:
    """Streaming insert into BigQuery. Inserts add rows and do not replace the table."""

    def __init__(self, project: str) -> None:
        self.project = project

    def append(self, table: str, rows: list[dict]) -> None:
        from google.cloud import bigquery  # imported lazily so tests need no GCP libs

        client = bigquery.Client(project=self.project)
        encoded = rows_for_streaming_insert(table, rows)
        errors = client.insert_rows_json(f"{self.project}.{table}", encoded)
        if errors:
            raise RuntimeError(errors)
