MODEL_RATES = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "claude-3.5-sonnet": (3.00, 15.00),
    "gemini-2.0-flash": (0.10, 0.40),
    "nexus-extractive": (0.0, 0.0),
}


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    inp, out = MODEL_RATES.get(model, (0.15, 0.60))
    return round((tokens_in / 1_000_000) * inp + (tokens_out / 1_000_000) * out, 6)
