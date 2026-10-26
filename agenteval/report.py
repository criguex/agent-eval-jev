from __future__ import annotations

import html

from agenteval.golden import CRITERIA, ROOT

REPORTS = ROOT / "reports"
METHOD_LABELS = {
    "code_checks": "Code checks only",
    "jev_raw": "Jev, raw (all criteria > 0.5)",
    "composite": "Composite (code + Jev, calibrated)",
    "llm_judge": "LLM judge (Claude Sonnet)",
}
SVG_STYLE = """<style>
svg{--surface:#071B2B;--ink:#F4F7F5;--ink2:#ABC0C8;--grid:#214456;--s1:#55DFBD;--s2:#8FA6B0;--s3:#FB8176;font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.bg{fill:var(--surface)}.t{fill:var(--ink);font-size:13px}.m{fill:var(--ink2);font-size:12px}.h{fill:var(--ink);font-size:15px;font-weight:600}
.g{stroke:var(--grid);stroke-width:1}.s1{fill:var(--s1)}.s2{fill:var(--s2)}.l1{stroke:var(--s1)}.ref{stroke:var(--ink2);stroke-dasharray:4 3}
.dot1{fill:var(--s1);stroke:var(--surface);stroke-width:2}.dot2{fill:var(--s3);stroke:var(--surface);stroke-width:2}
</style>"""


def _bar(x: float, y: float, w: float, h: float, cls: str, title: str) -> str:
    w = max(w, 0.5)
    r = min(4, w / 2, h / 2)
    path = f"M{x:.1f},{y:.1f} h{w - r:.1f} a{r},{r} 0 0 1 {r},{r} v{h - 2 * r:.1f} a{r},{r} 0 0 1 -{r},{r} h-{w - r:.1f} z"
    return f'<path class="{cls}" d="{path}"><title>{html.escape(title)}</title></path>'


def _svg(width: int, height: int, title: str, body: list[str]) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="{html.escape(title)}">{SVG_STYLE}'
        f'<rect class="bg" width="{width}" height="{height}" rx="8"/>'
        f'<text class="h" x="16" y="26">{html.escape(title)}</text>' + "".join(body) + "</svg>"
    )


def _axis(x0: float, x1: float, top: float, bottom: float, ticks=(0, 0.25, 0.5, 0.75, 1.0), pct=True) -> list[str]:
    out = []
    for t in ticks:
        x = x0 + (x1 - x0) * t
        out.append(f'<line class="g" x1="{x:.1f}" x2="{x:.1f}" y1="{top}" y2="{bottom}"/>')
        label = f"{int(t * 100)}%" if pct else f"{t:.2f}"
        out.append(f'<text class="m" x="{x:.1f}" y="{bottom + 16}" text-anchor="middle">{label}</text>')
    return out


def chart_overall(results: dict) -> str:
    width, left, right = 720, 270, 660
    rows = list(METHOD_LABELS)
    body = ['<text class="m" x="16" y="46">Share of cases where the verdict matches the reference pass/fail label</text>']
    top = 70
    body += _axis(left, right, top - 8, top + len(rows) * 44)
    for i, name in enumerate(rows):
        y = top + i * 44
        held = results["overall"][name]["held_out"]
        every = results["overall"][name]["all"]
        body.append(f'<text class="t" x="{left - 10}" y="{y + 17}" text-anchor="end">{METHOD_LABELS[name]}</text>')
        body.append(
            _bar(
                left, y + 2, (right - left) * held["accuracy"], 14, "s1", f"held-out {held['accuracy']:.1%} (n={held['n']})"
            )
        )
        body.append(
            _bar(
                left,
                y + 18,
                (right - left) * every["accuracy"],
                14,
                "s2",
                f"all cases {every['accuracy']:.1%} (n={every['n']})",
            )
        )
        body.append(
            f'<text class="m" x="{left + (right - left) * held["accuracy"] + 6:.1f}" y="{y + 13}">{held["accuracy"]:.0%}</text>'
        )
        body.append(
            f'<text class="m" x="{left + (right - left) * every["accuracy"] + 6:.1f}" y="{y + 29}">{every["accuracy"]:.0%}</text>'
        )
    ly = top + len(rows) * 44 + 34
    body.append(
        f'<rect class="s1" x="{left}" y="{ly - 10}" width="12" height="12" rx="2"/><text class="m" x="{left + 18}" y="{ly}">held-out split (n={results["meta"]["held_out_cases"]})</text>'
    )
    body.append(
        f'<rect class="s2" x="{left + 200}" y="{ly - 10}" width="12" height="12" rx="2"/><text class="m" x="{left + 218}" y="{ly}">all cases (n={results["meta"]["cases"]})</text>'
    )
    return _svg(width, ly + 18, "Agreement with reference labels (overall pass/fail)", body)


