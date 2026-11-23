import json
from datetime import date
from pathlib import Path

from drug_safe.ingestion.raw_load import load_jsonl, load_path
from drug_safe.ingestion.raw_writer import RawWriter


def _write_part(tmp_path, ingest_id: str, record: dict, part: int = 0) -> str:
    writer = RawWriter(str(tmp_path))
    path = writer.partition_path(ingest_id, date(2024, 1, 2), date(2024, 1, 2), part)
    data = writer.to_jsonl([record], ingest_id, "https://api.fda.gov/drug/event.json")
    writer.write(path, data)
    return path


def test_payload_matches_written_record(tmp_path):
    record = {"safetyreportid": "123", "patient": {"reaction": [{"reactionmeddrapt": "Nausea"}]}}
    path = _write_part(tmp_path, "run-1", record)

    loaded = load_path(path)

    assert loaded.records_rejected == 0
    assert loaded.rows[0]["payload"] == record
    assert loaded.rows[0]["_ingest_id"] == "run-1"
    assert loaded.rows[0]["_source_url"] == "https://api.fda.gov/drug/event.json"
    assert loaded.rows[0]["_fetched_at"]


def test_rows_from_a_second_file_keep_the_first_run(tmp_path):
    first = {"safetyreportid": "123"}
    second = {"safetyreportid": "456"}
    first_path = _write_part(tmp_path, "run-1", first, part=0)
    second_path = _write_part(tmp_path, "run-2", second, part=1)

    combined = load_path(first_path).rows + load_path(second_path).rows

    assert [row["_ingest_id"] for row in combined] == ["run-1", "run-2"]
    assert combined[0]["payload"] == first
    assert combined[1]["payload"] == second


def test_invalid_line_is_counted_and_excluded(tmp_path):
    record = {"safetyreportid": "123"}
    path = _write_part(tmp_path, "run-1", record)
    original = Path(path).read_text(encoding="utf-8")
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write("not-json\n")

    loaded = load_path(path)

    assert loaded.records_received == 1
    assert loaded.records_rejected == 1
    assert loaded.rejected[0].reason == "invalid json"
    assert loaded.rejected[0].line_number == 2
    assert loaded.rows[0]["payload"] == record
    assert json.loads(original)["payload"] == record


def test_line_missing_ingest_id_is_rejected():
    loaded = load_jsonl('{"_fetched_at": "2024-01-02T00:00:00.000Z", "payload": {}}\n')

    assert loaded.rows == []
    assert loaded.records_rejected == 1
    assert loaded.rejected[0].reason == "missing _ingest_id"
