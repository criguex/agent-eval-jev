from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor

from agenteval import judge_llm
from agenteval.golden import load_cases
from agenteval.jev import JevClient, JevError
from agenteval.judge_jev import judge


def record_jev(repeats: int, workers: int) -> None:
    client = JevClient(mode="record")

    def one(case) -> str:
        lines = []
        for repeat in range(repeats):
            try:
                response = judge(client, case, repeat)
            except JevError as error:
                lines.append(f"{case.id} #{repeat}: FAILED {str(error)[:120]}")
                break
            lines.append(f"{case.id} #{repeat}: {response.latency_ms:.0f} ms, {response.attempts} attempt(s)")
        return "\n".join(lines)

    with ThreadPoolExecutor(workers) as pool:
        for block in pool.map(one, load_cases()):
            print(block, flush=True)


def record_llm(repeats: int, workers: int) -> None:
    jobs = [(case, repeat) for case in load_cases() for repeat in range(repeats)]

    def one(job) -> str:
        case, repeat = job
        record = judge_llm.judge(case, repeat, mode="record")
        return f"{case.id} #{repeat}: {record['verdict']}"

    with ThreadPoolExecutor(workers) as pool:
        for line in pool.map(one, jobs):
            print(line, flush=True)


def live_check(count: int) -> int:
    from agenteval.golden import CRITERIA
    from agenteval.judge_jev import build_state, criterion_probabilities, questions

    recorded = JevClient(mode="replay")
    live = JevClient(mode="live")
    cases = load_cases()[:: max(1, len(load_cases()) // count)][:count]
    drift = []
    flips = 0
    for case in cases:
        before = criterion_probabilities(recorded.recorded(build_state(case), questions())[0])
        now = criterion_probabilities(live.ask(build_state(case), questions()))
        for criterion in CRITERIA:
            drift.append(abs(before[criterion] - now[criterion]))
            flips += (before[criterion] > 0.5) != (now[criterion] > 0.5)
        print(f"{case.id}: " + ", ".join(f"{c} {before[c]:.2f}->{now[c]:.2f}" for c in CRITERIA), flush=True)
    print(f"max drift {max(drift):.3f}, decision flips {flips}/{len(drift)}")
    return 1 if flips else 0


def provider_probe(case_id: str, calls: int) -> None:
    import json
    from collections import defaultdict
    from statistics import mean

    from agenteval.golden import ROOT
    from agenteval.judge_jev import build_state, criterion_probabilities, questions

    case = next(c for c in load_cases() if c.id == case_id)
    client = JevClient(mode="live", route=None)
    by_provider = defaultdict(list)
    for _ in range(calls):
        response = client.ask(build_state(case), questions())
        by_provider[response.provider or "unknown"].append(round(criterion_probabilities(response)["complete"], 3))
        print(response.provider, by_provider[response.provider or "unknown"][-1], flush=True)
    summary = {
        "case": case_id,
        "criterion": "complete",
        "calls": calls,
        "by_provider": {
            name: {"n": len(v), "min": min(v), "max": max(v), "mean": round(mean(v), 3)} for name, v in by_provider.items()
        },
    }
    (ROOT / "results" / "provider_probe.json").write_text(json.dumps(summary, indent=1) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agenteval")
    sub = parser.add_subparsers(dest="command", required=True)
    rj = sub.add_parser("record-jev", help="call Jev live and store responses as fixtures")
    rj.add_argument("--repeats", type=int, default=5)
    rj.add_argument("--workers", type=int, default=6)
    rl = sub.add_parser("record-llm", help="call the LLM judge (claude -p) and store verdicts")
    rl.add_argument("--repeats", type=int, default=3)
    rl.add_argument("--workers", type=int, default=4)
    lc = sub.add_parser("live-check", help="re-ask Jev live on a sample and compare with the recordings")
    lc.add_argument("--cases", type=int, default=6)
    pp = sub.add_parser("provider-probe", help="ask the same question through the unpinned gateway, grouped by upstream")
    pp.add_argument("--case", default="live-q08")
    pp.add_argument("--calls", type=int, default=20)
    sub.add_parser("evaluate", help="compute every metric from fixtures and write results/ + reports/")
    gate = sub.add_parser("gate", help="exit non-zero if the agent or the judge fall below thresholds")
    gate.add_argument("--min-agreement", type=float, default=0.85)
    args = parser.parse_args(argv)

    if args.command == "record-jev":
        record_jev(args.repeats, args.workers)
    elif args.command == "record-llm":
        record_llm(args.repeats, args.workers)
    elif args.command == "provider-probe":
        provider_probe(args.case, args.calls)
    elif args.command == "live-check":
        return live_check(args.cases)
    elif args.command == "evaluate":
        from agenteval.evaluate import main as evaluate

        evaluate()
    elif args.command == "gate":
        from agenteval.evaluate import gate as run_gate

        return run_gate(args.min_agreement)
    return 0


if __name__ == "__main__":
    sys.exit(main())
