import json

import pytest

from agenteval.jev import JevClient, JevError, MissingFixture, normalize_answer, request_key


def test_gateway_boolean_shape_is_normalized_to_noul():
    assert normalize_answer({"type": "boolean", "probability": 0.8}) == {"type": "noul", "noul": 0.8}


def test_native_noul_passes_through():
    assert normalize_answer({"type": "noul", "noul": 0.1}) == {"type": "noul", "noul": 0.1}


def test_score_and_choice_are_kept():
    raw = {"type": "score", "score": 1.2, "probabilities": {"0": 0.1}, "confidence": 0.5}
    assert normalize_answer(raw) is raw


def test_unknown_answer_type_is_an_error():
    with pytest.raises(JevError):
        normalize_answer({"type": "essay"})


def test_request_key_ignores_key_order():
    assert request_key({"a": 1, "b": {"c": 2, "d": 3}}) == request_key({"b": {"d": 3, "c": 2}, "a": 1})


def test_replay_reads_recorded_repeats(tmp_path):
    client = JevClient(mode="replay", fixtures=tmp_path, route=None)
    body = {"model": "jev-latest", "state": "s", "questions": {"q": {"type": "noul", "instructions": "i"}}}
    response = {
        "answers": {"q": {"type": "noul", "noul": 0.9}},
        "model": "jev",
        "input_tokens": 10,
        "cost_usd": 0.0,
        "latency_ms": 400.0,
        "attempts": 1,
    }
    (tmp_path / f"{request_key(body)}.json").write_text(json.dumps({"request": body, "responses": [response]}))
    assert client.ask("s", body["questions"]).answers["q"]["noul"] == 0.9
    with pytest.raises(MissingFixture):
        client.ask("s", body["questions"], repeat=1)


def test_live_mode_without_key_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(JevError):
        JevClient(mode="live", fixtures=tmp_path).ask("s", {"q": {"type": "noul", "instructions": "i"}})


def test_pinned_and_unpinned_recordings_do_not_collide(tmp_path):
    body = {"model": "jev-latest", "state": "s", "questions": {}}
    pinned = JevClient(mode="replay", fixtures=tmp_path)._path(body)
    unpinned = JevClient(mode="replay", fixtures=tmp_path, route=None)._path(body)
    assert pinned != unpinned
    assert unpinned.name == f"{request_key(body)}.json"
