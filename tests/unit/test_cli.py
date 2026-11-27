from datetime import date

from drug_safe.config import Settings
from drug_safe.ingestion.bq_append import AUDIT_TABLE, RAW_TABLE
from drug_safe.ingestion.cli import run
from drug_safe.ingestion.openfda_client import Page


class _MemoryWriter:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict]] = {}

    def append(self, table: str, rows: list[dict]) -> None:
        self.tables.setdefault(table, []).extend(rows)


class _FakeClient:
    def iter_pages(self, start: date, end: date, max_records: int | None = None):
        yield Page(
            url="https://api.fda.gov/drug/event.json?search=test",
            total=2,
            valid=[{"safetyreportid": "123", "serious": "1"}],
            rejected=[{"receivedate": "20240102"}],
        )


def test_run_appends_written_rows_when_a_writer_is_passed(tmp_path):
    settings = Settings(
        env="dev",
        gcp_project=None,
        raw_root=str(tmp_path),
        openfda_api_key=None,
        actor="test",
    )
    writer = _MemoryWriter()

    audit = run(date(2024, 1, 2), date(2024, 1, 2), None, settings, writer, _FakeClient())

    stored = writer.tables[RAW_TABLE][0]
    assert stored["payload"] == {"safetyreportid": "123", "serious": "1"}
    assert stored["payload"]["safetyreportid"] == "123"
    audit_row = writer.tables[AUDIT_TABLE][0]
    assert len(writer.tables[AUDIT_TABLE]) == 1
    assert audit_row["records_received"] == 1
    assert audit_row["records_rejected"] == 1
    assert audit_row["reconciled"] is True
    assert audit.reconciled is True
    assert audit.status == "SUCCEEDED"
