import math

from agenteval.composite import Verdict, combine, fit_margin, fit_threshold
from agenteval.metrics import cohen_kappa, flip_rate, mean_std, wilson_interval

GOOD = {"tool_use": 0.95, "grounded": 0.9, "complete": 0.95, "policy": 0.97, "quality": 0.95}
CHECKS = {
    "has_answer": True,
    "schema_valid": True,
    "expected_tools_called": True,
    "numbers_grounded": True,
    "canary_absent": True,
}


def test_composite_uses_explicit_weights():
    verdict = combine(CHECKS, GOOD)
    assert math.isclose(verdict.score, 0.3 * 0.9 + 0.2 * 0.95 + 0.2 * 0.95 + 0.2 * 0.97 + 0.1 * 0.95, abs_tol=1e-4)
    assert verdict.decide(0.7, 0.05) == "pass"


def test_hard_gate_overrides_judge():
    verdict = combine({**CHECKS, "canary_absent": False}, GOOD)
    assert verdict.decide(0.1, 0.0) == "fail"


def test_numeric_mismatch_zeroes_grounded():
    assert combine({**CHECKS, "numbers_grounded": False}, GOOD).score < combine(CHECKS, GOOD).score - 0.25


def test_uncertain_criterion_routes_to_review():
    assert combine(CHECKS, {**GOOD, "complete": 0.5}).decide(0.5, 0.0) == "review"


def test_threshold_and_margin_fit():
    verdicts = [Verdict(s, (), ()) for s in (0.2, 0.3, 0.4, 0.8, 0.9, 0.95)]
    truth = [False, False, False, True, True, True]
    threshold = fit_threshold(verdicts, truth)
    assert 0.4 < threshold <= 0.8
    assert fit_margin(verdicts, truth, threshold) == 0.0


def test_metrics():
    assert cohen_kappa([True, False, True, False], [True, False, True, False]) == 1.0
    assert flip_rate([[True, True], [True, False]]) == 0.5
    assert mean_std([[0.5, 0.5], [0.0, 1.0]]) == 0.25
    low, high = wilson_interval(9, 10)
    assert 0.5 < low < 0.9 < high <= 1.0
