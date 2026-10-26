"""Output schema validation."""
import json

from guardrails.kb import KB
from guardrails.result import GuardResult

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
