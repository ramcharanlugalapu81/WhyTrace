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

    assert (text, model) == ("SELECT 1", "Meterless · fast-test")
    assert seen["api_key"] == "test-token"
    assert seen["base_url"] == "https://nightshift.test/v1"
    assert seen["request"]["model"] == "fast-test"
    assert '"ok": true' in (tmp_path / "requests.jsonl").read_text(encoding="utf-8")


def test_nemotron_skeptic_uses_nvidia_endpoint(tmp_path, monkeypatch):
    seen = {}

    class FakeClient:
        def __init__(self, api_key, base_url):
            seen["api_key"], seen["base_url"] = api_key, base_url
            self.chat = SimpleNamespace(completions=self)

        def create(self, **kwargs):
            seen["request"] = kwargs
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"status":"reviewed"}'))])

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeClient))
    monkeypatch.delenv("METERLESS_RUNTIME_TOKEN", raising=False)
    monkeypatch.setenv("NVIDIA_API_KEY", "nvidia-test-token")
    monkeypatch.setenv("WHYTRACE_LOG_DIR", str(tmp_path))

    text, model = generate("skeptic", "Review this evidence")

    assert text == '{"status":"reviewed"}'
    assert model == "Nvidia · nvidia/nemotron-3.5-bolt-e4b"
    assert seen["api_key"] == "nvidia-test-token"
    assert seen["base_url"] == "https://integrate.api.nvidia.com/v1"
