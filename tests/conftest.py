"""Keep the default suite isolated from live HTTP services."""

import pytest
import requests


@pytest.fixture(autouse=True)
def block_live_http(request, monkeypatch) -> None:
    """Require non-integration tests to stub their HTTP boundaries."""
    if request.node.get_closest_marker("integration") is not None:
        return

    def blocked_request(*args, **kwargs) -> None:
        pytest.fail("Live HTTP is disabled in unit tests; stub the service boundary.")

    monkeypatch.setattr(requests.sessions.Session, "request", blocked_request)
