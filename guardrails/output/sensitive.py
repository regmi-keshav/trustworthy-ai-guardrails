"""Sensitive-information scan of generated answers."""
import re

from guardrails.input.pii import redact_pii
from guardrails.result import GuardResult

_INTERNAL = re.compile(r"https?://\S*\.internal\S*|system prompt|internal use only|confidential", re.I)


PUBLIC_CONTACTS = ["1-800-555-0100"]  # the bank's own number is not a leak


def check_sensitive_info(answer: str) -> GuardResult:
    # shortcut: regex PII + small denylist; upgrade to NER and a managed secret/PII scanner
    if _INTERNAL.search(answer):
        return GuardResult("sensitive_info", True, "block", "internal data")
    for i, c in enumerate(PUBLIC_CONTACTS):
        answer = answer.replace(c, f"\x00{i}\x00")
    clean, found = redact_pii(answer)
    for i, c in enumerate(PUBLIC_CONTACTS):
        clean = clean.replace(f"\x00{i}\x00", c)
    return GuardResult("sensitive_info", bool(found), "redact" if found else "allow", ",".join(found), clean)
