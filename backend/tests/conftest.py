"""Root conftest — registers custom pytest markers."""


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "smoke: Smoke tests for phase validation")
    config.addinivalue_line("markers", "phase(name): Filter tests by phase identifier")
