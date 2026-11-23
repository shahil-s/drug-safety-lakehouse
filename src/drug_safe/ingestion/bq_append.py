"""Append parsed openFDA rows and one audit record.

`raw_load` decides which lines are rows. This module only adds those rows to
`raw.openfda_adverse_events` and one row to `audit.pipeline_runs`. A second
call adds more rows and leaves the earlier rows in place. The BigQuery client
is built only inside `BigQueryRowWriter`. Tests pass a fake writer instead.
"""

from __future__ import annotations

from typing import Protocol

from drug_safe.common.audit import AuditRecord
from drug_safe.ingestion.raw_load import RawLoad

RAW_TABLE = "raw.openfda_adverse_events"
AUDIT_TABLE = "audit.pipeline_runs"


class RowWriter(Protocol):
    """Adds rows to a table. Implementations must not delete or replace existing rows."""

    def append(self, table: str, rows: list[dict]) -> None:
        """Add `rows` to `table`."""


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


class BigQueryRowWriter:
    """Streaming insert into BigQuery. Inserts add rows and do not replace the table."""

    def __init__(self, project: str) -> None:
        self.project = project

    def append(self, table: str, rows: list[dict]) -> None:
        from google.cloud import bigquery  # imported lazily so tests need no GCP libs

        client = bigquery.Client(project=self.project)
        errors = client.insert_rows_json(f"{self.project}.{table}", rows)
        if errors:
            raise RuntimeError(errors)
