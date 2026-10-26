from __future__ import annotations

import csv
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from agenteval.metrics import cohen_kappa, wilson_interval

ROOT = Path(__file__).resolve().parents[1]
LABELS = "relabel/labels.csv"
RESULTS = "relabel/RESULTS.md"
CRITERIA = ("grounded", "tool_use", "complete", "policy")


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def labels_commit(repo: Path) -> tuple[str, str]:
    line = git(repo, "log", "-1", "--format=%H %cI", "--", LABELS).stdout.strip()
    if not line:
        raise SystemExit(f"{LABELS} no tiene ningún commit: commitéalo solo antes de comparar.")
    sha, when = line.split()
    if git(repo, "status", "--porcelain", "--", LABELS).stdout.strip():
        raise SystemExit(f"{LABELS} tiene cambios sin commitear.")
    files = git(repo, "show", "--name-only", "--format=", sha).stdout.split()
    if files != [LABELS]:
        raise SystemExit(f"el commit {sha[:7]} debe contener solo {LABELS}; contiene {files}.")
    if datetime.fromisoformat(when) > datetime.now(UTC):
        raise SystemExit(f"el commit {sha[:7]} tiene fecha futura ({when}).")
    first_results = git(repo, "log", "--reverse", "--format=%H", "--", RESULTS).stdout.split()
    if first_results and git(repo, "merge-base", "--is-ancestor", sha, first_results[0]).returncode:
        raise SystemExit(f"{LABELS} cambió después del primer {RESULTS}: el orden ya no es ciego.")
    return sha, when


def read_labels(path: Path) -> dict[str, dict]:
    with path.open(newline="") as f:
        rows = {r["case_id"].strip(): r for r in csv.DictReader(f)}
    for code, r in rows.items():
        bad = [k for k in (*CRITERIA, "overall") if r[k].strip().lower() not in ("pass", "fail")]
        if r["confidence"].strip() not in ("1", "2", "3"):
            bad.append("confidence")
        bad += [k for k in ("started_at", "finished_at") if not r[k].strip()]
        if bad:
            raise SystemExit(f"fila {code} incompleta o inválida: {', '.join(bad)}")
    return rows


def pct(hits: int, n: int) -> str:
    return f"{hits}/{n} ({hits / n:.0%})" if n else "0/0"


def report(rows: dict[str, dict], sample: list[dict], golden: dict[str, dict], decisions: dict[str, str]) -> str:
    ids = {s["code"]: s["id"] for s in sample}
    missing = set(ids) - set(rows)
    if missing:
        raise SystemExit(f"faltan filas en {LABELS}: {sorted(missing)}")
    codes = sorted(ids)
    cris = {c: {k: rows[c][k].strip().lower() == "pass" for k in (*CRITERIA, "overall")} for c in codes}
    ai = {c: {**golden[ids[c]]["labels"], "overall": golden[ids[c]]["pass"]} for c in codes}
    word = lambda b: "pass" if b else "fail"

    out = ["## Cris contra las etiquetas de la IA", "", "| Criterio | Acuerdo | Kappa de Cohen |", "|---|---|---|"]
    gaps = []
    for k in (*CRITERIA, "overall"):
        a, b = [cris[c][k] for c in codes], [ai[c][k] for c in codes]
        out.append(f"| {k} | {pct(sum(x == y for x, y in zip(a, b)), len(codes))} | {cohen_kappa(a, b):.2f} |")
        gaps += [(c, k) for c in codes if cris[c][k] != ai[c][k]]

    decided = [c for c in codes if decisions[ids[c]] != "review"]
    hits = sum(cris[c]["overall"] == (decisions[ids[c]] == "pass") for c in decided)
    low, high = wilson_interval(hits, len(decided))
    review = [c for c in codes if c not in decided]
    out += [
        "",
        "## Cris contra el evaluador compuesto (veredicto global)",
        "",
        f"- Casos decididos por el evaluador: {len(decided)}; enviados a revisión: {len(review)} ({', '.join(review) or 'ninguno'}).",
        f"- Acuerdo en los decididos: {pct(hits, len(decided))}, intervalo de Wilson 95 %: [{low:.2f}, {high:.2f}].",
        "",
        "## Desacuerdos con la IA",
        "",
        "| Código | Caso | Campo | Cris | IA | Nota de Cris |",
        "|---|---|---|---|---|---|",
    ]
    out += [
        f"| {c} | {ids[c]} | {k} | {word(cris[c][k])} | {word(ai[c][k])} | {rows[c]['note'].strip()} |" for c, k in gaps
    ] or ["| - | - | - | - | - | - |"]
    out += ["", "## Desacuerdos con el evaluador", "", "| Código | Caso | Cris | Evaluador |", "|---|---|---|---|"]
    out += [
        f"| {c} | {ids[c]} | {word(cris[c]['overall'])} | {decisions[ids[c]]} |"
        for c in decided
        if cris[c]["overall"] != (decisions[ids[c]] == "pass")
    ] or ["| - | - | - | - |"]
    return "\n".join(out) + "\n"


def main() -> None:
    sha, when = labels_commit(ROOT)
    sample = json.loads((ROOT / "relabel/sample.json").read_text())
    golden = {
        r["id"]: r for r in (json.loads(x) for x in (ROOT / "data/golden.jsonl").read_text().splitlines() if x.strip())
    }
    decisions = {c["id"]: c["decision"] for c in json.loads((ROOT / "results/results.json").read_text())["cases"]}
    body = report(read_labels(ROOT / LABELS), sample["cases"], golden, decisions)
    head = [
        "# Reetiquetado a ciegas: resultados",
        "",
        f"- Commit de labels.csv: `{sha}` ({when})",
        f"- Corrida: {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"- Semilla de la muestra: {sample['seed']} ({len(sample['cases'])} casos)",
        "",
    ]
    (ROOT / RESULTS).write_text("\n".join(head) + "\n" + body)
    print(f"escrito {RESULTS}")


if __name__ == "__main__":
    main()
