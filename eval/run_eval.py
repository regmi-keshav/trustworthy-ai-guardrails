"""Run the golden benchmark through the pipeline and write eval/results.md.

Usage: python -m eval.run_eval
"""
import json
from collections import defaultdict
from pathlib import Path

from guardrails.llm import MockLLM, ScriptedLLM
from guardrails.pipeline import run

HERE = Path(__file__).parent


def load_cases(path: Path = HERE / "golden_benchmark.jsonl") -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def evaluate(cases: list[dict]) -> list[dict]:
    rows = []
    for c in cases:
        llm = ScriptedLLM(*c["llm_outputs"]) if "llm_outputs" in c else MockLLM(*c["llm_modes"])
        result = run(c["input"], llm)
        flagged = any(g.name == c["guard"] and g.flagged for g in result.trace)
        rows.append({
            **c,
            "actual_status": result.status,
            "flagged": flagged,
            "response": result.response,
            "passed": result.status == c["expected_status"] and flagged == c["should_flag"],
        })
    return rows


def metrics(rows: list[dict]) -> dict:
    tp = sum(r["should_flag"] and r["flagged"] for r in rows)
    fp = sum(not r["should_flag"] and r["flagged"] for r in rows)
    fn = sum(r["should_flag"] and not r["flagged"] for r in rows)
    tn = sum(not r["should_flag"] and not r["flagged"] for r in rows)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall}


def _fmt(x):
    return "n/a" if x is None else f"{x:.2f}"


def report(rows: list[dict]) -> str:
    passed = sum(r["passed"] for r in rows)
    out = [f"# Evaluation results\n\n**{passed}/{len(rows)} cases passed.**\n"]

    out.append("## Per-guard detection metrics\n")
    out.append("| Guard | TP | FP | FN | TN | Precision | Recall |\n|---|---|---|---|---|---|---|")
    by_guard = defaultdict(list)
    for r in rows:
        by_guard[r["guard"]].append(r)
    for g, rs in by_guard.items():
        m = metrics(rs)
        out.append(f"| {g} | {m['tp']} | {m['fp']} | {m['fn']} | {m['tn']} | {_fmt(m['precision'])} | {_fmt(m['recall'])} |")
    m = metrics(rows)
    out.append(f"| **all** | {m['tp']} | {m['fp']} | {m['fn']} | {m['tn']} | {_fmt(m['precision'])} | {_fmt(m['recall'])} |\n")

    benign = [r for r in rows if r["expected_status"] == "ok"]
    refused = [r for r in benign if r["actual_status"] != "ok"]
    out.append(f"**False refusals:** {len(refused)}/{len(benign)} requests that should have been answered were not"
               f" ({', '.join(r['id'] for r in refused) or 'none'}).\n")

    out.append("## Per-category pass rate\n")
    out.append("| Category | Passed |\n|---|---|")
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r["passed"])
    for cat, ps in by_cat.items():
        out.append(f"| {cat} | {sum(ps)}/{len(ps)} |")

    out.append("\n## All cases\n")
    out.append("| ID | Category | Input | Reference | Guard | Expected | Actual | Result |\n|---|---|---|---|---|---|---|---|")
    for r in rows:
        exp = f"{r['expected_status']}, {'flag' if r['should_flag'] else 'no flag'}"
        act = f"{r['actual_status']}, {'flag' if r['flagged'] else 'no flag'}"
        text = r["input"].replace("|", "\\|") + (f" _({r['note']})_" if r.get("note") else "")
        out.append(f"| {r['id']} | {r['category']} | {text} | {', '.join(r['reference']) or '-'} | {r['guard']} | {exp} | {act} | {'PASS' if r['passed'] else '**FAIL**'} |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    rows = evaluate(load_cases())
    md = report(rows)
    (HERE / "results.md").write_text(md)
    print(md)
