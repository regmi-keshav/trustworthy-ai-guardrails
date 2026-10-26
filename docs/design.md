# Trustworthy AI Guardrails — Design

## Purpose
A runnable Python guardrail pipeline around a **bank customer-support FAQ bot**. It shows input and output guardrails improving privacy, safety and reliability, tests them, and documents their limits. Deliverables: source, 20+ test cases with expected/actual results, evaluation report, architecture diagram, README.

## Decisions
- **Domain:** bank support bot answering from a small FAQ knowledge base (also the groundedness reference).
- **Detection approach:** rule-based, Python stdlib only (+ pytest). Chosen because every pass/failure is explainable, which the failure analysis and trade-off sections need. ML (Presidio, NLI) and LLM-as-judge are documented as upgrade paths, not built.
- **LLM backend:** `MockLLM` (deterministic; can emit good, hallucinated, malformed and PII-leaking answers) for tests; `GeminiLLM` (free tier, `GEMINI_API_KEY`) for live demos. Both implement `generate(prompt, kb_passages) -> str`.

## Data flow
```
user input
 → INPUT GUARDS: 1 PII → 2 Injection → 3 Sensitive topic
 → LLM (sanitised input + KB passages)
 → OUTPUT GUARDS: 4 Schema → 5 Groundedness → 6 Sensitive info
 → final response + audit trace
```
Order rationale: redact PII before anything else sees it; block injections before spending an LLM call; validate schema before groundedness (needs parsed fields); scan sensitive info last so it covers the final text.

Every guard returns `GuardResult(name, flagged, action, detail)`. The pipeline returns the final response and the list of results (trace).

## Guardrails
| Guard | Detection | Action | Limitation |
|---|---|---|---|
| PII (input) | Regex: email, phone, SSN-style ID, 16-digit card with Luhn check | Redact to `[EMAIL]` etc., continue | Misses names, addresses, obfuscated forms |
| Injection | Weighted phrase patterns (override instructions, reveal system prompt, role reassignment) | Block, refuse | Paraphrase, other languages, encoded payloads |
| Sensitive topic | Keyword categories: fraud/account-takeover → escalate to human; self-harm → crisis safe-response; legal/investment advice → disclaimer; else allow | Per-category action | Keyword false positives and implicit-phrasing misses |
| Schema (output) | LLM returns JSON `{answer: str, sources: [kb_id], confidence: float 0–1}`; hand-written type/range checks | Regenerate once, then safe fallback | Structure only, not truth |
| Groundedness | Per sentence: content-word overlap with cited KB entries, plus numeric values (rates, fees, limits) must appear in the KB | Regenerate once, then fallback "please contact support" | Paraphrased hallucinations, negation flips; false flags on valid paraphrase |
| Sensitive info (output) | PII regexes + internal-data denylist (internal URLs, system-prompt text) | Redact; refuse if internal data leaked | Same limits as input PII |

## Failure handling
Regenerate at most once per request. If the output is still invalid, return a safe fallback ("I can't answer that reliably; please contact support"). The trace records which guard fired and what action was taken.

## Layout
```
guardrails/  kb.py  llm.py  pipeline.py  result.py
             input/   pii.py  injection.py  topic.py
             output/  schema.py  groundedness.py  sensitive.py
tests/       unit tests per guard + pipeline
eval/        golden_benchmark.jsonl  run_eval.py  (results written to eval/results.md)
docs/        design.md  REPORT.md
README.md  pyproject.toml
```

## Evaluation
`eval/golden_benchmark.jsonl` holds 24+ cases as data: input, reference info, expected behaviour, ground-truth label. Categories: normal, malicious, sensitive, invalid structure, unsupported claim. `eval/run_eval.py` runs all, prints expected vs actual and pass/fail, and computes precision, recall, false positives and false negatives for guards with labels (PII, injection, topic, groundedness). Schema and sensitive-info cases are reported as pass/fail. The report also covers: ≥2 failure cases with cause/consequence/fix, safety-vs-usability trade-offs (one stricter-is-worse-for-usability, one looser-is-riskier), remaining risks and a deployment verdict.

## Build steps (one commit each)
1. Spec + repo scaffold (this doc, `.gitignore`, README stub)
2. KB + LLM interface + mock
3. Input guards + tests
4. Output guards + tests
5. Pipeline
6. Full test cases + `evaluate.py`
7. Gemini adapter
8. Architecture diagram
9. Report + README

## Out of scope
ML models, async/serving, auth, persistence, UI.
