from __future__ import annotations

import json
from statistics import mean

from agenteval import judge_llm
from agenteval.checks import run_checks
from agenteval.composite import HARD_GATES, UNCERTAIN_BAND, WEIGHTS, combine, fit_margin, fit_threshold
from agenteval.golden import CRITERIA, ROOT, load_cases, split
from agenteval.jev import MODEL as JEV_MODEL
from agenteval.jev import JevClient
from agenteval.judge_jev import build_state, criterion_probabilities, questions
from agenteval.metrics import (
    accuracy,
    balanced_accuracy,
    cohen_kappa,
    confusion,
    flip_rate,
    mean_std,
    percentile,
    wilson_interval,
)

AUTO_ACCURACY_TARGET = 0.95
RESULTS = ROOT / "results" / "results.json"


def _summary(predicted: list[bool], truth: list[bool]) -> dict:
    hits = sum(p == t for p, t in zip(predicted, truth))
    low, high = wilson_interval(hits, len(truth))
    return {
        "n": len(truth),
        "accuracy": round(accuracy(predicted, truth), 4),
        "accuracy_ci95": [round(low, 4), round(high, 4)],
        "balanced_accuracy": round(balanced_accuracy(predicted, truth), 4),
        "kappa": round(cohen_kappa(predicted, truth), 4),
        "confusion": confusion(predicted, truth),
    }


def _llm_runs(case) -> list[dict]:
    runs = []
    repeat = 0
    while (judge_llm.FIXTURES / f"{case.id}__{repeat}.json").exists():
        runs.append(judge_llm.judge(case, repeat, mode="replay"))
        repeat += 1
    return runs


def collect() -> dict:
    cases = load_cases()
    calibration, held_out = split(cases)
    held_ids = {c.id for c in held_out}
    client = JevClient(mode="replay")
    q = questions()
    rows = []
    for case in cases:
        responses = client.recorded(build_state(case), q)
        if not responses:
            raise SystemExit(f"missing Jev fixture for {case.id}; run `python -m agenteval record-jev`")
        probs = [criterion_probabilities(r) for r in responses]
        llm = _llm_runs(case)
        det = run_checks(case)
        rows.append(
            {
                "case": case,
                "split": "held_out" if case.id in held_ids else "calibration",
                "det": det,
                "jev": probs[0],
                "jev_runs": probs,
                "jev_responses": responses,
                "llm": llm[0]["verdict"] if llm else None,
                "llm_runs": llm,
                "verdict": combine(det["checks"], probs[0]),
                "verdict_runs": [combine(det["checks"], p) for p in probs],
            }
        )
    return {"rows": rows}


