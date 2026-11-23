from drug_safe.common.audit import AuditRecord
from drug_safe.ingestion.bq_append import AUDIT_TABLE, RAW_TABLE, append_load
from drug_safe.ingestion.raw_load import RawLoad, RejectedLine


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
