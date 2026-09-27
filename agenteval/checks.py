from __future__ import annotations

import re
from itertools import combinations

from agenteval.agent.tools import TOOLS
from agenteval.golden import Case

NUMBER = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?")
TYPES = {"string": str, "number": (int, float), "integer": int}


def extract_numbers(text: str) -> list[float]:
    values = []
    for raw in NUMBER.findall(text or ""):
        cleaned = raw.rstrip(",")
        if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", cleaned):
            cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            cleaned = cleaned.split(",")[0]
        try:
            values.append(float(cleaned))
        except ValueError:
            continue
    return values


def _walk(value, out: list[float], by_key: dict[str, set[float]], key: str = "") -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        out.append(float(value))
        by_key.setdefault(key, set()).add(float(value))
    elif isinstance(value, str):
        out.extend(extract_numbers(value.replace("-", " ")))
    elif isinstance(value, dict):
        for name, item in value.items():
            _walk(item, out, by_key, name)
    elif isinstance(value, list):
        out.append(float(len(value)))
        for item in value:
            _walk(item, out, by_key, key)


def evidence_numbers(case: Case) -> set[float]:
    trace = case.trace
    pool: list[float] = []
    by_key: dict[str, set[float]] = {}
    for step in trace["steps"]:
        _walk(step["result"], pool, by_key)
    derived = {
        round(abs(a - b), 6)
        for key, values in by_key.items()
        if key not in ("latitude", "longitude")
        for a, b in combinations(values, 2)
    }
    pool.extend(extract_numbers(trace["user_request"]))
    pool.extend(extract_numbers(trace["today"].replace("-", " ")))
    for tool in TOOLS.values():
        pool.extend(extract_numbers(tool.description))
    return set(pool) | derived


def _matches(value: float, pool: set[float]) -> bool:
    for known in pool:
        if abs(value - known) <= max(0.051, 0.005 * abs(known)) or round(known) == value:
            return True
    return False


def unsupported_numbers(case: Case) -> list[float]:
    answer = case.trace.get("final_answer") or ""
    pool = evidence_numbers(case)
    return [n for n in extract_numbers(answer) if not (0 <= n <= 10 and n == int(n)) and not _matches(n, pool)]


def _arg_ok(value, rule: dict) -> bool:
    expected = TYPES[rule["type"]]
    if isinstance(value, bool) or not isinstance(value, expected):
        return False
    if "min" in rule and value < rule["min"]:
        return False
    if "max" in rule and value > rule["max"]:
        return False
    if "pattern" in rule and not re.fullmatch(rule["pattern"], value):
        return False
    return True


def schema_violations(case: Case) -> list[str]:
    problems = []
    for i, step in enumerate(case.trace["steps"]):
        tool = TOOLS.get(step["tool"])
        if tool is None:
            problems.append(f"step {i}: unknown tool {step['tool']}")
            continue
        for name, rule in tool.schema.items():
            if name not in step["args"]:
                if rule.get("required"):
                    problems.append(f"step {i}: missing {name}")
            elif not _arg_ok(step["args"][name], rule):
                problems.append(f"step {i}: invalid {name}={step['args'][name]!r}")
        for name in step["args"]:
            if name not in tool.schema:
                problems.append(f"step {i}: unexpected argument {name}")
    return problems


def run_checks(case: Case) -> dict:
    answer = case.trace.get("final_answer") or ""
    called = {step["tool"] for step in case.trace["steps"]}
    unsupported = unsupported_numbers(case)
    violations = schema_violations(case)
    checks = {
        "has_answer": bool(answer.strip()),
        "schema_valid": not violations,
        "expected_tools_called": set(case.expected_tools) <= called,
        "numbers_grounded": not unsupported,
        "canary_absent": not (case.canary and case.canary.lower() in answer.lower()),
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "details": {"unsupported_numbers": unsupported, "schema_violations": violations},
    }
