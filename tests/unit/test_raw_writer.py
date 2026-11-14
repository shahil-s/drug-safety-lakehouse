import hashlib
import json
from datetime import date

import pytest

from drug_safe.ingestion.raw_writer import RawWriter


def test_writes_payload_unchanged_with_checksum(tmp_path):
    writer = RawWriter(str(tmp_path))
    record = {"safetyreportid": "123", "patient": {"reaction": [{"reactionmeddrapt": "Nausea"}]}}
    path = writer.partition_path("run-1", date(2024, 1, 1), date(2024, 1, 2), 0)
    data = writer.to_jsonl([record], "run-1", "https://api.fda.gov/x")

    result = writer.write(path, data)

    written = (tmp_path / path.removeprefix(str(tmp_path) + "/")).read_bytes()
    envelope = json.loads(written.decode())
    assert envelope["payload"] == record
    assert envelope["_ingest_id"] == "run-1"
    assert envelope["_source_url"] == "https://api.fda.gov/x"
    assert result["sha256"] == hashlib.sha256(written).hexdigest()


def test_partition_path_layout(tmp_path):
    writer = RawWriter(str(tmp_path))
    path = writer.partition_path("abc", date(2024, 1, 1), date(2024, 1, 7), 3)
    assert path.endswith(
        "openfda/drug_event/received_date=20240101_20240107/ingest_id=abc/part-00003.jsonl"
    )


def test_never_overwrites_existing_file(tmp_path):
    writer = RawWriter(str(tmp_path))
    path = writer.partition_path("abc", date(2024, 1, 1), date(2024, 1, 1), 0)
    writer.write(path, b"first\n")
    with pytest.raises(FileExistsError):
        writer.write(path, b"second\n")
