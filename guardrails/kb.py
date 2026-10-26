"""Tiny bank FAQ knowledge base. Doubles as the groundedness reference."""
import re

KB = {
    "overdraft": "The overdraft fee is $35 per transaction, limited to 3 fees per day.",
    "atm_limit": "The daily ATM withdrawal limit is $500 for standard accounts.",
    "savings_rate": "The savings account pays 2.5% annual interest, compounded monthly.",
    "card_lost": "If your card is lost or stolen, freeze it in the mobile app and call 1-800-555-0100.",
    "wire_fee": "Domestic wire transfers cost $25 and international wire transfers cost $45.",
    "branch_hours": "Branch hours are Monday to Friday, 9am to 5pm, and Saturday 9am to 1pm.",
    "account_opening": "To open an account you need a valid government photo ID and a minimum deposit of $100.",
    "mortgage": "Fixed-rate mortgages require a 5% minimum down payment and a credit score of 620 or higher.",
}

_STOP = {"the", "a", "an", "is", "are", "what", "how", "do", "i", "my", "to", "of", "for", "and", "can", "me", "your"}


def tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9$%.]+", text.lower()) if w not in _STOP}


def retrieve(query: str, k: int = 2) -> list[tuple[str, str]]:
    """Top-k (id, text) KB entries by word overlap; entries with no overlap are dropped."""
    q = tokens(query)
    scored = sorted(((len(q & tokens(t)), i, t) for i, t in KB.items()), reverse=True)
    return [(i, t) for s, i, t in scored[:k] if s > 0]
