"""Shared utilities used across the platform."""

import math
import os


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def resolve_env_vars(env: dict[str, str]) -> dict[str, str]:
    """Resolve ${VAR_NAME} references from os.environ."""
    return {
        k: os.environ.get(v[2:-1], v) if v.startswith("${") and v.endswith("}") else v
        for k, v in env.items()
    }
