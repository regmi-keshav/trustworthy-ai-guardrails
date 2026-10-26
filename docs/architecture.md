# Architecture

```mermaid
flowchart TD
    U(["User question"]) --> PII

    subgraph IN["Input guardrails (guardrails/input)"]
        PII["1. PII detector<br/>regex + Luhn"] -->|"redacted text"| INJ["2. Injection detector<br/>weighted phrase patterns"]
        INJ -->|"score < 0.8"| TOP["3. Sensitive-topic classifier<br/>keyword categories"]
    end

    INJ -->|"score >= 0.8"| BLOCK["Refusal<br/>status: blocked"]
    TOP -->|"self_harm"| CRISIS["Crisis message (988)<br/>status: safe_response"]
    TOP -->|"fraud"| ESC["Hand off to human<br/>status: escalated"]
    TOP -->|"allow / legal_investment<br/>(disclaimer noted)"| KB["Retrieve KB passages<br/>guardrails/kb.py"]

    KB --> LLM["LLM client<br/>MockLLM / ScriptedLLM (tests)<br/>GeminiLLM (demo)"]

    subgraph OUT["Output guardrails (guardrails/output)"]
        SCH["4. Schema validator<br/>JSON: answer, sources, confidence"] -->|"valid"| GR["5. Groundedness check<br/>word overlap + numbers vs cited KB"]
        GR -->|"supported"| SEN["6. Sensitive-info scan<br/>PII regex + internal denylist"]
    end

    LLM --> SCH
    SCH -->|"invalid"| RETRY{"Attempts left?<br/>(max 2)"}
    GR -->|"unsupported claim"| RETRY
    RETRY -->|"yes: regenerate"| LLM
    RETRY -->|"no"| FB["Safe fallback<br/>status: fallback"]
    SEN -->|"internal data"| FB
    SEN -->|"PII: redact / clean"| OK(["Answer (+ disclaimer if flagged)<br/>status: ok"])

    BLOCK & CRISIS & ESC & FB & OK --> T[["PipelineResult: response, status, trace of every GuardResult"]]
```

## Why each stage sits where it does

| Stage | Placement reason |
|---|---|
| PII first | Nothing downstream (logs, retrieval, the LLM provider) ever sees raw PII. |
| Injection before topic and LLM | Attacks are refused before any model call is spent. |
| Topic before LLM | Self-harm and fraud must never depend on what a model generates; they get fixed, reviewed responses. |
| Schema before groundedness | Groundedness needs the parsed `answer` and `sources` fields. |
| Groundedness before sensitive info | An unsupported answer is regenerated anyway, so scanning it is wasted work. |
| Sensitive info last | It checks the exact text the user will receive. Internal data goes straight to fallback with no retry, because a model that leaked once may leak again. |

Every guard returns the same `GuardResult(name, flagged, action, detail)` ([guardrails/result.py](../guardrails/result.py)), so the pipeline, tests and evaluation treat all six the same way.
