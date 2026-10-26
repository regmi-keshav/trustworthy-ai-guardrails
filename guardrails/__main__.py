"""CLI: python -m guardrails [--mock] "question"."""
import sys

from guardrails.llm import GeminiLLM, MockLLM
from guardrails.pipeline import run

args = sys.argv[1:]
mock = "--mock" in args
question = " ".join(a for a in args if a != "--mock") or "What is the overdraft fee?"
try:
    llm = MockLLM() if mock else GeminiLLM()
except (RuntimeError, ImportError) as e:
    sys.exit(f"error: {e}\n(install with `pip install -e \".[gemini]\"`, or use --mock)")
result = run(question, llm)
print(f"status:   {result.status}\nresponse: {result.response}\ntrace:")
for g in result.trace:
    print(f"  {g.name:<15} flagged={g.flagged!s:<5} action={g.action:<13} {g.detail}")