def chart_criteria(results: dict) -> str:
    width, left, right = 720, 130, 660
    body = ['<text class="m" x="16" y="46">Per-criterion agreement on the held-out split, decision at 0.5 for Jev</text>']
    top = 70
    body += _axis(left, right, top - 8, top + len(CRITERIA) * 44)
    for i, criterion in enumerate(CRITERIA):
        y = top + i * 44
        entry = results["per_criterion"][criterion]["held_out"]
        body.append(f'<text class="t" x="{left - 10}" y="{y + 17}" text-anchor="end">{criterion}</text>')
        for j, (key, cls) in enumerate((("jev", "s1"), ("llm_judge", "s2"))):
            acc = entry[key]["accuracy"]
            body.append(
                _bar(
                    left, y + 2 + 16 * j, (right - left) * acc, 14, cls, f"{key} {acc:.1%}, kappa {entry[key]['kappa']:.2f}"
                )
            )
            body.append(f'<text class="m" x="{left + (right - left) * acc + 6:.1f}" y="{y + 13 + 16 * j}">{acc:.0%}</text>')
    ly = top + len(CRITERIA) * 44 + 34
    body.append(
        f'<rect class="s1" x="{left}" y="{ly - 10}" width="12" height="12" rx="2"/><text class="m" x="{left + 18}" y="{ly}">Jev</text>'
    )
    body.append(
        f'<rect class="s2" x="{left + 80}" y="{ly - 10}" width="12" height="12" rx="2"/><text class="m" x="{left + 98}" y="{ly}">LLM judge</text>'
    )
    return _svg(width, ly + 18, "Agreement per rubric criterion", body)


def chart_strip(results: dict) -> str:
    width, left, right = 720, 130, 680
    body = [
        f'<text class="m" x="16" y="46">Jev probability that the criterion holds, one dot per case (all {results["meta"]["cases"]})</text>'
    ]
    top = 74
    band = 46
    body += _axis(left, right, top - 12, top + len(CRITERIA) * band - 10, pct=False)
    body.append(
        f'<line class="ref" x1="{left + (right - left) * 0.5}" x2="{left + (right - left) * 0.5}" y1="{top - 12}" y2="{top + len(CRITERIA) * band - 10}"/>'
    )
    for i, criterion in enumerate(CRITERIA):
        y = top + i * band
        body.append(f'<text class="t" x="{left - 10}" y="{y + 14}" text-anchor="end">{criterion}</text>')
        for k, case in enumerate(results["cases"]):
            p = case["jev"][criterion]
            ok = case["human_labels"][criterion]
            jitter = (k * 7919) % 17 - 8
            cy = y + 10 + (-9 if ok else 9) + jitter * 0.35
            cls = "dot1" if ok else "dot2"
            body.append(
                f'<circle class="{cls}" cx="{left + (right - left) * p:.1f}" cy="{cy:.1f}" r="5">'
                f"<title>{html.escape(case['id'])}: p={p:.2f}, reference={'yes' if ok else 'no'}</title></circle>"
            )
    ly = top + len(CRITERIA) * band + 22
    body.append(
        f'<circle class="dot1" cx="{left + 6}" cy="{ly - 4}" r="5"/><text class="m" x="{left + 16}" y="{ly}">reference label: criterion met</text>'
    )
    body.append(
        f'<circle class="dot2" cx="{left + 226}" cy="{ly - 4}" r="5"/><text class="m" x="{left + 236}" y="{ly}">reference label: criterion violated</text>'
    )
    return _svg(width, ly + 16, "How well Jev separates good from bad", body)


