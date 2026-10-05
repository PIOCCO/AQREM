import re


def normalize_question(text: str) -> str:
    lowered = text.lower().strip()
    lowered = re.sub(r"\s+", " ", lowered)
    lowered = re.sub(r"[^\w\s?]", "", lowered)
    return lowered
