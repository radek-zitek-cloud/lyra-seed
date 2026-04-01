"""Shared fixtures for smoke tests."""

from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory (two levels up from backend/tests/smoke/)."""
    return Path(__file__).resolve().parent.parent.parent.parent
