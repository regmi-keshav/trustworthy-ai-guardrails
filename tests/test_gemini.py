import pytest

from guardrails.llm import GeminiLLM, load_env


def test_load_env_reads_key_without_overriding(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comment\nFOO_KEY=from-file\nBAR_KEY = 'quoted'\n")
    monkeypatch.setenv("FOO_KEY", "from-shell")
    monkeypatch.delenv("BAR_KEY", raising=False)
    load_env(env)
    import os
    assert os.environ["FOO_KEY"] == "from-shell" and os.environ["BAR_KEY"] == "quoted"


def test_gemini_without_key_fails_clearly(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        GeminiLLM(env_file=tmp_path / "missing.env")
