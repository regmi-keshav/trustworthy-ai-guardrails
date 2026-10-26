"""Prompt-injection detection."""
import re

from guardrails.result import GuardResult

_INJECTION = [
    (1.0, r"(ignore|disregard|forget)\s+(all\s+|any\s+|the\s+|your\s+)*(previous|prior|above|earlier)\s+(instructions?|rules?|prompts?)"),
    (1.0, r"(reveal|show|print|repeat|leak)\s+.{0,20}(system prompt|hidden instructions|your instructions)"),
    (0.8, r"bypass\s+.{0,20}(rules?|restrictions?|filters?|guardrails?|safety)"),
    (0.6, r"you are now\b"),
    (0.6, r"\b(pretend (to be|you are)|developer mode|jailbreak|do anything now|DAN)\b"),
    (0.5, r"disregard\s+.{0,20}(rules?|instructions?)"),
]
_THRESHOLD = 0.8


def check_injection(text: str) -> GuardResult:
    # shortcut: English phrase patterns only, misses paraphrase/other languages/encodings; upgrade to a classifier
    score = sum(w for w, p in _INJECTION if re.search(p, text, re.I))
    flagged = score >= _THRESHOLD
    return GuardResult("injection", flagged, "block" if flagged else "allow", f"score={score:.1f}")
