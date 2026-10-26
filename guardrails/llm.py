"""LLM clients. Both return the model's raw text, expected to be a JSON object
{"answer": str, "sources": [kb_id], "confidence": float}."""
import json


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
