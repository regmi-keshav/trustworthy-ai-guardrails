"""LLM clients. Both return the model's raw text, expected to be a JSON object
{"answer": str, "sources": [kb_id], "confidence": float}."""
import json
import os
from pathlib import Path


class MockLLM:
    """Deterministic generator for tests. Takes modes, one per call; the last repeats.

    Modes: good | hallucinate | leak | bad_type | malformed
    """

    def __init__(self, *modes: str):
        self.modes = modes or ("good",)
        self.calls = 0

    def generate(self, question: str, passages: list[tuple[str, str]]) -> str:
        mode = self.modes[min(self.calls, len(self.modes) - 1)]
        self.calls += 1
        ids = [i for i, _ in passages]
        answer = passages[0][1] if passages else "I don't have information on that."
        out = {"answer": answer, "sources": ids[:1], "confidence": 0.9}
        if mode == "hallucinate":
            out["answer"] += " All fees are waived for the first 12 months."
        elif mode == "leak":
            out["answer"] += " Contact john.doe@example.com or 555-123-4567; see https://intranet.bank.internal/runbook."
        elif mode == "bad_type":
            out["confidence"] = "high"
        elif mode == "malformed":
            return "Sure! Here is the answer: " + answer
        return json.dumps(out)


class ScriptedLLM:
    """Returns the given raw outputs in order; the last repeats. Used for exact output-guard test cases."""

    def __init__(self, *outputs: str):
        self.outputs = outputs
        self.calls = 0

    def generate(self, question: str, passages: list[tuple[str, str]]) -> str:
        out = self.outputs[min(self.calls, len(self.outputs) - 1)]
        self.calls += 1
        return out


ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

SYSTEM_PROMPT = """You are a bank customer-support assistant.
Answer ONLY from the reference passages provided. Do not add facts, numbers or advice that are not in them.
Reply with a single JSON object and nothing else:
{"answer": "<short answer>", "sources": ["<id of each passage you used>"], "confidence": <number 0-1>}
If the passages do not answer the question, reply
{"answer": "I don't have information on that.", "sources": [], "confidence": 0}"""


def load_env(path: Path = ENV_FILE) -> None:
    """Minimal .env reader: KEY=VALUE lines; never overrides variables already set in the shell."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


class GeminiLLM:
    """Real model for demos. Needs `pip install google-genai` and GEMINI_API_KEY (shell or .env)."""

    def __init__(self, model: str | None = None, env_file: Path = ENV_FILE):
        load_env(env_file)
        key = os.environ.get("GEMINI_API_KEY", "")
        if not key or key.startswith(("your-", "paste-")):
            raise RuntimeError("GEMINI_API_KEY is not set; put it in .env (see .env.example)")
        from google import genai  # imported lazily so tests and the mock don't need the SDK

        self.client = genai.Client(api_key=key)
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

    def generate(self, question: str, passages: list[tuple[str, str]]) -> str:
        from google.genai import types

        context = "\n".join(f"[{i}] {t}" for i, t in passages) or "(no passages found)"
        resp = self.client.models.generate_content(
            model=self.model,
            contents=f"Reference passages:\n{context}\n\nCustomer question: {question}",
            # JSON mode only, no response schema: the schema guard should still have real work to do.
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT, response_mime_type="application/json", temperature=0
            ),
        )
        return resp.text or ""
