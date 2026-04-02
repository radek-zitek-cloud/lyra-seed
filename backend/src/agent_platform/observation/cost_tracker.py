"""Cost tracking — aggregate token usage from events.

Model costs are loaded from lyra.config.json (per million tokens).
"""

from agent_platform.observation.events import EventFilter, EventType
from agent_platform.observation.in_process_event_bus import InProcessEventBus

# Module-level state — set by configure() on startup
_model_costs: dict[str, list[float]] = {}
_default_cost: list[float] = [1.0, 4.0]


def configure(
    model_costs: dict[str, list[float]],
    default_cost: list[float],
) -> None:
    """Load cost config. Called once during app startup."""
    global _model_costs, _default_cost
    _model_costs = model_costs
    _default_cost = default_cost


def _get_cost_per_million(model: str) -> tuple[float, float]:
    """Look up cost per million tokens, with prefix matching fallback."""
    if model in _model_costs:
        c = _model_costs[model]
        return (c[0], c[1])
    # Try prefix match
    for prefix, c in _model_costs.items():
        if model.startswith(prefix):
            return (c[0], c[1])
    return (_default_cost[0], _default_cost[1])


# Only count provider-level events to avoid double-counting
# (core.runtime also emits LLM_RESPONSE for the same call)
_COST_MODULES = {"llm.openrouter", "embedding.openrouter"}


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
    events = [e for e in events if e.module in _COST_MODULES]
    return _aggregate_costs(events)


async def compute_total_cost(
    event_bus: InProcessEventBus,
) -> dict:
    """Compute cost summary across all agents."""
    events = await event_bus.query(EventFilter(event_types=[EventType.LLM_RESPONSE]))
    events = [e for e in events if e.module in _COST_MODULES]
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

        input_rate, output_rate = _get_cost_per_million(model)
        cost = (prompt / 1_000_000 * input_rate) + (
            completion / 1_000_000 * output_rate
        )
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
