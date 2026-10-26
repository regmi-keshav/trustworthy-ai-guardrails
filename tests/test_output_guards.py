import json

import pytest

from guardrails.kb import KB
from guardrails.output import check_groundedness, check_schema, check_sensitive_info

REF = [KB["overdraft"]]


def raw(**kw):
    d = {"answer": "ok", "sources": ["overdraft"], "confidence": 0.8}
    d.update(kw)
    return json.dumps(d)


def test_schema_valid():
    r = check_schema(raw())
    assert not r.flagged and r.data["answer"] == "ok"


@pytest.mark.parametrize("bad", [
    "Sure! here you go",
    json.dumps(["not", "an", "object"]),
    json.dumps({"answer": "x", "sources": []}),            # missing confidence
    raw(confidence="high"),                                 # wrong type
    raw(confidence=True),                                   # bool is not a number
    raw(confidence=1.5),                                    # out of range
    raw(answer=""),                                         # empty answer
    raw(sources=["nope"]),                                  # unknown KB id
    raw(sources="overdraft"),                               # not a list
])
def test_schema_invalid_triggers_regenerate(bad):
    r = check_schema(bad)
    assert r.flagged and r.action == "regenerate"


def test_grounded_answer_passes():
    assert not check_groundedness(KB["overdraft"], REF).flagged


def test_grounded_paraphrase_passes():
    assert not check_groundedness("The overdraft fee is $35 per transaction.", REF).flagged


@pytest.mark.parametrize("answer", [
    KB["overdraft"] + " All fees are waived for the first 12 months.",   # invented claim
    "The overdraft fee is $50 per transaction, limited to 3 fees per day.",  # wrong number
    "Premium customers get free crypto trading and a private jet lounge.",   # unrelated
])
def test_ungrounded_answer_flagged(answer):
    r = check_groundedness(answer, REF)
    assert r.flagged and r.action == "regenerate"


def test_abstention_is_allowed():
    assert not check_groundedness("I don't have information on that.", []).flagged


def test_sensitive_pii_redacted():
    r = check_sensitive_info("Email john.doe@example.com or call 555-123-4567")
    assert r.action == "redact" and "@" not in r.text and "[PHONE]" in r.text


def test_sensitive_internal_data_blocked():
    r = check_sensitive_info("See https://intranet.bank.internal/runbook for details")
    assert r.action == "block"


def test_sensitive_clean_text_allowed():
    assert not check_sensitive_info(KB["wire_fee"]).flagged
