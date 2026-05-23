"""
Throughput and cost observability for APOLLO (Groq-only).

Estimates token usage and API cost based on Groq pricing.
All estimates are approximate — actual usage depends on prompt construction,
response length, and model behavior.

Groq pricing (current):
- llama-3.3-70b-versatile: $0.59/1M input tokens, $0.79/1M output tokens
- Character-to-token ratio ~4:1 for English text
"""
from typing import Dict, List, Optional
import time


# Groq model pricing (per 1M tokens)
GROQ_PRICING = {
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "default": {"input": 0.59, "output": 0.79},
}

# Approximate character-to-token ratio
CHARS_PER_TOKEN = 4.0

# Per-minute throughput window
THROUGHPUT_WINDOW_SECONDS = 60.0


def estimate_tokens(char_count: int) -> int:
    """Estimate token count from character count."""
    if isinstance(char_count, str):
        char_count = len(char_count)
    return max(1, int(char_count / CHARS_PER_TOKEN))


def estimate_request_cost(
    prompt_chars: int,
    response_chars: int,
    model: str = "llama-3.3-70b-versatile",
) -> Dict:
    """Estimate API cost for a single request.

    Args:
        prompt_chars: Character count of the prompt.
        response_chars: Character count of the response.
        model: Groq model name.

    Returns:
        Dict with token estimates and cost.
    """
    pricing = GROQ_PRICING.get(model, GROQ_PRICING["default"])
    input_tokens = estimate_tokens(prompt_chars)
    output_tokens = estimate_tokens(response_chars)
    cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
    return {
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "estimated_cost_usd": round(cost, 6),
    }


def estimate_batch_cost(
    requests: List[Dict],
    model: str = "llama-3.3-70b-versatile",
) -> Dict:
    """Estimate total cost for a batch of requests.

    Args:
        requests: List of dicts with 'prompt_chars' and 'response_chars'.
        model: Groq model name.

    Returns:
        Dict with aggregate cost estimates.
    """
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0

    for req in requests:
        est = estimate_request_cost(
            req.get("prompt_chars", 0),
            req.get("response_chars", 0),
            model,
        )
        total_input_tokens += est["input_tokens"]
        total_output_tokens += est["output_tokens"]
        total_cost += est["estimated_cost_usd"]

    return {
        "model": model,
        "request_count": len(requests),
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_tokens": total_input_tokens + total_output_tokens,
        "estimated_total_cost_usd": round(total_cost, 4),
    }


def compute_throughput(
    timestamps: List[float],
    window_seconds: float = THROUGHPUT_WINDOW_SECONDS,
) -> Dict:
    """Compute throughput statistics from a list of timestamps.

    Args:
        timestamps: List of Unix timestamps.
        window_seconds: Sliding window for rate calculation.

    Returns:
        Dict with requests_per_minute and time range.
    """
    if not timestamps:
        return {"requests_per_minute": 0.0, "total": 0}
    now = time.time()
    cutoff = now - window_seconds
    recent = [t for t in timestamps if t >= cutoff]
    rate = len(recent) / (window_seconds / 60.0) if window_seconds > 0 else 0.0
    return {
        "requests_per_minute": round(rate, 2),
        "total": len(timestamps),
        "recent": len(recent),
        "window_seconds": window_seconds,
        "time_range": {
            "earliest": min(timestamps),
            "latest": max(timestamps),
        },
    }


def compute_retry_amplification(
    total_requests: int,
    unique_items: int,
) -> float:
    """Compute retry amplification factor.

    amp = total_requests / max(unique_items, 1)

    1.0 = no retries, > 1.0 = some items required retries.
    """
    if unique_items <= 0:
        return 1.0
    return round(total_requests / unique_items, 4)


def compute_cache_savings(
    cache_hits: int,
    avg_cost_per_request: float = 0.001,
) -> Dict:
    """Compute estimated cache savings.

    Args:
        cache_hits: Number of cache hits.
        avg_cost_per_request: Average cost per LLM request in USD.

    Returns:
        Dict with estimated savings.
    """
    return {
        "cache_hits": cache_hits,
        "avg_cost_per_request_usd": avg_cost_per_request,
        "estimated_savings_usd": round(cache_hits * avg_cost_per_request, 4),
    }
