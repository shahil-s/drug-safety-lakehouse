from datetime import date

import pytest
import requests

from drug_safe.ingestion.openfda_client import (
    OpenFDAClient,
    WindowTooLargeError,
)


class FakeResponse:
    def __init__(self, status_code=200, body=None, url="https://api.fda.gov/drug/event.json?x"):
        self.status_code = status_code
        self._body = body or {}
        self.url = url

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """Returns queued responses in order and records the params of each call."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(params)
        return self.responses.pop(0)


def body(total, ids):
    return {
        "meta": {"results": {"total": total}},
        "results": [{"safetyreportid": i} if i else {"receivedate": "20240101"} for i in ids],
    }


def make_client(responses, **kwargs):
    session = FakeSession(responses)
    client = OpenFDAClient(session=session, backoff_seconds=0, **kwargs)
    return client, session


def test_build_search_formats_window():
    assert (
        OpenFDAClient.build_search(date(2024, 1, 1), date(2024, 1, 7))
        == "receivedate:[20240101 TO 20240107]"
    )


def test_build_search_rejects_reversed_window():
    with pytest.raises(ValueError):
        OpenFDAClient.build_search(date(2024, 1, 7), date(2024, 1, 1))


def test_pages_until_total_reached():
    client, session = make_client(
        [FakeResponse(body=body(3, ["a", "b"])), FakeResponse(body=body(3, ["c"]))],
        page_size=2,
    )
    pages = list(client.iter_pages(date(2024, 1, 1), date(2024, 1, 1)))

    assert [len(p.valid) for p in pages] == [2, 1]
    assert [c["skip"] for c in session.calls] == [0, 2]


def test_records_without_report_id_are_rejected():
    client, _ = make_client([FakeResponse(body=body(3, ["a", None, "c"]))])
    (page,) = client.iter_pages(date(2024, 1, 1), date(2024, 1, 1))

    assert len(page.valid) == 2
    assert len(page.rejected) == 1


def test_404_means_no_results():
    client, _ = make_client([FakeResponse(status_code=404)])
    assert list(client.iter_pages(date(2024, 1, 1), date(2024, 1, 1))) == []


def test_retries_on_rate_limit_then_succeeds():
    client, session = make_client(
        [FakeResponse(status_code=429), FakeResponse(body=body(1, ["a"]))]
    )
    pages = list(client.iter_pages(date(2024, 1, 1), date(2024, 1, 1)))

    assert len(pages) == 1
    assert len(session.calls) == 2


def test_retries_on_connection_error():
    class FlakySession(FakeSession):
        def get(self, url, params=None, timeout=None):
            self.calls.append(params)
            if len(self.calls) == 1:
                raise requests.ConnectionError("network blip")
            return self.responses.pop(0)

    session = FlakySession([FakeResponse(body=body(1, ["a"]))])
    client = OpenFDAClient(session=session, backoff_seconds=0)
    pages = list(client.iter_pages(date(2024, 1, 1), date(2024, 1, 1)))

    assert len(pages) == 1
    assert len(session.calls) == 2


def test_gives_up_after_max_retries():
    client, _ = make_client([FakeResponse(status_code=503)] * 3, max_retries=2)
    with pytest.raises(RuntimeError):
        list(client.iter_pages(date(2024, 1, 1), date(2024, 1, 1)))


def test_window_too_large_fails_loudly():
    client, _ = make_client([FakeResponse(body=body(100_000, ["a"]))])
    with pytest.raises(WindowTooLargeError):
        list(client.iter_pages(date(2024, 1, 1), date(2024, 12, 31)))


def test_max_records_caps_the_pull():
    client, session = make_client([FakeResponse(body=body(10, ["a", "b"]))], page_size=5)
    pages = list(client.iter_pages(date(2024, 1, 1), date(2024, 1, 1), max_records=2))

    assert sum(len(p.valid) for p in pages) == 2
    assert session.calls[0]["limit"] == 2


def test_api_key_is_sent_when_configured():
    client, session = make_client([FakeResponse(body=body(1, ["a"]))], api_key="secret")
    list(client.iter_pages(date(2024, 1, 1), date(2024, 1, 1)))
    assert session.calls[0]["api_key"] == "secret"