def compute() -> dict:
    rows = collect()["rows"]
    cal = [r for r in rows if r["split"] == "calibration"]
    held = [r for r in rows if r["split"] == "held_out"]
    truth = lambda rs: [r["case"].passed for r in rs]

    threshold = fit_threshold([r["verdict"] for r in cal], truth(cal))
    margin = fit_margin([r["verdict"] for r in cal], truth(cal), threshold, AUTO_ACCURACY_TARGET)

    methods = {
        "code_checks": lambda r: r["det"]["passed"],
        "jev_raw": lambda r: all(r["jev"][c] > 0.5 for c in CRITERIA),
        "composite": lambda r: r["verdict"].passes(threshold),
        "llm_judge": lambda r: all(r["llm"][c] for c in CRITERIA) if r["llm"] else False,
    }
    overall = {
        name: {
            part: _summary([fn(r) for r in rs], truth(rs))
            for part, rs in (("calibration", cal), ("held_out", held), ("all", rows))
        }
        for name, fn in methods.items()
    }

    per_criterion = {}
    for criterion in CRITERIA:
        entry = {}
        for part, rs in (("calibration", cal), ("held_out", held), ("all", rows)):
            labels = [r["case"].labels[criterion] for r in rs]
            entry[part] = {
                "jev": _summary([r["jev"][criterion] > 0.5 for r in rs], labels),
                "llm_judge": _summary([bool(r["llm"] and r["llm"][criterion]) for r in rs], labels),
            }
        per_criterion[criterion] = entry

    routing = {}
    for part, rs in (("calibration", cal), ("held_out", held), ("all", rows)):
        decisions = [(r["verdict"].decide(threshold, margin), r["case"].passed) for r in rs]
        auto = [(d == "pass") == t for d, t in decisions if d != "review"]
        reviewed = [t for d, t in decisions if d == "review"]
        routing[part] = {
            "n": len(rs),
            "auto_decided": len(auto),
            "auto_accuracy": round(sum(auto) / len(auto), 4) if auto else None,
            "sent_to_review": len(reviewed),
            "review_share": round(len(reviewed) / len(rs), 4),
            "reviewed_cases_human_fail": sum(not t for t in reviewed),
        }

    jev_requests = [resp for r in rows for resp in r["jev_responses"]]
    jev_decisions = sum(len(resp.answers) for resp in jev_requests)
    repeat_jev = {
        "requests": len(jev_requests),
        "decisions": jev_decisions,
        "repeats_per_case": min(len(r["jev_runs"]) for r in rows),
        "criterion_flip_rate": {
            c: round(flip_rate([[p[c] > 0.5 for p in r["jev_runs"]] for r in rows]), 4) for c in CRITERIA
        },
        "criterion_mean_std": {c: round(mean_std([[p[c] for p in r["jev_runs"]] for r in rows]), 6) for c in CRITERIA},
        "overall_flip_rate": round(flip_rate([[v.passes(threshold) for v in r["verdict_runs"]] for r in rows]), 4),
        "failure_mode_flip_rate": round(flip_rate([[p["failure_mode"] for p in r["jev_runs"]] for r in rows]), 4),
    }
    llm_rows = [r for r in rows if len(r["llm_runs"]) > 1]
    llm_n = min((len(r["llm_runs"]) for r in rows), default=0)
    repeat_jev["comparable_repeats"] = llm_n
    repeat_jev["criterion_flip_rate_comparable"] = {
        c: round(flip_rate([[p[c] > 0.5 for p in r["jev_runs"][:llm_n]] for r in rows]), 4) for c in CRITERIA
    }
    repeat_jev["overall_flip_rate_comparable"] = round(
        flip_rate([[v.passes(threshold) for v in r["verdict_runs"][:llm_n]] for r in rows]), 4
    )
    repeat_llm = {
        "calls": sum(len(r["llm_runs"]) for r in rows),
        "repeats_per_case": min((len(r["llm_runs"]) for r in rows), default=0),
        "criterion_flip_rate": {
            c: round(flip_rate([[run["verdict"][c] for run in r["llm_runs"]] for r in llm_rows]), 4) for c in CRITERIA
        },
        "overall_flip_rate": round(
            flip_rate([[all(run["verdict"][c] for c in CRITERIA) for run in r["llm_runs"]] for r in llm_rows]), 4
        ),
    }

    unpinned = JevClient(mode="replay", route=None)
    unpinned_runs = [
        [criterion_probabilities(x) for x in unpinned.recorded(build_state(r["case"]), questions())] for r in rows
    ]
    unpinned_runs = [runs for runs in unpinned_runs if len(runs) > 1]
    if unpinned_runs:
        repeat_jev["unpinned_gateway"] = {
            "cases": len(unpinned_runs),
            "repeats_per_case": min(len(runs) for runs in unpinned_runs),
            "criterion_flip_rate": {
                c: round(flip_rate([[p[c] > 0.5 for p in runs] for runs in unpinned_runs]), 4) for c in CRITERIA
            },
            "criterion_mean_std": {
                c: round(mean_std([[p[c] for p in runs] for runs in unpinned_runs]), 6) for c in CRITERIA
            },
        }
    probe_path = ROOT / "results" / "provider_probe.json"
    if probe_path.exists():
        repeat_jev["provider_probe"] = json.loads(probe_path.read_text())

    jev_latency = [resp.latency_ms for resp in jev_requests]
    llm_calls = [run for r in rows for run in r["llm_runs"]]
    llm_wall = [run["wall_latency_ms"] for run in llm_calls]
    llm_api = [run["api_latency_ms"] for run in llm_calls if run["api_latency_ms"]]
    latency = {
        "jev": {
            "p50_ms": round(percentile(jev_latency, 0.5), 1),
            "p95_ms": round(percentile(jev_latency, 0.95), 1),
            "mean_ms": round(mean(jev_latency), 1),
            "requests_needing_retry": sum(resp.attempts > 1 for resp in jev_requests),
            "note": "successful attempt only; 429 retries (upstream high demand) excluded from latency",
        },
        "llm_judge": {
            "p50_ms": round(percentile(llm_wall, 0.5), 1) if llm_wall else None,
            "p95_ms": round(percentile(llm_wall, 0.95), 1) if llm_wall else None,
            "api_p50_ms": round(percentile(llm_api, 0.5), 1) if llm_api else None,
            "note": "wall time of `claude -p` includes CLI start-up; api_p50 is the model call alone",
        },
    }
    jev_cost = sum(resp.cost_usd for resp in jev_requests)
    llm_cost = sum(run["cost_usd"] or 0 for run in llm_calls)
    cost = {
        "jev": {
            "total_usd": round(jev_cost, 6),
            "per_evaluation_usd": round(jev_cost / len(jev_requests), 8),
            "per_1000_evaluations_usd": round(1000 * jev_cost / len(jev_requests), 4),
            "mean_input_tokens": round(mean(resp.input_tokens for resp in jev_requests), 1),
            "questions_per_evaluation": len(questions()),
        },
        "llm_judge": {
            "total_usd": round(llm_cost, 6),
            "per_evaluation_usd": round(llm_cost / len(llm_calls), 6) if llm_calls else None,
            "per_1000_evaluations_usd": round(1000 * llm_cost / len(llm_calls), 2) if llm_calls else None,
            "note": "list-price cost reported by the Claude Code CLI",
        },
    }

    agents = {}
    for source in ("agent_v1", "agent_v2", "seeded_defect"):
        rs = [r for r in rows if r["case"].source == source]
        agents[source] = {
            "n": len(rs),
            "human_pass_rate": round(mean(r["case"].passed for r in rs), 4),
            "composite_pass_rate": round(mean(r["verdict"].passes(threshold) for r in rs), 4),
            "hard_gate_failures": sum(bool(r["verdict"].gate_failures) for r in rs),
            "policy_failures": sum(("canary_absent" in r["verdict"].gate_failures) or r["jev"]["policy"] < 0.5 for r in rs),
        }

    case_rows = [
        {
            "id": r["case"].id,
            "split": r["split"],
            "source": r["case"].source,
            "category": r["case"].category,
            "human_pass": r["case"].passed,
            "ambiguous": r["case"].ambiguous,
            "human_labels": r["case"].labels,
            "checks": r["det"]["checks"],
            "check_details": r["det"]["details"],
            "jev": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r["jev"].items()},
            "jev_runs": {c: [round(p[c], 4) for p in r["jev_runs"]] for c in CRITERIA},
            "llm_judge": r["llm"],
            "score": r["verdict"].score,
            "gate_failures": list(r["verdict"].gate_failures),
            "uncertain": list(r["verdict"].uncertain),
            "decision": r["verdict"].decide(threshold, margin),
            "rationale": r["case"].rationale,
        }
        for r in rows
    ]

    return {
        "meta": {
            "cases": len(rows),
            "calibration_cases": len(cal),
            "held_out_cases": len(held),
            "human_pass": sum(r["case"].passed for r in rows),
            "jev_model": sorted({resp.model for resp in jev_requests}),
            "jev_model_requested": JEV_MODEL,
            "jev_providers": sorted({resp.provider or "unrecorded" for resp in jev_requests}),
            "llm_judge_model": sorted({run["model"] for run in llm_calls}),
            "source": "recorded fixtures (fixtures/jev, fixtures/llm_judge)",
        },
        "calibration": {
            "weights": WEIGHTS,
            "hard_gates": list(HARD_GATES),
            "uncertain_band": list(UNCERTAIN_BAND),
            "threshold": threshold,
            "review_margin": margin,
            "auto_accuracy_target": AUTO_ACCURACY_TARGET,
            "routing": routing,
        },
        "overall": overall,
        "per_criterion": per_criterion,
        "repeatability": {"jev": repeat_jev, "llm_judge": repeat_llm},
        "latency": latency,
        "cost": cost,
        "agents": agents,
        "cases": case_rows,
    }


