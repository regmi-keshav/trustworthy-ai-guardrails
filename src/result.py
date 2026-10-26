from dataclasses import dataclass


@dataclass
class GuardResult:
    name: str
    flagged: bool
    action: str = "allow"  # allow | redact | block | safe_response | escalate | disclaimer | regenerate | fallback
    detail: str = ""
    text: str | None = None  # sanitised text when the guard rewrites it
