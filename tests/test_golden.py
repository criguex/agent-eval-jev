from agenteval.golden import CRITERIA, load_cases, split


def test_golden_set_shape():
    cases = load_cases()
    assert 40 <= len(cases) <= 60
    assert len({c.id for c in cases}) == len(cases)
    for case in cases:
        assert set(case.labels) == set(CRITERIA)
        assert case.passed == all(case.labels.values())
        assert case.rationale
        assert case.trace["final_answer"] is not None


def test_golden_set_covers_every_category():
    categories = {c.category for c in load_cases()}
    assert {
        "happy",
        "multi_tool",
        "edge",
        "out_of_scope",
        "adversarial",
        "indirect_injection",
        "seeded_defect",
    } <= categories


def test_split_is_disjoint_and_stratified():
    cases = load_cases()
    calibration, held_out = split(cases)
    assert not {c.id for c in calibration} & {c.id for c in held_out}
    assert len(calibration) + len(held_out) == len(cases)
    for source in {c.source for c in cases}:
        for passed in (True, False):
            a = sum(c.source == source and c.passed == passed for c in calibration)
            b = sum(c.source == source and c.passed == passed for c in held_out)
            assert abs(a - b) <= 1
