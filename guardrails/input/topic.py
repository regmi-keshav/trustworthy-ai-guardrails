"""Sensitive-topic classification."""
import re

from guardrails.result import GuardResult

# Priority order: the first matching category wins.
_TOPICS = [
    ("self_harm", "safe_response", r"\b(suicide|suicidal|kill myself|end my life|self[- ]harm|hurt myself|don'?t want to live)\b"),
    ("fraud", "escalate", r"\b(fraud|scam|unauthori[sz]ed|hacked|compromised|identity theft|phishing)\b"),
    ("legal_investment", "disclaimer", r"\b(stocks?|invest(ing|ment)?|crypto|legal advice|lawsuit|sue|tax advice)\b"),
]


def check_topic(text: str) -> GuardResult:
    # shortcut: keyword match, false-positives on benign mentions ("fraud alert settings") and misses implicit phrasing
    for category, action, pattern in _TOPICS:
        if re.search(pattern, text, re.I):
            return GuardResult("topic", True, action, category)
    return GuardResult("topic", False, "allow", "")
