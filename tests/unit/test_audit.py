import json

from drug_safe.common.audit import AuditLogger, AuditRecord


def make_record(**overrides):
    record = AuditRecord(
        pipeline="test", actor="ci", source="openfda:drug/event", parameters={"start": "2024-01-01"}
    )
    for key, value in overrides.items():
        setattr(record, key, value)
    return record


def test_audit_record_captures_run_metadata(tmp_path):
    record = make_record(records_expected=3, records_received=2, records_rejected=1)
    record.finish("SUCCEEDED")
    path = tmp_path / "audit.jsonl"

    AuditLogger(path).write(record)

    saved = json.loads(path.read_text())
    assert saved["actor"] == "ci"
    assert saved["status"] == "SUCCEEDED"
    assert saved["started_at"] and saved["ended_at"]
    assert saved["reconciled"] is True


def test_unreconciled_counts_are_flagged():
    assert make_record(records_expected=5, records_received=3).reconciled is False


def test_logger_appends_and_never_overwrites(tmp_path):
    path = tmp_path / "audit.jsonl"
    logger = AuditLogger(path)
    logger.write(make_record())
    logger.write(make_record())
    assert len(path.read_text().splitlines()) == 2
