"""Guardrail pipeline: input guards -> LLM -> output guards, with a full audit trace."""
from dataclasses import dataclass, field

from src.input_guards import check_injection, check_pii, check_topic
from src.kb import KB, retrieve
from src.output_guards import check_groundedness, check_schema, check_sensitive_info
from src.result import GuardResult

MAX_ATTEMPTS = 2  # first try + one regeneration

MESSAGES = {
    "blocked": "I can't help with that request.",
    "safe_response": "I'm sorry you're going through this. You're not alone; please call or text 988 (US) to reach a crisis counsellor right now.",
    "escalated": "This sounds like a security matter. I'm connecting you to a human fraud specialist; please also freeze your card in the mobile app.",
    "fallback": "I can't answer that reliably. Please contact support at 1-800-555-0100.",
    "disclaimer": "Note: this is general information, not financial or legal advice.\n\n",
}


@dataclass
class PipelineResult:
    response: str
    status: str  # ok | blocked | safe_response | escalated | fallback
    trace: list[GuardResult] = field(default_factory=list)


def run(user_input: str, llm) -> PipelineResult:
    trace: list[GuardResult] = []

    def done(status, response=None):
        return PipelineResult(response or MESSAGES[status], status, trace)

    pii = check_pii(user_input)
    trace.append(pii)
    text = pii.text

    inj = check_injection(text)
    trace.append(inj)
    if inj.flagged:
        return done("blocked")

    topic = check_topic(text)
    trace.append(topic)
    if topic.action in ("safe_response", "escalate"):
        return done("safe_response" if topic.action == "safe_response" else "escalated")

    passages = retrieve(text)
    for _ in range(MAX_ATTEMPTS):
        schema = check_schema(llm.generate(text, passages))
        trace.append(schema)
        if schema.flagged:
            continue
        data = schema.data
        grounded = check_groundedness(data["answer"], [KB[s] for s in data["sources"]])
        trace.append(grounded)
        if grounded.flagged:
            continue

        sensitive = check_sensitive_info(data["answer"])
        trace.append(sensitive)
        if sensitive.action == "block":
            return done("fallback")
        answer = sensitive.text if sensitive.flagged else data["answer"]
        if topic.action == "disclaimer":
            answer = MESSAGES["disclaimer"] + answer
        return done("ok", answer)

    return done("fallback")
