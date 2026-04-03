"""Time decay strategy for memory scoring."""

import math
from datetime import UTC, datetime

from agent_platform.memory.models import MemoryEntry


class TimeDecayStrategy:
    """Logarithmic decay based on time since last access.

    Score decreases over time but is boosted by access_count and importance.
    """

    def __init__(
        self,
        half_life_days: float = 7.0,
        decay_weights: list[float] | None = None,
    ) -> None:
        self._half_life_seconds = half_life_days * 86400
        w = decay_weights or [0.6, 0.2, 0.2]
        self._w_base = w[0]
        self._w_access = w[1] if len(w) > 1 else 0.2
        self._w_importance = w[2] if len(w) > 2 else 0.2

    def compute(self, entry: MemoryEntry) -> float:
        """Compute decay score for a memory entry. Returns 0.0–1.0."""
        now = datetime.now(UTC)
        elapsed = (now - entry.last_accessed_at).total_seconds()
        elapsed = max(elapsed, 0.0)

        # Base decay: exponential decay with half-life
        base = math.pow(0.5, elapsed / self._half_life_seconds)

        # Access boost: log(1 + access_count) / log(1 + 100)
        access_boost = math.log1p(entry.access_count) / math.log1p(100)

        # Importance boost: directly scales retention
        importance_boost = entry.importance

        # Combined score with configurable weights
        score = (
            self._w_base * base
            + self._w_access * access_boost
            + self._w_importance * importance_boost
        )

        return max(0.0, min(1.0, score))
