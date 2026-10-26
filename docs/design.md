# Design

How the guardrail pipeline is put together, the contracts between its parts, and where to change it. For the diagram see [architecture.md](architecture.md); for measured results and limitations see [REPORT.md](REPORT.md).

## Goals and non-goals

**Goals**
- Wrap a bank FAQ bot so that customer PII never reaches the model or the answer, attacks and high-risk topics never depend on model output, and every stated fee, limit or rate is backed by the knowledge base.
- Make every decision explainable: each verdict traces back to a specific pattern or threshold.
- Run fully offline and deterministically for tests; use a real model only for demos.

**Non-goals**
- ML detectors (NER, NLI, injection classifiers). They are noted as upgrade paths in `shortcut:` comments.
- Serving, async, auth, persistence and UI.
- Multilingual or non-US formats.

## Components

| Module | Responsibility |
|---|---|
| [guardrails/kb.py](../guardrails/kb.py) | 8-entry FAQ (`KB: dict[id, text]`) and `retrieve(query, k=2)`: top-k entries by word overlap, zero-overlap entries dropped. The KB is also the groundedness reference. |
| [guardrails/llm.py](../guardrails/llm.py) | `MockLLM` (scripted failure modes), `ScriptedLLM` (exact raw outputs) and `GeminiLLM` (live). |
| [guardrails/input/](../guardrails/input/) | `check_pii`, `check_injection`, `check_topic`. |
| [guardrails/output/](../guardrails/output/) | `check_schema`, `check_groundedness`, `check_sensitive_info`. |
| [guardrails/pipeline.py](../guardrails/pipeline.py) | `run(user_input, llm) -> PipelineResult`: orders the guards, applies retry and fallback, builds the trace. |
| [guardrails/__main__.py](../guardrails/__main__.py) | CLI: `python -m guardrails [--mock] "question"` prints status, response and trace. |
| [eval/run_eval.py](../eval/run_eval.py) | Runs the labelled benchmark and computes per-guard metrics. |

## Contracts

**Guard result.** Every guard returns a `GuardResult` ([result.py](../guardrails/result.py)):

```python
GuardResult(name, flagged, action, detail, text=None, data=None)
```

- `action` is one of `allow | redact | block | safe_response | escalate | disclaimer | regenerate`.
- `text` carries the rewritten text when a guard redacts.
- `data` carries the parsed payload (schema guard only).

Guards are pure functions with no knowledge of each other. The pipeline alone decides what an action means.

**LLM client.** Any object with:

```python
generate(question: str, passages: list[tuple[id, text]]) -> str
```

It returns raw text that is expected, but not trusted, to be the JSON `{"answer": str, "sources": [kb_id], "confidence": 0..1}`.

**Pipeline result.**

```python
PipelineResult(response, status, trace)
```

- `status` is one of `ok | blocked | safe_response | escalated | fallback`.
- `trace` lists every `GuardResult` in the order it ran, including each attempt when a regeneration happens.

## Control flow

1. **PII.** The input is redacted. All later stages see only the redacted text.
2. **Injection.** If the score is ≥ 0.8, return `blocked`. No model call is made.
3. **Topic.** `self_harm` returns `safe_response` and `fraud` returns `escalated`, both with fixed messages. `legal_investment` continues, with a disclaimer to be added later.
4. **Retrieve** KB passages.
5. **Generate and validate**, up to `MAX_ATTEMPTS = 2`:
   - **Schema** invalid → try again.
   - **Groundedness**: the answer is checked only against the KB entries it cites. An unsupported sentence → try again.
   - **Sensitive info**: internal data → `fallback` immediately, with no retry. PII → redact.
   - Otherwise return `ok`, with the disclaimer prepended if one is pending.
6. If the attempts run out, return `fallback`.

User-facing messages live in one `MESSAGES` table in `pipeline.py`.

## Policy knobs

| Knob | Location | Value | Effect of changing |
|---|---|---|---|
| Injection threshold | `input/injection.py` `_THRESHOLD` | 0.8 | Lower: blocks more paraphrases, but benign phrases like "you are now…" start to trip it. |
| Injection pattern weights | `input/injection.py` `_INJECTION` | 0.5–1.0 per pattern | Weights are summed. One weak phrase (0.5 or 0.6) alone never blocks. |
| Topic categories and priority | `input/topic.py` `_TOPICS` | self_harm > fraud > legal_investment | The first match wins; the order is the policy. |
| Groundedness overlap | `output/groundedness.py` `_MIN_OVERLAP` | 0.6 | Higher: rejects more valid paraphrases. Lower: lets more invented content through. Numbers must always match. |
| Abstain phrases | `output/groundedness.py` `_ABSTAIN` | "don't have information", "contact support" | These sentences are exempt from the grounding check. |
| Internal-data denylist | `output/sensitive.py` `_INTERNAL` | `.internal` URLs, "system prompt", "confidential", … | A match always triggers fallback. |
| Public contacts allowlist | `output/sensitive.py` `PUBLIC_CONTACTS` | bank support number | These are never redacted from answers. |
| Retry budget | `pipeline.py` `MAX_ATTEMPTS` | 2 | Each extra attempt costs one LLM call. |

## Key decisions

- **Rule-based detectors, standard library only.** We trade detection strength for reproducibility and explainability. The only optional dependency is the Gemini SDK, which is imported lazily.
- **PII redaction is shared.** The input guard and the output guard use the same `redact_pii`, so each fix applies in both directions.
- **Grounding is checked against cited sources only.** The model can't pass by citing one entry and stating facts from another.
- **Gemini runs in JSON mode without a response schema.** This keeps the schema guard exercised by a real model.
- **No retry after a leak.** A model that emitted internal data once is likely to do it again.

## Testing and evaluation

- **Unit tests:** [tests/](../tests/). There is one file per guard group, plus pipeline, LLM, eval and Gemini tests. The Gemini tests cover `.env` loading and key errors and make no network calls. `ScriptedLLM` pins exact outputs for edge cases. `MockLLM` modes (`good`, `hallucinate`, `leak`, `bad_type`, `malformed`) drive the retry and fallback paths.
- **Benchmark:** [eval/golden_benchmark.jsonl](../eval/golden_benchmark.jsonl) is 33 labelled cases. Each case has an input, the expected status, the guard under test, a `should_flag` label, reference KB ids and LLM modes.
- **Runs:**
  - `python -m eval.run_eval` is deterministic and writes `eval/results.md`.
  - `--live` uses Gemini and writes `eval/results_live.md`.

## Extending

- **New guard.** Write a function that returns a `GuardResult`, export it from its package `__init__`, call it at the right point in `run()`, and add tests and benchmark cases.
- **New LLM.** Implement `generate(question, passages)`. Nothing else in the pipeline needs to change.
- **New KB entry.** Add it to `KB`. Retrieval and groundedness pick it up automatically. Add benchmark cases that cite it.
