"""Input guardrails: PII redaction, prompt-injection blocking, sensitive-topic routing."""
import re

from src.result import GuardResult

# --- PII ---------------------------------------------------------------------

def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def _card(m: re.Match) -> str:
    digits = re.sub(r"\D", "", m.group())
    return "[CARD]" if 13 <= len(digits) <= 16 and _luhn(digits) else m.group()


# Order matters: cards (Luhn-checked) and SSNs before phones, so digits aren't mislabelled.
_PII = [
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,16}\b"), _card),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[EMAIL]"),
    ("PHONE", re.compile(r"(?<!\w)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE]"),
]


def redact_pii(text: str) -> tuple[str, list[str]]:
    """Return (redacted text, PII types found). Shared with the output guard."""
    found = []
    for kind, pattern, repl in _PII:
        new = pattern.sub(repl, text)
        if new != text:
            found.append(kind)
            text = new
    return text, found


def check_pii(text: str) -> GuardResult:
    # shortcut: regex only (no names/addresses, no obfuscated forms), upgrade to an NER model like Presidio
    clean, found = redact_pii(text)
    return GuardResult("pii", bool(found), "redact" if found else "allow", ",".join(found), clean)


# --- Prompt injection --------------------------------------------------------

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


# --- Sensitive topics --------------------------------------------------------

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
