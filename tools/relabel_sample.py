from __future__ import annotations

import csv
import html
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "relabel"
SEED = 20261026
QUOTAS = {"live-": 8, "v1-": 3, "mut-": 4}
FIELDS = [
    "case_id",
    "grounded",
    "tool_use",
    "complete",
    "policy",
    "overall",
    "confidence",
    "note",
    "started_at",
    "finished_at",
]


def pick(ids: list[str], seed: int = SEED) -> list[str]:
    rng = random.Random(seed)
    chosen = []
    for prefix, k in QUOTAS.items():
        chosen += rng.sample(sorted(i for i in ids if i.startswith(prefix)), k)
    rng.shuffle(chosen)
    return chosen


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def compact(result) -> str:
    if not isinstance(result, dict):
        return dumps(result)
    lines = []
    for key, value in result.items():
        if isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
            lines.append(f"{key}: ({len(value)})")
            lines += [f"  - {dumps(x)}" for x in value]
        else:
            lines.append(f"{key}: {dumps(value)}")
    return "\n".join(lines)


def rubric() -> str:
    text = (ROOT / "RUBRIC.md").read_text().split("## Ambiguous cases")[0]
    return "\n\n".join(p for p in text.strip().split("\n\n") if not p.startswith("The same four definitions"))


def case_html(code: str, trace: dict) -> str:
    e = html.escape
    parts = [
        f'<section id="{code}"><h2>{code}</h2>',
        "<h3>Petición del usuario</h3>",
        f"<pre>{e(trace['user_request'])}</pre>",
    ]
    parts.append(f"<h3>Llamadas a herramientas ({len(trace['steps'])})</h3>")
    for n, step in enumerate(trace["steps"], 1):
        parts.append(
            f"<p><b>{n}. {e(step['tool'])}</b> <code>{e(dumps(step['args']))}</code></p><pre>{e(compact(step['result']))}</pre>"
        )
    parts.append(f"<h3>Respuesta final</h3><pre>{e(str(trace['final_answer']))}</pre>")
    parts.append(
        f"<p class=fill>Llena la fila <b>{code}</b> en relabel/labels.csv antes de pasar al siguiente caso.</p></section>"
    )
    return "\n".join(parts)


def sheet(sample: list[dict]) -> str:
    traces = {}
    for row in map(json.loads, (ROOT / "data/golden.jsonl").read_text().splitlines()):
        traces[row["id"]] = json.loads((ROOT / "data/traces" / f"{row['trace']}.json").read_text())
    body = "\n".join(case_html(s["code"], traces[s["id"]]) for s in sample)
    toc = " · ".join(f'<a href="#{s["code"]}">{s["code"]}</a>' for s in sample)
    return f"""<!doctype html><html lang=es><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Hoja de reetiquetado</title><style>
:root{{--bg:#fff;--fg:#1a1a1a;--box:#f3f4f6;--line:#d0d4da}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16181c;--fg:#e6e6e6;--box:#22262c;--line:#3a3f47}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:900px;margin:0 auto;padding:16px}}
pre{{background:var(--box);padding:10px;white-space:pre-wrap;word-break:break-word;border-radius:6px}}
section{{border-top:2px solid var(--line);margin-top:32px}} .fill{{font-style:italic}}
</style></head><body>
<h1>Hoja de reetiquetado a ciegas ({len(sample)} casos)</h1>
<p>Lee un caso, llena su fila en <code>relabel/labels.csv</code> y pasa al siguiente. No abras <code>data/</code>,
<code>results/</code>, <code>reports/</code> ni <code>relabel/sample.json</code> hasta haber commiteado labels.csv.</p>
<p>{toc}</p>
<details open><summary><b>Rúbrica (RUBRIC.md, criterios 1-4)</b></summary><pre>{html.escape(rubric())}</pre></details>
{body}
</body></html>
"""


def main() -> None:
    labels = OUT / "labels.csv"
    if labels.exists() and "--force" not in sys.argv:
        sys.exit("relabel/labels.csv ya existe; no se sobrescribe (usa --force solo si está vacío).")
    ids = [json.loads(line)["id"] for line in (ROOT / "data/golden.jsonl").read_text().splitlines() if line.strip()]
    sample = [{"code": f"c{n:02d}", "id": case_id} for n, case_id in enumerate(pick(ids), 1)]
    OUT.mkdir(exist_ok=True)
    (OUT / "sample.json").write_text(json.dumps({"seed": SEED, "quotas": QUOTAS, "cases": sample}, indent=2) + "\n")
    (OUT / "sheet.html").write_text(sheet(sample))
    with labels.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(FIELDS)
        writer.writerows([s["code"]] + [""] * (len(FIELDS) - 1) for s in sample)
    print(f"semilla {SEED}: {len(sample)} casos en relabel/sheet.html; plantilla en relabel/labels.csv")


if __name__ == "__main__":
    main()
