import json
import pytest
from voicetest import clients


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body if body is not None else {}
        self.text = json.dumps(self._body, ensure_ascii=False)
        self.content = b""

    def json(self):
        return self._body


@pytest.fixture
def api(monkeypatch, tmp_path):
    """Fake network + temporary cache folder + fake key. Returns the list of calls made."""
    calls = []

    def fake_post(url, **kwargs):
        data = kwargs.get("data") or {}
        calls.append({"url": url, "data": data})
        return FakeResponse(200, {"success": True, "transcript": "ok",
                                  "model": data.get("model")})

    monkeypatch.setattr(clients.requests, "post", fake_post)
    monkeypatch.setattr(clients, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("GNANI_API_KEY", "test-key")
    return calls


@pytest.fixture
def wav(tmp_path):
    p = tmp_path / "a.wav"
    p.write_bytes(b"fake-audio-bytes")
    return p


def test_second_identical_call_is_served_from_cache(api, wav):
    first = clients.transcribe(wav)
    second = clients.transcribe(wav)
    assert len(api) == 1                 # only one real request
    assert first == second


def test_model_and_format_are_always_sent_explicitly(api, wav):
    clients.transcribe(wav, model="prisma-v3.0", fmt="transcribe")
    assert api[0]["data"]["model"] == "prisma-v3.0"
    assert api[0]["data"]["format"] == "transcribe"


def test_changing_model_is_a_cache_miss(api, wav):
    clients.transcribe(wav, model="prisma-v2.5")
    clients.transcribe(wav, model="prisma-v3.0")
    assert len(api) == 2


def test_changing_format_is_a_cache_miss(api, wav):
    clients.transcribe(wav, model="prisma-v3.0", fmt="transcribe")
    clients.transcribe(wav, model="prisma-v3.0", fmt="verbatim")
    assert len(api) == 2


def test_keyterms_are_sent_as_json_for_v3(api, wav):
    clients.transcribe(wav, model="prisma-v3.0", keyterms=["खाता", "HDFC Bank"])
    assert api[0]["data"]["keyterms"] == '["खाता", "HDFC Bank"]'


def test_keyterms_with_v2_5_is_rejected_before_any_request(api, wav):
    with pytest.raises(ValueError):
        clients.transcribe(wav, model="prisma-v2.5", keyterms=["खाता"])
    assert api == []


def test_http_error_raises_with_gnani_message_and_is_not_cached(monkeypatch, api, wav, tmp_path):
    def bad_post(url, **kwargs):
        return FakeResponse(400, {"success": False,
                                  "error": {"type": "INVALID_FORMAT", "message": "bad"}})
    monkeypatch.setattr(clients.requests, "post", bad_post)
    with pytest.raises(RuntimeError, match="INVALID_FORMAT"):
        clients.transcribe(wav)
    assert list((tmp_path / "stt").glob("*")) == []      # nothing saved

def test_http_error_keeps_status_code_and_shortens_html_pages(monkeypatch, api, wav):
    html = "<!DOCTYPE html><html><head><title>vachana.ai | 504: Gateway time-out</title></head></html>"

    def gateway_post(url, **kwargs):
        r = FakeResponse(504)
        r.text = html
        return r

    monkeypatch.setattr(clients.requests, "post", gateway_post)
    with pytest.raises(clients.ApiError) as info:
        clients.transcribe(wav)
    assert info.value.status == 504
    assert "504: Gateway time-out" in str(info.value)
    assert "<html" not in str(info.value)