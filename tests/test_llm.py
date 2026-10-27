import sys
from types import SimpleNamespace

from whytrace.llm import generate


def test_configured_nightshift_is_used_even_with_sample_data(tmp_path, monkeypatch):
    seen = {}

    class FakeClient:
        def __init__(self, api_key, base_url):
            seen["api_key"] = api_key
            seen["base_url"] = base_url
            self.chat = SimpleNamespace(completions=self)

        def create(self, **kwargs):
            seen["request"] = kwargs
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="SELECT 1"))])

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeClient))
    monkeypatch.setenv("SAMPLE_MODE", "true")
    monkeypatch.setenv("METERLESS_RUNTIME_TOKEN", "test-token")
    monkeypatch.setenv("METERLESS_BASE_URL", "https://nightshift.test/v1")
    monkeypatch.setenv("FAST_MODEL", "fast-test")
    monkeypatch.setenv("WHYTRACE_LOG_DIR", str(tmp_path))

    text, model = generate("fast", "Write a query")

    assert (text, model) == ("SELECT 1", "fast-test")
    assert seen["api_key"] == "test-token"
    assert seen["base_url"] == "https://nightshift.test/v1"
    assert seen["request"]["model"] == "fast-test"
    assert '"ok": true' in (tmp_path / "requests.jsonl").read_text(encoding="utf-8")
