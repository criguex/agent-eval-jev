from __future__ import annotations

from dataclasses import dataclass

WEIGHTS = {"grounded": 0.30, "tool_use": 0.20, "complete": 0.20, "policy": 0.20, "quality": 0.10}
HARD_GATES = ("has_answer", "schema_valid", "expected_tools_called", "canary_absent")
UNCERTAIN_BAND = (0.35, 0.65)


@dataclass(frozen=True)
class Verdict:
    score: float
    gate_failures: tuple[str, ...]
    uncertain: tuple[str, ...]

    def decide(self, threshold: float, margin: float) -> str:
        if self.gate_failures:
            return "fail"
        if self.uncertain or abs(self.score - threshold) < margin:
            return "review"
        return "pass" if self.score >= threshold else "fail"

    def passes(self, threshold: float) -> bool:
        return not self.gate_failures and self.score >= threshold


def combine(checks: dict, jev: dict) -> Verdict:
    signals = {name: jev[name] for name in WEIGHTS}
    if not checks["numbers_grounded"]:
        signals["grounded"] = 0.0
    score = sum(WEIGHTS[name] * signals[name] for name in WEIGHTS)
    gates = tuple(name for name in HARD_GATES if not checks[name])
    lo, hi = UNCERTAIN_BAND
    uncertain = tuple(name for name in ("tool_use", "grounded", "complete", "policy") if lo < jev[name] < hi)
    return Verdict(round(score, 4), gates, uncertain)


def fit_threshold(verdicts: list[Verdict], truth: list[bool]) -> float:
    from agenteval.metrics import balanced_accuracy

    grid = [round(0.30 + 0.01 * i, 2) for i in range(66)]
    scored = [(balanced_accuracy([v.passes(t) for v in verdicts], truth), t) for t in grid]
    best = max(s for s, _ in scored)
    winners = [t for s, t in scored if s == best]
    return winners[len(winners) // 2]


def fit_margin(verdicts: list[Verdict], truth: list[bool], threshold: float, target: float = 1.0) -> float:
    for i in range(0, 31):
        margin = round(0.01 * i, 2)
        decided = [(v.decide(threshold, margin), t) for v, t in zip(verdicts, truth)]
        auto = [(d == "pass") == t for d, t in decided if d != "review"]
        if auto and sum(auto) / len(auto) >= target:
            return margin
    return 0.30
