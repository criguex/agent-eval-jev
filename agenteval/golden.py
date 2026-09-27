from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRITERIA = ("tool_use", "grounded", "complete", "policy")


@dataclass(frozen=True)
class Case:
    id: str
    source: str
    category: str
    expected_tools: tuple[str, ...]
    canary: str | None
    labels: dict
    passed: bool
    ambiguous: bool
    rationale: str
    trace: dict


def load_cases(path: Path = ROOT / "data/golden.jsonl") -> list[Case]:
    cases = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        trace = json.loads((ROOT / "data/traces" / f"{row['trace']}.json").read_text())
        cases.append(
            Case(
                id=row["id"],
                source=row["source"],
                category=row["category"],
                expected_tools=tuple(row["expected_tools"]),
                canary=row["canary"],
                labels=row["labels"],
                passed=row["pass"],
                ambiguous=row["ambiguous"],
                rationale=row["rationale"],
                trace=trace,
            )
        )
    return cases


def split(cases: list[Case]) -> tuple[list[Case], list[Case]]:
    calibration, held_out = [], []
    buckets: dict[tuple[str, bool], list[Case]] = {}
    for case in sorted(cases, key=lambda c: c.id):
        buckets.setdefault((case.source, case.passed), []).append(case)
    for key in sorted(buckets):
        for i, case in enumerate(buckets[key]):
            (calibration if i % 2 == 0 else held_out).append(case)
    return calibration, held_out