def main() -> dict:
    from agenteval.report import write_reports

    results = compute()
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n")
    write_reports(results)
    held = results["overall"]["composite"]["held_out"]
    print(
        f"composite held-out accuracy {held['accuracy']:.3f} (n={held['n']}), "
        f"threshold {results['calibration']['threshold']}, margin {results['calibration']['review_margin']}"
    )
    return results


def gate(min_agreement: float) -> int:
    results = compute()
    failures = []
    held = results["overall"]["composite"]["held_out"]["accuracy"]
    if held < min_agreement:
        failures.append(f"judge agreement on held-out {held:.3f} < {min_agreement}")
    v2 = results["agents"]["agent_v2"]
    if v2["composite_pass_rate"] < 0.85:
        failures.append(f"agent v2 pass rate {v2['composite_pass_rate']:.2f} < 0.85")
    if v2["policy_failures"]:
        failures.append(f"agent v2 has {v2['policy_failures']} policy failures")
    v1 = results["agents"]["agent_v1"]
    print(f"judge held-out agreement: {held:.3f}")
    print(f"agent v2 pass rate: {v2['composite_pass_rate']:.2f}, policy failures: {v2['policy_failures']}")
    print(f"agent v1 pass rate: {v1['composite_pass_rate']:.2f} (would be blocked by the same gate)")
    for failure in failures:
        print(f"GATE FAILED: {failure}")
    return 1 if failures else 0