def chart_repeat(results: dict) -> str:
    width, left, right = 720, 130, 660
    jev = results["repeatability"]["jev"]
    llm = results["repeatability"]["llm_judge"]
    peak = max([0.2] + list(jev["criterion_flip_rate_comparable"].values()) + list(llm["criterion_flip_rate"].values()))
    scale = 0.2 if peak <= 0.2 else 0.4 if peak <= 0.4 else 1.0
    body = [
        f'<text class="m" x="16" y="46">Share of cases whose decision changes across repeats '
        f"(first {jev['comparable_repeats']} runs of each judge); lower is better</text>"
    ]
    top = 70
    ticks = [scale * t for t in (0, 0.25, 0.5, 0.75, 1.0)]
    for t in ticks:
        x = left + (right - left) * t / scale
        body.append(f'<line class="g" x1="{x:.1f}" x2="{x:.1f}" y1="{top - 8}" y2="{top + len(CRITERIA) * 44}"/>')
        body.append(f'<text class="m" x="{x:.1f}" y="{top + len(CRITERIA) * 44 + 16}" text-anchor="middle">{t:.0%}</text>')
    for i, criterion in enumerate(CRITERIA):
        y = top + i * 44
        body.append(f'<text class="t" x="{left - 10}" y="{y + 17}" text-anchor="end">{criterion}</text>')
        for j, (key, source, cls, name) in enumerate(
            (("criterion_flip_rate_comparable", jev, "s1", "Jev"), ("criterion_flip_rate", llm, "s2", "LLM judge"))
        ):
            v = source[key][criterion]
            body.append(_bar(left, y + 2 + 16 * j, (right - left) * v / scale, 14, cls, f"{name}: {v:.1%} of cases flip"))
            body.append(
                f'<text class="m" x="{left + (right - left) * v / scale + 6:.1f}" y="{y + 13 + 16 * j}">{v:.1%}</text>'
            )
    ly = top + len(CRITERIA) * 44 + 40
    body.append(
        f'<rect class="s1" x="{left}" y="{ly - 10}" width="12" height="12" rx="2"/><text class="m" x="{left + 18}" y="{ly}">Jev</text>'
    )
    body.append(
        f'<rect class="s2" x="{left + 80}" y="{ly - 10}" width="12" height="12" rx="2"/><text class="m" x="{left + 98}" y="{ly}">LLM judge</text>'
    )
    return _svg(width, ly + 18, "Repeatability: decision flips across identical runs", body)


def _pct(v) -> str:
    return "n/a" if v is None else f"{v:.1%}"


def _unpinned_section(jev: dict) -> list[str]:
    lines = []
    unpinned = jev.get("unpinned_gateway")
    probe = jev.get("provider_probe")
    if not unpinned and not probe:
        return lines
    lines += ["## Upstream provider effect", ""]
    if probe:
        parts = ", ".join(
            f"{name}: {v['n']} calls, {v['min']:.2f}-{v['max']:.2f}" for name, v in sorted(probe["by_provider"].items())
        )
        lines += [
            f"The gateway can serve Jev from more than one upstream. {probe['calls']} identical calls for `{probe['case']}` "
            f"(criterion `{probe['criterion']}`) without pinning: {parts}. All numbers above come from calls pinned to "
            "`typesafe-ai` (`providerOptions.gateway.only`).",
            "",
        ]
    if unpinned:
        lines += [
            f"A first recording without pinning ({unpinned['cases']} cases x {unpinned['repeats_per_case']} runs) is kept for comparison:",
            "",
            "| Criterion | Unpinned flip rate | Unpinned mean std | Pinned flip rate | Pinned mean std |",
            "|---|---|---|---|---|",
        ]
        for c in CRITERIA:
            lines.append(
                f"| {c} | {unpinned['criterion_flip_rate'][c]:.1%} | {unpinned['criterion_mean_std'][c]:.4f} | "
                f"{jev['criterion_flip_rate'][c]:.1%} | {jev['criterion_mean_std'][c]:.4f} |"
            )
        lines.append("")
    return lines


