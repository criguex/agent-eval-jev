import os

from agenteval.evaluate import compute


def test_full_evaluation_replays_offline(monkeypatch):
    monkeypatch.setenv("JEV_MODE", "replay")
    monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
    results = compute()
    assert results["meta"]["cases"] == 60
    assert results["repeatability"]["jev"]["repeats_per_case"] >= 5
    assert results["overall"]["composite"]["held_out"]["accuracy"] >= 0.85
    assert os.environ.get("AI_GATEWAY_API_KEY") is None
