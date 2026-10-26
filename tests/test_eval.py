from eval.run_eval import evaluate, load_cases, metrics

REQUIRED = {"normal", "malicious", "pii", "sensitive", "invalid_output", "unsupported_claim"}


def test_benchmark_has_enough_cases_and_categories():
    cases = load_cases()
    assert len(cases) >= 20
    assert REQUIRED <= {c["category"] for c in cases}


def test_metrics_counts():
    rows = [
        {"should_flag": True, "flagged": True},
        {"should_flag": True, "flagged": False},
        {"should_flag": False, "flagged": True},
        {"should_flag": False, "flagged": False},
    ]
    m = metrics(rows)
    assert (m["tp"], m["fn"], m["fp"], m["tn"]) == (1, 1, 1, 1)
    assert m["precision"] == 0.5 and m["recall"] == 0.5


def test_every_case_produces_a_result():
    results = evaluate(load_cases())
    assert all({"actual_status", "flagged", "passed"} <= r.keys() for r in results)
