"""Writes source records to the immutable raw zone.

Each line is an envelope: ingestion metadata plus the source record exactly as received.
Files are never overwritten (ALCOA+: Original). A SHA-256 checksum of the written bytes is returned
so it can be stored in the audit record and re-verified later (ALCOA+: Accurate).

Layout:
  {root}/openfda/drug_event/received_date={start}_{end}/ingest_id={uuid}/part-00000.jsonl
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from drug_safe.common.audit import utc_now


class RawWriter:
    def __init__(self, root: str) -> None:
        self.root = root.rstrip("/")
        self.is_gcs = self.root.startswith("gs://")

    def partition_path(self, ingest_id: str, start: date, end: date, part: int) -> str:
        return (
            f"{self.root}/openfda/drug_event/"
            f"received_date={start:%Y%m%d}_{end:%Y%m%d}/"
            f"ingest_id={ingest_id}/part-{part:05d}.jsonl"
        )

    @staticmethod
    def to_jsonl(records: list[dict], ingest_id: str, source_url: str) -> bytes:
        fetched_at = utc_now()
        lines = [
            json.dumps(
                {
                    "_ingest_id": ingest_id,
                    "_source_url": source_url,
                    "_fetched_at": fetched_at,
                    "payload": record,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            for record in records
        ]
        return ("\n".join(lines) + "\n").encode("utf-8")

    def write(self, path: str, data: bytes) -> dict:
        checksum = hashlib.sha256(data).hexdigest()
        if self.is_gcs:
            self._write_gcs(path, data)
        else:
            local = Path(path)
            local.parent.mkdir(parents=True, exist_ok=True)
            with local.open("xb") as f:  # "x": fail if the file already exists
                f.write(data)
        return {"path": path, "sha256": checksum, "bytes": len(data)}

    @staticmethod
    def _write_gcs(path: str, data: bytes) -> None:
        from google.cloud import storage  # imported lazily so local dev needs no GCP libs

        bucket_name, blob_name = path.removeprefix("gs://").split("/", 1)
        blob = storage.Client().bucket(bucket_name).blob(blob_name)
        # if_generation_match=0: only succeed if the object does not exist yet.
        blob.upload_from_string(data, content_type="application/x-ndjson", if_generation_match=0)
