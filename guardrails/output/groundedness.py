"""Groundedness check against reference text."""
import re

from guardrails.result import GuardResult

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
