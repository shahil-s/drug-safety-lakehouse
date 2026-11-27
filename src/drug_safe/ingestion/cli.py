"""Command line entry point: pull openFDA adverse events for a date window into the raw zone.

When `GCP_PROJECT` is set, the written JSONL files are appended to BigQuery.
Without it, the command only writes the local raw files and the local audit log.

Example:
    python -m drug_safe.ingestion.cli --start 2024-01-01 --end 2024-01-01 --max-records 500
"""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

from drug_safe.common.audit import AuditLogger, AuditRecord
from drug_safe.config import Settings
from drug_safe.ingestion.bq_append import BigQueryRowWriter, RowWriter, append_run
from drug_safe.ingestion.openfda_client import OpenFDAClient
from drug_safe.ingestion.raw_writer import RawWriter

log = logging.getLogger("drug_safe.ingestion")


def run(
    start: date,
    end: date,
    max_records: int | None,
    settings: Settings,
    row_writer: RowWriter | None = None,
    client: OpenFDAClient | None = None,
) -> AuditRecord:
    client = client or OpenFDAClient(api_key=settings.openfda_api_key)
    raw_writer = RawWriter(settings.raw_root)
    audit = AuditRecord(
        pipeline="openfda_drug_event_batch",
        actor=settings.actor,
        source="openfda:drug/event",
        parameters={"start": start.isoformat(), "end": end.isoformat(), "max_records": max_records},
    )
    audit_path = Path("./data/audit/pipeline_runs.jsonl")
    try:
        for part, page in enumerate(client.iter_pages(start, end, max_records=max_records)):
            if audit.records_expected is None:
                audit.records_expected = (
                    page.total if max_records is None else min(page.total, max_records)
                )
            if page.valid:
                path = raw_writer.partition_path(audit.run_id, start, end, part)
                data = raw_writer.to_jsonl(page.valid, audit.run_id, page.url)
                audit.output_files.append(raw_writer.write(path, data))
            audit.records_received += len(page.valid)
            audit.records_rejected += len(page.rejected)
            log.info("page %s: %s valid, %s rejected", part, len(page.valid), len(page.rejected))
        if audit.records_expected is None:
            audit.records_expected = 0
        audit.finish("SUCCEEDED")
        if row_writer is not None:
            append_run(audit, row_writer)
    except Exception as exc:  # record the failure, then re-raise
        audit.finish("FAILED", error=repr(exc))
        raise
    finally:
        AuditLogger(audit_path).write(audit)
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--max-records", type=int, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings.from_env()
    row_writer = BigQueryRowWriter(settings.gcp_project) if settings.gcp_project else None
    audit = run(args.start, args.end, args.max_records, settings, row_writer)
    log.info(
        "run %s %s: expected=%s received=%s rejected=%s reconciled=%s",
        audit.run_id,
        audit.status,
        audit.records_expected,
        audit.records_received,
        audit.records_rejected,
        audit.reconciled,
    )


if __name__ == "__main__":
    main()
