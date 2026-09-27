from agenteval.agent.runner import parse_step, system_prompt
from agenteval.agent.tools import call_tool


def test_parse_step_from_fenced_json():
    text = '```json\n{"action":"tool","tool":"geocode","args":{"name":"Lima"}}\n```'
    assert parse_step(text) == {"action": "tool", "tool": "geocode", "args": {"name": "Lima"}}


def test_parse_step_rejects_prose():
    assert parse_step("I cannot help with that") is None


def test_unknown_tool_is_reported_not_raised():
    assert call_tool("book_flight", {}) == {"error": "unknown tool 'book_flight'"}


def test_prompt_versions_differ_only_by_protocol():
    assert "You do have working tools" in system_prompt("v2")
    assert "You do have working tools" not in system_prompt("v1")