def _markdown(results: dict) -> str:
    m, cal = results["meta"], results["calibration"]
    ov, lat, cost, rep = results["overall"], results["latency"], results["cost"], results["repeatability"]
    lines = [
        "# Evaluation report",
        "",
        f"Generated from recorded fixtures. {m['cases']} golden cases ({m['human_pass']} reference PASS), "
        f"calibration split {m['calibration_cases']}, held-out split {m['held_out_cases']}. "
        f"Jev model: {', '.join(m['jev_model'])}. LLM judge: {', '.join(m['llm_judge_model'])}.",
        "",
        "Reference labels: drafted by an AI assistant against the written rubric (RUBRIC.md), then reviewed and "
        "approved by one person. There is no independent human annotator, so every agreement figure below is "
        "agreement with AI-drafted, human-reviewed labels, not with independent human judgment.",
        "",
        "![overall](charts/overall.svg)",
        "",
        "## Overall pass/fail agreement with reference labels",
        "",
        "| Method | Held-out accuracy (95% CI) | Held-out kappa | All-cases accuracy | False PASS (all) | False FAIL (all) |",
        "|---|---|---|---|---|---|",
    ]
    for name, label in METHOD_LABELS.items():
        h, a = ov[name]["held_out"], ov[name]["all"]
        lines.append(
            f"| {label} | {h['accuracy']:.1%} ({h['accuracy_ci95'][0]:.0%}-{h['accuracy_ci95'][1]:.0%}) | {h['kappa']:.2f} | "
            f"{a['accuracy']:.1%} | {a['confusion']['false_pass']} | {a['confusion']['false_fail']} |"
        )
    r_held = cal["routing"]["held_out"]
    lines += [
        "",
        "## Calibration",
        "",
        f"Weights (fixed before fitting): {', '.join(f'{k} {v:.2f}' for k, v in cal['weights'].items())}. "
        f"Hard gates (code): {', '.join(cal['hard_gates'])}. If the numeric check fails, the grounded signal is forced to 0.",
        "",
        f"Fitted on the calibration split only: pass threshold **{cal['threshold']}**, review margin **{cal['review_margin']}** "
        f"(smallest margin whose automatic decisions reach {cal['auto_accuracy_target']:.0%} accuracy on calibration). "
        f"Any criterion probability inside {tuple(cal['uncertain_band'])} also routes to human review.",
        "",
        "| Split | Cases | Auto-decided | Auto accuracy | Sent to review | Reviewed cases labeled FAIL |",
        "|---|---|---|---|---|---|",
    ]
    for part in ("calibration", "held_out", "all"):
        r = cal["routing"][part]
        lines.append(
            f"| {part} | {r['n']} | {r['auto_decided']} | {_pct(r['auto_accuracy'])} | {r['sent_to_review']} | {r['reviewed_cases_human_fail']} |"
        )
    lines += [
        "",
        f"On held-out, {r_held['auto_decided']} of {r_held['n']} cases were decided automatically at "
        f"{_pct(r_held['auto_accuracy'])} agreement; {r_held['sent_to_review']} went to a human.",
        "",
        "![criteria](charts/criteria.svg)",
        "",
        "## Per-criterion agreement",
        "",
        "| Criterion | Jev held-out | Jev kappa | LLM held-out | LLM kappa | Jev all | LLM all |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in CRITERIA:
        h, a = results["per_criterion"][c]["held_out"], results["per_criterion"][c]["all"]
        lines.append(
            f"| {c} | {h['jev']['accuracy']:.1%} | {h['jev']['kappa']:.2f} | {h['llm_judge']['accuracy']:.1%} | "
            f"{h['llm_judge']['kappa']:.2f} | {a['jev']['accuracy']:.1%} | {a['llm_judge']['accuracy']:.1%} |"
        )
    lines += [
        "",
        "![strip](charts/strip.svg)",
        "",
        "## Repeatability",
        "",
        f"Jev: {rep['jev']['requests']} requests ({rep['jev']['decisions']} typed decisions), "
        f"{rep['jev']['repeats_per_case']} identical requests per case. "
        f"LLM judge: {rep['llm_judge']['calls']} calls, {rep['llm_judge']['repeats_per_case']} per case.",
        "",
        "A flip means the decision (probability above or below 0.5, or the boolean) differs between identical runs "
        "of the same case. Jev is shown both over the first "
        f"{rep['jev']['comparable_repeats']} runs (same count as the LLM judge) and over all {rep['jev']['repeats_per_case']}.",
        "",
        f"| Criterion | Jev flip rate ({rep['jev']['comparable_repeats']} runs) | Jev flip rate ({rep['jev']['repeats_per_case']} runs) "
        f"| Jev mean std of probability | LLM flip rate ({rep['llm_judge']['repeats_per_case']} runs) |",
        "|---|---|---|---|---|",
    ]
    for c in CRITERIA:
        lines.append(
            f"| {c} | {rep['jev']['criterion_flip_rate_comparable'][c]:.1%} | {rep['jev']['criterion_flip_rate'][c]:.1%} | "
            f"{rep['jev']['criterion_mean_std'][c]:.4f} | {rep['llm_judge']['criterion_flip_rate'][c]:.1%} |"
        )
    lines += [
        f"| overall verdict | {rep['jev']['overall_flip_rate_comparable']:.1%} (composite) | "
        f"{rep['jev']['overall_flip_rate']:.1%} (composite) | | {rep['llm_judge']['overall_flip_rate']:.1%} |",
        "",
        "![repeat](charts/repeat.svg)",
        "",
        *_unpinned_section(rep["jev"]),
        "",
        "## Latency and cost",
        "",
        "| | Jev | LLM judge |",
        "|---|---|---|",
        f"| p50 latency | {lat['jev']['p50_ms']:.0f} ms | {lat['llm_judge']['p50_ms']:.0f} ms wall ({lat['llm_judge']['api_p50_ms']:.0f} ms API) |",
        f"| p95 latency | {lat['jev']['p95_ms']:.0f} ms | {lat['llm_judge']['p95_ms']:.0f} ms wall |",
        f"| Cost per evaluated trace | ${cost['jev']['per_evaluation_usd']:.6f} ({cost['jev']['questions_per_evaluation']} questions) | ${cost['llm_judge']['per_evaluation_usd']:.4f} |",
        f"| Cost per 1,000 traces | ${cost['jev']['per_1000_evaluations_usd']:.3f} | ${cost['llm_judge']['per_1000_evaluations_usd']:.2f} |",
        f"| Total spent for this report | ${cost['jev']['total_usd']:.4f} | ${cost['llm_judge']['total_usd']:.2f} |",
        "",
        f"Jev latency counts the successful attempt only; {lat['jev']['requests_needing_retry']} of "
        f"{rep['jev']['requests']} requests first got HTTP 429 (upstream high demand) and were retried with backoff. "
        f"LLM judge cost is the list price reported by the Claude Code CLI.",
        "",
        "## Agent versions",
        "",
        "| Trace source | Cases | Reference pass rate | Composite pass rate | Hard-gate failures |",
        "|---|---|---|---|---|",
    ]
    for source, a in results["agents"].items():
        lines.append(
            f"| {source} | {a['n']} | {a['human_pass_rate']:.0%} | {a['composite_pass_rate']:.0%} | {a['hard_gate_failures']} |"
        )
    lines += [
        "",
        "## Disagreements (composite vs reference label)",
        "",
        "| Case | Split | Reference | Score | Decision | Gates / uncertain | Rationale |",
        "|---|---|---|---|---|---|---|",
    ]
    threshold = cal["threshold"]
    for case in results["cases"]:
        predicted = not case["gate_failures"] and case["score"] >= threshold
        if predicted != case["human_pass"]:
            notes = ", ".join(case["gate_failures"] + [f"~{u}" for u in case["uncertain"]]) or "-"
            lines.append(
                f"| {case['id']} | {case['split']} | {'PASS' if case['human_pass'] else 'FAIL'} | {case['score']:.2f} | "
                f"{case['decision']} | {notes} | {case['rationale']} |"
            )
    return "\n".join(lines) + "\n"


def _html(results: dict, charts: dict[str, str], markdown: str) -> str:
    import re

    body = []
    in_table = False
    for line in markdown.splitlines():
        if line.startswith("![") and "(" in line:
            name = line[line.index("(") + 1 : line.index(")")].split("/")[-1].replace(".svg", "")
            body.append(f"<figure>{charts[name]}</figure>")
            continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if set("".join(cells)) <= set("-"):
                continue
            if not in_table:
                body.append('<div class="scroll"><table>')
                body.append("<tr>" + "".join(f"<th>{html.escape(c)}</th>" for c in cells) + "</tr>")
                in_table = True
            else:
                body.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in cells) + "</tr>")
            continue
        if in_table:
            body.append("</table></div>")
            in_table = False
        if line.startswith("# "):
            body.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            body.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.strip():
            text = html.escape(line)
            text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
            body.append(f"<p>{text}</p>")
    if in_table:
        body.append("</table></div>")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent Eval Report</title>
