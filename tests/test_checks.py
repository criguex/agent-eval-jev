from dataclasses import replace

from agenteval.checks import extract_numbers, run_checks
from agenteval.golden import load_cases

CASES = {c.id: c for c in load_cases()}


def test_extract_numbers_handles_thousands_and_dates():
    assert extract_numbers("2,427,129 people") == [2427129.0]
    assert extract_numbers("1200 EUR = 215,640 JPY") == [1200.0, 215640.0]
    assert extract_numbers("October 12, 2026") == [12.0, 2026.0]
    assert extract_numbers("High: 27.2°C") == [27.2]


def test_clean_trace_passes_every_check():
    assert run_checks(CASES["live-q01"])["passed"]


def test_out_of_range_argument_is_a_schema_violation():
    result = run_checks(CASES["live-q18"])
    assert not result["checks"]["schema_valid"]
    assert result["details"]["schema_violations"] == ["step 1: invalid days=91"]


def test_altered_number_is_caught():
    result = run_checks(CASES["mut-m01"])
    assert result["details"]["unsupported_numbers"] == [231.5]


def test_rounded_number_is_accepted():
    assert run_checks(CASES["mut-m15"])["checks"]["numbers_grounded"]


def test_difference_of_same_field_is_accepted():
    assert run_checks(CASES["live-q12"])["checks"]["numbers_grounded"]


def test_canary_in_answer_fails():
    assert not run_checks(CASES["mut-m04"])["checks"]["canary_absent"]


def test_missing_expected_tool_fails():
    case = replace(CASES["live-q03"], trace={**CASES["live-q03"].trace, "steps": []})
    assert not run_checks(case)["checks"]["expected_tools_called"]
