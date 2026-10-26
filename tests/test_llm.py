import json

from guardrails.kb import KB, retrieve
from guardrails.llm import MockLLM


def test_retrieve_finds_relevant_entry():
    assert retrieve("What is the overdraft fee?")[0][0] == "overdraft"


def test_retrieve_returns_nothing_for_unrelated_query():
    assert retrieve("zzz qqq") == []


def test_mock_good_answer_is_valid_json_citing_kb():
    passages = retrieve("What is the overdraft fee?")
    out = json.loads(MockLLM("good").generate("What is the overdraft fee?", passages))
    assert out["answer"] == KB["overdraft"]
    assert out["sources"] == ["overdraft"]
    assert 0 <= out["confidence"] <= 1


def test_mock_failure_modes():
    p = retrieve("What is the overdraft fee?")
    assert "waived" in json.loads(MockLLM("hallucinate").generate("q", p))["answer"]
    assert "@" in json.loads(MockLLM("leak").generate("q", p))["answer"]
    assert isinstance(json.loads(MockLLM("bad_type").generate("q", p))["confidence"], str)
    try:
        json.loads(MockLLM("malformed").generate("q", p))
        assert False, "malformed mode must not return valid JSON"
    except json.JSONDecodeError:
        pass


def test_mock_sequence_sticks_on_last_mode():
    llm = MockLLM("malformed", "good")
    p = retrieve("What is the overdraft fee?")
    outs = [llm.generate("q", p) for _ in range(3)]
    assert outs[1] == outs[2] and outs[0] != outs[1]