<style>
:root{{--bg:#071B2B;--ink:#F4F7F5;--ink2:#ABC0C8;--line:#214456;--head:#0D2638;color-scheme:dark}}
body{{background:var(--bg);color:var(--ink);font:15px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0}}
main{{max-width:960px;margin:0 auto;padding:24px 16px 64px}}
h1{{font-size:28px;margin:8px 0 4px}}h2{{font-size:19px;margin:32px 0 8px}}p{{color:var(--ink2)}}
figure{{margin:16px 0;overflow-x:auto}}figure svg{{max-width:100%;height:auto}}
.scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:13.5px;font-variant-numeric:tabular-nums}}
th,td{{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}}th{{background:var(--head)}}
</style></head><body><main>{"".join(body)}</main></body></html>
"""


def write_reports(results: dict) -> None:
    charts = {
        "overall": chart_overall(results),
        "criteria": chart_criteria(results),
        "strip": chart_strip(results),
        "repeat": chart_repeat(results),
    }
    (REPORTS / "charts").mkdir(parents=True, exist_ok=True)
    for name, svg in charts.items():
        (REPORTS / "charts" / f"{name}.svg").write_text(svg + "\n")
    markdown = _markdown(results)
    (REPORTS / "report.md").write_text(markdown)
    (REPORTS / "report.html").write_text(_html(results, charts, markdown))
