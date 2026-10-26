import json
import os
import re
import subprocess

import pytest

from tools.relabel_compare import LABELS, labels_commit, report
from tools.relabel_sample import ROOT, pick, sheet

ALL_PASS = {"tool_use": True, "grounded": True, "complete": True, "policy": True}


def row(code, overall="pass", **criteria):
    base = {k: "pass" for k in ALL_PASS} | criteria
    return {
        "case_id": code,
        **base,
        "overall": overall,
        "confidence": "2",
        "note": "",
        "started_at": "t0",
        "finished_at": "t1",
    }


def test_report_counts_agreement_and_disagreements():
    sample = [{"code": f"c0{i}", "id": f"x{i}"} for i in range(1, 5)]
    golden = {
        "x1": {"labels": ALL_PASS, "pass": True},
        "x2": {"labels": ALL_PASS | {"grounded": False}, "pass": False},
        "x3": {"labels": ALL_PASS, "pass": True},
        "x4": {"labels": ALL_PASS | {"policy": False}, "pass": False},
    }
    rows = {
        "c01": row("c01"),
        "c02": row("c02", "fail", grounded="fail"),
        "c03": row("c03", "fail", complete="fail"),
        "c04": row("c04", "fail", policy="fail"),
    }
    decisions = {"x1": "pass", "x2": "fail", "x3": "pass", "x4": "review"}
    text = report(rows, sample, golden, decisions)
    assert "| grounded | 4/4 (100%) | 1.00 |" in text
    assert "| complete | 3/4 (75%) | 0.00 |" in text
    assert "| overall | 3/4 (75%) | 0.50 |" in text
    assert "| c03 | x3 | complete | fail | pass |" in text
    assert "enviados a revisión: 1 (c04)" in text
    assert "Acuerdo en los decididos: 2/3 (67%)" in text
    assert "| c03 | x3 | fail | pass |" in text


def git(repo, *args):
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def test_labels_must_be_committed_alone_before_results(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "relabel").mkdir()
    labels = tmp_path / LABELS
    labels.write_text("case_id\n")
    (tmp_path / "other.txt").write_text("x")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "plantilla")
    with pytest.raises(SystemExit, match="solo"):
        labels_commit(tmp_path)

    labels.write_text("case_id\nc01\n")
    with pytest.raises(SystemExit, match="sin commitear"):
        labels_commit(tmp_path)

    git(tmp_path, "commit", "-qam", "etiquetas")
    sha, _ = labels_commit(tmp_path)
    assert len(sha) == 40

    (tmp_path / "relabel/RESULTS.md").write_text("r")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "resultados")
    assert labels_commit(tmp_path)[0] == sha
    labels.write_text("case_id\nc02\n")
    git(tmp_path, "commit", "-qam", "retoque")
    with pytest.raises(SystemExit, match="después"):
        labels_commit(tmp_path)


def test_sample_is_fixed_and_sheet_hides_references():
    rows = [json.loads(line) for line in (ROOT / "data/golden.jsonl").read_text().splitlines() if line.strip()]
    ids = [r["id"] for r in rows]
    chosen = pick(ids)
    assert chosen == pick(ids) and len(set(chosen)) == 15
    html = sheet([{"code": f"c{n:02d}", "id": i} for n, i in enumerate(ids, 1)])
    leaks = r"rationale|\"labels\"|ambiguous|human_|decision|[Jj]ev|llm_judge|score|mutation|seeded|expected_tools|canary|Labeled|live-q\d|v1-q\d|mut-m\d"
    assert not re.search(leaks, html)
    assert not [r["id"] for r in rows if r["rationale"] in html]
    assert (ROOT / "relabel/sheet.html").read_text() == sheet(
        json.loads((ROOT / "relabel/sample.json").read_text())["cases"]
    )
