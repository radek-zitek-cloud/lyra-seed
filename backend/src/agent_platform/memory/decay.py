"""Time decay strategy for memory scoring."""

import math
from datetime import UTC, datetime

from agent_platform.memory.models import MemoryEntry


class TimeDecayStrategy:
    """Logarithmic decay based on time since last access.

    Score decreases over time but is boosted by access_count and importance.
    """

    def __init__(self, half_life_days: float = 7.0) -> None:
        self._half_life_seconds = half_life_days * 86400

    def compute(self, entry: MemoryEntry) -> float:
        """Compute decay score for a memory entry. Returns 0.0–1.0."""
        now = datetime.now(UTC)
        elapsed = (now - entry.last_accessed_at).total_seconds()
        elapsed = max(elapsed, 0.0)

        # Base decay: exponential decay with half-life
        base = math.pow(0.5, elapsed / self._half_life_seconds)

        # Access boost: log(1 + access_count) / log(1 + 100)
        # Maxes out around 100 accesses
        access_boost = math.log1p(entry.access_count) / math.log1p(100)

        # Importance boost: directly scales retention
        importance_boost = entry.importance

        # Combined score: base decay boosted by access and importance
        # Weights: 60% base, 20% access, 20% importance
        score = 0.6 * base + 0.2 * access_boost + 0.2 * importance_boost

        return max(0.0, min(1.0, score))
