"""Cost tracking — aggregate token usage from events."""

from agent_platform.observation.events import EventFilter, EventType
from agent_platform.observation.in_process_event_bus import InProcessEventBus

# Cost per 1K tokens (input, output) in USD.
# Approximate pricing — update as needed.
MODEL_COSTS: dict[str, tuple[float, float]] = {
    "openai/gpt-4.1": (0.002, 0.008),
    "openai/gpt-4.1-mini": (0.0004, 0.0016),
    "openai/gpt-4.1-nano": (0.0001, 0.0004),
    "openai/gpt-5.4": (0.003, 0.012),
    "openai/text-embedding-3-large": (0.00013, 0.0),
    "openai/text-embedding-3-small": (0.00002, 0.0),
    "anthropic/claude-sonnet-4": (0.003, 0.015),
    "anthropic/claude-haiku-4": (0.0008, 0.004),
}

DEFAULT_COST = (0.001, 0.004)  # fallback per 1K tokens


def _get_cost_per_1k(model: str) -> tuple[float, float]:
    """Look up cost for a model, with prefix matching fallback."""
    if model in MODEL_COSTS:
        return MODEL_COSTS[model]
    # Try prefix match
    for prefix, cost in MODEL_COSTS.items():
        if model.startswith(prefix):
            return cost
    return DEFAULT_COST


async def compute_agent_cost(
    event_bus: InProcessEventBus,
    agent_id: str,
) -> dict:
    """Compute cost summary for a single agent."""
    events = await event_bus.query(
        EventFilter(
            agent_id=agent_id,
            event_types=[EventType.LLM_RESPONSE],
        )
    )
    return _aggregate_costs(events)


async def compute_total_cost(
    event_bus: InProcessEventBus,
) -> dict:
    """Compute cost summary across all agents."""
    events = await event_bus.query(EventFilter(event_types=[EventType.LLM_RESPONSE]))
    return _aggregate_costs(events)


def _aggregate_costs(events: list) -> dict:
    """Aggregate token usage and costs from LLM_RESPONSE events."""
    total_prompt = 0
    total_completion = 0
    total_cost = 0.0
    by_model: dict[str, dict] = {}

    for evt in events:
        usage = evt.payload.get("usage", {})
        model = evt.payload.get("model", "unknown")

        prompt = usage.get("prompt_tokens", 0) or 0
        completion = usage.get("completion_tokens", 0) or 0

        total_prompt += prompt
        total_completion += completion

        input_rate, output_rate = _get_cost_per_1k(model)
        cost = (prompt / 1000 * input_rate) + (completion / 1000 * output_rate)
        total_cost += cost

        if model not in by_model:
            by_model[model] = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cost_usd": 0.0,
                "calls": 0,
            }
        by_model[model]["prompt_tokens"] += prompt
        by_model[model]["completion_tokens"] += completion
        by_model[model]["cost_usd"] += cost
        by_model[model]["calls"] += 1

    return {
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "total_cost_usd": round(total_cost, 6),
        "by_model": {
            k: {**v, "cost_usd": round(v["cost_usd"], 6)} for k, v in by_model.items()
        },
    }
