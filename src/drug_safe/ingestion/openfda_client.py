"""Client for the openFDA drug adverse event endpoint.

Docs: https://open.fda.gov/apis/drug/event/

Design notes (good interview talking points):
- Pulls by `receivedate` window so loads are idempotent and easy to backfill.
- Retries 429/5xx with exponential backoff; openFDA returns 404 when a query has no matches.
- openFDA caps `skip` paging, so windows that are too large fail loudly
  instead of silently truncating.
- Records without a `safetyreportid` are rejected and counted, never silently
  dropped (ALCOA+: Complete).
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date

import requests

BASE_URL = "https://api.fda.gov/drug/event.json"
MAX_LIMIT = 1000  # openFDA max records per request
MAX_SKIP = 25000  # openFDA max value for the skip parameter
RETRY_STATUSES = {429, 500, 502, 503, 504}


class WindowTooLargeError(ValueError):
    """The date window returns more records than skip-based paging can reach."""


@dataclass
class Page:
    url: str
    total: int
    valid: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)


class OpenFDAClient:
    def __init__(
        self,
        api_key: str | None = None,
        session: requests.Session | None = None,
        page_size: int = MAX_LIMIT,
        max_retries: int = 5,
        backoff_seconds: float = 1.0,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not 1 <= page_size <= MAX_LIMIT:
            raise ValueError(f"page_size must be between 1 and {MAX_LIMIT}")
        self.api_key = api_key
        self.session = session or requests.Session()
        self.page_size = page_size
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def build_search(start: date, end: date) -> str:
        if end < start:
            raise ValueError("end date must be on or after start date")
        return f"receivedate:[{start:%Y%m%d} TO {end:%Y%m%d}]"

    def _get(self, params: dict) -> requests.Response:
        for attempt in range(self.max_retries + 1):
            is_last = attempt == self.max_retries
            try:
                response = self.session.get(BASE_URL, params=params, timeout=self.timeout_seconds)
            except (requests.ConnectionError, requests.Timeout):
                if is_last:
                    raise
            else:
                if response.status_code not in RETRY_STATUSES:
                    return response
                if is_last:
                    response.raise_for_status()
                    return response
            time.sleep(self.backoff_seconds * 2**attempt)
        raise AssertionError("unreachable")

    @staticmethod
    def split_valid(records: list[dict]) -> tuple[list[dict], list[dict]]:
        valid, rejected = [], []
        for record in records:
            (valid if record.get("safetyreportid") else rejected).append(record)
        return valid, rejected

    def iter_pages(self, start: date, end: date, max_records: int | None = None) -> Iterator[Page]:
        """Yield pages of adverse event reports received between start and end (inclusive)."""
        search = self.build_search(start, end)
        skip = 0
        fetched = 0

        while True:
            limit = self.page_size
            if max_records is not None:
                limit = min(limit, max_records - fetched)
                if limit <= 0:
                    return

            params = {"search": search, "limit": limit, "skip": skip}
            if self.api_key:
                params["api_key"] = self.api_key

            response = self._get(params)
            if response.status_code == 404:  # openFDA: no matching records
                return
            response.raise_for_status()

            body = response.json()
            total = body["meta"]["results"]["total"]
            if skip == 0 and max_records is None and total > MAX_SKIP + self.page_size:
                raise WindowTooLargeError(
                    f"{search} matches {total} records; use a smaller date window "
                    f"(skip paging reaches at most {MAX_SKIP + self.page_size})."
                )

            results = body.get("results", [])
            valid, rejected = self.split_valid(results)
            yield Page(url=response.url, total=total, valid=valid, rejected=rejected)

            fetched += len(results)
            skip += len(results)
            if not results or skip >= total:
                return
