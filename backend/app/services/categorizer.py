from __future__ import annotations

import re
from typing import List, Tuple, Optional

ESSENTIALS = {
    "Housing",
    "Utilities",
    "Groceries",
    "Insurance",
    "Healthcare",
    "Transport",
    "Debt",
}


def auto_categorize(description: Optional[str], amount: float) -> str:
    if amount > 0:
        return "Income"
    desc = (description or "").lower()

    patterns: List[Tuple[str, str]] = [
        (r"rent|landlord|mortgage|lease|property", "Housing"),
        (r"electric|water|utility|internet|wifi|comcast|verizon|att|sewer|gas bill", "Utilities"),
        (r"grocery|supermarket|whole foods|aldi|kroger|costco|walmart", "Groceries"),
        (r"uber|lyft|taxi|metro|subway|bus|train|mta|bart|shell|exxon|bp|chevron|gas", "Transport"),
        (r"geico|progressive|state farm|insurance|premium", "Insurance"),
        (r"hospital|doctor|clinic|pharmacy|cvs|walgreens|rite aid|drug", "Healthcare"),
        (r"netflix|spotify|hulu|disney|prime video|youtube|subscription", "Subscriptions"),
        (r"restaurant|cafe|coffee|starbucks|mcdonald|kfc|taco bell|dunkin", "Dining"),
        (r"amazon|etsy|mercado|ebay|aliexpress|shopping", "Shopping"),
        (r"loan|credit card payment|emi|mortgage payment|student loan|auto loan|debt", "Debt"),
        (r"gym|fitness|sports|hobby|game|travel|hotel|airbnb|airline", "Entertainment"),
    ]
    for pattern, label in patterns:
        if re.search(pattern, desc):
            return label
    return "General"


def is_essential(category: str) -> bool:
    return category in ESSENTIALS

