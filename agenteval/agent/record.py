from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from agenteval.agent.runner import run

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the TripDesk agent live and record traces")
    parser.add_argument("--only", nargs="*", default=None)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--version", choices=["v1", "v2"], default="v2")
    args = parser.parse_args()
    queries = [json.loads(line) for line in (ROOT / "data/queries.jsonl").read_text().splitlines() if line.strip()]
    if args.only:
        queries = [q for q in queries if q["id"] in args.only]
    out = ROOT / "data/traces" / args.version
    out.mkdir(parents=True, exist_ok=True)

    def one(query: dict) -> str:
        if (out / f"{query['id']}.json").exists():
            return f"{query['id']}: already recorded"
        try:
            trace = run(query["id"], query["request"], query.get("injection"), version=args.version)
        except Exception as error:
            return f"{query['id']}: FAILED {error}"
        (out / f"{query['id']}.json").write_text(json.dumps(trace.to_dict(), indent=2, ensure_ascii=False) + "\n")
        return f"{query['id']}: {len(trace.steps)} steps, ${trace.cost_usd:.4f}"

    with ThreadPoolExecutor(args.workers) as pool:
        for line in pool.map(one, queries):
            print(line, flush=True)


if __name__ == "__main__":
    main()
