"""Output guardrails: schema validation, groundedness, sensitive-information scan."""
import json
import re

from src.input_guards import redact_pii
from src.kb import KB
from src.result import GuardResult

# --- Schema ------------------------------------------------------------------

def check_schema(raw: str) -> GuardResult:
    """Expect {"answer": non-empty str, "sources": [known KB ids], "confidence": number in [0,1]}."""
    def bad(why):
        return GuardResult("schema", True, "regenerate", why)

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return bad("not valid JSON")
    if not isinstance(data, dict):
        return bad("not a JSON object")
    if not isinstance(data.get("answer"), str) or not data["answer"].strip():
        return bad("answer must be a non-empty string")
    src = data.get("sources")
    if not isinstance(src, list) or not all(isinstance(s, str) and s in KB for s in src):
        return bad("sources must be a list of known KB ids")
    conf = data.get("confidence")
    if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
        return bad("confidence must be a number in [0, 1]")
    return GuardResult("schema", False, "allow", data=data)


# --- Groundedness ------------------------------------------------------------

_STOP = {"the", "and", "are", "for", "you", "your", "with", "this", "that", "from", "can", "will", "has", "have", "per"}
_ABSTAIN = re.compile(r"don'?t have (any )?information|contact (customer )?support", re.I)
_MIN_OVERLAP = 0.6


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 2 and w not in _STOP}


def _nums(text: str) -> set[str]:
    return {n.rstrip(".,") for n in re.findall(r"\d+(?:[.,]\d+)*", text)}


def check_groundedness(answer: str, reference: list[str]) -> GuardResult:
    """Every sentence needs >=60% of its content words in the reference, and all its numbers must appear there."""
    # shortcut: lexical overlap only, misses negation flips and paraphrased hallucinations; upgrade to an NLI model
    ref = " ".join(reference)
    ref_words, ref_nums = _words(ref), _nums(ref)
    unsupported = []
    for sent in re.split(r"(?<=[.!?])\s+", answer.strip()):
        if not sent or _ABSTAIN.search(sent):
            continue
        words = _words(sent)
        overlap = len(words & ref_words) / len(words) if words else 1.0
        if overlap < _MIN_OVERLAP or not _nums(sent) <= ref_nums:
            unsupported.append(sent)
    return GuardResult("groundedness", bool(unsupported), "regenerate" if unsupported else "allow", " | ".join(unsupported))


# --- Sensitive information ---------------------------------------------------

_INTERNAL = re.compile(r"https?://\S*\.internal\S*|system prompt|internal use only|confidential", re.I)


def check_sensitive_info(answer: str) -> GuardResult:
    # shortcut: regex PII + small denylist; upgrade to NER and a managed secret/PII scanner
    if _INTERNAL.search(answer):
        return GuardResult("sensitive_info", True, "block", "internal data")
    clean, found = redact_pii(answer)
    return GuardResult("sensitive_info", bool(found), "redact" if found else "allow", ",".join(found), clean)
