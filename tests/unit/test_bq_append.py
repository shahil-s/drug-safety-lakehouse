from datetime import date
from pathlib import Path

import pytest

from drug_safe.common.audit import AuditRecord
from drug_safe.ingestion.bq_append import AUDIT_TABLE, RAW_TABLE, append_load, append_run
from drug_safe.ingestion.raw_load import RawLoad, RejectedLine
from drug_safe.ingestion.raw_writer import RawWriter


class MemoryWriter:
    """Records appended rows in order. A second append extends the list."""

    def __init__(self) -> None:
        self.tables: dict[str, list[dict]] = {}

    def append(self, table: str, rows: list[dict]) -> None:
        self.tables.setdefault(table, []).extend(rows)


def _audit() -> AuditRecord:
    return AuditRecord(
        pipeline="openfda_drug_event_batch",
        actor="test",
        source="openfda:drug/event",
        parameters={"start": "2024-01-02", "end": "2024-01-02"},
        run_id="run-1",
        records_expected=2,
    )


def test_payload_is_appended_unchanged():
    payload = {"safetyreportid": "123", "patient": {"reaction": [{"reactionmeddrapt": "Nausea"}]}}
    load = RawLoad(
        rows=[
            {
                "_ingest_id": "run-1",
                "_source_url": "https://api.fda.gov/drug/event.json",
                "_fetched_at": "2024-01-02T00:00:00.000Z",
                "payload": payload,
            }
        ],
        rejected=[],
    )
    writer = MemoryWriter()

    append_load(load, _audit(), writer)

    stored = writer.tables[RAW_TABLE][0]
    assert stored["payload"] == payload
    assert stored["payload"] is payload


def test_second_append_keeps_the_first_run():
    def row(ingest_id: str, report_id: str) -> dict:
        return {
            "_ingest_id": ingest_id,
            "_source_url": "https://api.fda.gov/drug/event.json",
            "_fetched_at": "2024-01-02T00:00:00.000Z",
            "payload": {"safetyreportid": report_id},
        }

    writer = MemoryWriter()
    first = _audit()
    second = _audit()
    second.run_id = "run-2"
    append_load(RawLoad(rows=[row("run-1", "123")], rejected=[]), first, writer)
    append_load(RawLoad(rows=[row("run-2", "456")], rejected=[]), second, writer)

    stored = writer.tables[RAW_TABLE]
    assert [item["_ingest_id"] for item in stored] == ["run-1", "run-2"]
    assert stored[0]["payload"] == {"safetyreportid": "123"}


def test_audit_row_records_the_rejected_count():
    load = RawLoad(
        rows=[],
        rejected=[RejectedLine(line_number=1, reason="invalid json", text="not-json")],
    )
    audit = _audit()
    audit.records_expected = 1
    writer = MemoryWriter()

    append_load(load, audit, writer)

    assert RAW_TABLE not in writer.tables
    stored = writer.tables[AUDIT_TABLE][0]
    assert stored["run_id"] == "run-1"
    assert stored["records_received"] == 0
    assert stored["records_rejected"] == 1
    assert stored["reconciled"] is True


def _written_part(tmp_path, ingest_id: str, record: dict, part: int = 0) -> dict:
    raw = RawWriter(str(tmp_path))
    path = raw.partition_path(ingest_id, date(2024, 1, 2), date(2024, 1, 2), part)
    data = raw.to_jsonl([record], ingest_id, "https://api.fda.gov/drug/event.json")
    return raw.write(path, data)


def test_run_appends_the_payload_and_keeps_the_api_reject(tmp_path):
    payload = {"safetyreportid": "123", "patient": {"reaction": [{"reactionmeddrapt": "Nausea"}]}}
    audit = _audit()
    audit.records_expected = 2
    audit.records_received = 1
    audit.records_rejected = 1
    audit.output_files.append(_written_part(tmp_path, "run-1", payload))
    writer = MemoryWriter()

    append_run(audit, writer)

    stored = writer.tables[RAW_TABLE][0]
    assert stored["payload"] == payload
    audit_stored = writer.tables[AUDIT_TABLE]
    assert len(audit_stored) == 1
    assert audit_stored[0]["records_received"] == 1
    assert audit_stored[0]["records_rejected"] == 1
    assert audit_stored[0]["reconciled"] is True


def test_a_bad_file_line_moves_from_received_to_rejected(tmp_path):
    written = _written_part(tmp_path, "run-1", {"safetyreportid": "123"})
    with Path(written["path"]).open("a", encoding="utf-8") as handle:
        handle.write("not-json\n")
    audit = _audit()
    audit.records_expected = 3
    audit.records_received = 2
    audit.records_rejected = 1
    audit.output_files.append(written)
    writer = MemoryWriter()

    append_run(audit, writer)

    assert len(writer.tables[RAW_TABLE]) == 1
    stored = writer.tables[AUDIT_TABLE][0]
    assert stored["records_received"] == 1
    assert stored["records_rejected"] == 2
    assert stored["reconciled"] is True


def test_a_run_with_no_file_still_writes_one_audit_row():
    audit = _audit()
    audit.records_expected = 1
    audit.records_received = 0
    audit.records_rejected = 1
    writer = MemoryWriter()

    append_run(audit, writer)

    assert RAW_TABLE not in writer.tables
    stored = writer.tables[AUDIT_TABLE][0]
    assert stored["records_received"] == 0
    assert stored["records_rejected"] == 1


def test_two_part_files_append_once_and_keep_both_payloads(tmp_path):
    first = {"safetyreportid": "123"}
    second = {"safetyreportid": "456"}
    audit = _audit()
    audit.records_expected = 2
    audit.records_received = 2
    audit.output_files.append(_written_part(tmp_path, "run-1", first, part=0))
    audit.output_files.append(_written_part(tmp_path, "run-1", second, part=1))
    writer = MemoryWriter()

    append_run(audit, writer)

    stored = writer.tables[RAW_TABLE]
    assert [row["payload"] for row in stored] == [first, second]
    assert len(writer.tables[AUDIT_TABLE]) == 1


def test_a_gcs_path_is_refused_before_any_append():
    audit = _audit()
    audit.records_received = 1
    audit.output_files.append({"path": "gs://bucket/part-00000.jsonl", "sha256": "abc", "bytes": 1})
    writer = MemoryWriter()

    with pytest.raises(ValueError, match="local JSONL"):
        append_run(audit, writer)

    assert writer.tables == {}
