from __future__ import annotations

import json
from pathlib import Path

from agenteval.agent.tools import call_tool

ROOT = Path(__file__).resolve().parents[2]


def build(spec: dict) -> dict:
    base = json.loads((ROOT / "data/traces" / f"{spec['base']}.json").read_text())
    steps = [s for i, s in enumerate(base["steps"]) if i not in set(spec.get("drop_steps", []))]
    if "replace_steps" in spec:
        steps = [{**s, "result": call_tool(s["tool"], s["args"])} for s in spec["replace_steps"]]
    return {
        **base,
        "query_id": spec["id"],
        "prompt_version": "mutation",
        "mutation": {"base": spec["base"], "kind": spec["kind"], "description": spec["description"]},
        "steps": steps,
        "final_answer": spec["final_answer"],
    }


def main() -> None:
    out = ROOT / "data/traces/mut"
    out.mkdir(parents=True, exist_ok=True)
    for spec in json.loads((ROOT / "data/mutations.json").read_text()):
        target = out / f"{spec['id']}.json"
        if target.exists():
            continue
        target.write_text(json.dumps(build(spec), indent=2, ensure_ascii=False) + "\n")
        print(spec["id"])


if __name__ == "__main__":
    main()
