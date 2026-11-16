"""V3 llm.py: thinking-setting fallback and the free-tier rate-limit guard (no API key needed)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "v3"))
import llm  # noqa: E402


class FakeModels:
    def __init__(self, errors):
        self.errors = list(errors)
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append(config.thinking_config)
        if self.errors:
            raise RuntimeError(self.errors.pop(0))

        class R:
            text = " ready "
        return R()


class FakeClient:
    def __init__(self, errors=()):
        self.models = FakeModels(errors)
        self.models.generate_content = llm._rate_guard(self.models.generate_content)


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(llm, "_cooldown_until", 0.0)
    monkeypatch.setattr(llm, "_cooldown_daily", False)
    monkeypatch.setattr(llm, "_THINKING_MODE", {})
    monkeypatch.setattr(llm, "flash_model", lambda client: "fake-flash")


def test_bare_invalid_argument_falls_back_to_minimal_thinking():
    c = FakeClient(["400 INVALID_ARGUMENT. Request contains an invalid argument."])
    assert llm.generate(c, "hi") == "ready"
    assert len(c.models.calls) == 2 and llm._THINKING_MODE["fake-flash"] == 1
    llm.generate(c, "again")                          # remembered: no failing first attempt
    assert len(c.models.calls) == 3


def test_429_starts_a_cooldown_without_further_requests():
    c = FakeClient(["429 RESOURCE_EXHAUSTED. {'retryDelay': '20s'}"])
    with pytest.raises(RuntimeError):
        llm.generate(c, "hi")
    assert 15 < llm.cooling_down() <= 20
    with pytest.raises(llm.RateLimited):
        llm.generate(c, "hi")
    assert len(c.models.calls) == 1                   # the second call never reached Gemini


def test_other_errors_do_not_retry_or_cool_down():
    c = FakeClient(["403 PERMISSION_DENIED"])
    with pytest.raises(RuntimeError):
        llm.generate(c, "hi")
    assert len(c.models.calls) == 1 and llm.cooling_down() == 0


def test_daily_quota_is_honoured_in_full():
    c = FakeClient(["429 RESOURCE_EXHAUSTED. {'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', "
                    "'retryDelay': '52980s'}"])
    with pytest.raises(RuntimeError):
        llm.generate(c, "hi")
    assert llm.daily_quota_used_up()
    assert 52970 < llm.cooling_down() <= 52980          # not capped at 2 minutes


def test_busy_server_is_retried(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    c = FakeClient(["503 UNAVAILABLE. high demand", "503 UNAVAILABLE. high demand"])
    assert llm.generate(c, "hi") == "ready"                # third try succeeds
    assert llm.cooling_down() == 0
