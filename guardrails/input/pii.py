"""PII detection and redaction (input guard; also reused by the output scan)."""
import re

from guardrails.result import GuardResult

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
