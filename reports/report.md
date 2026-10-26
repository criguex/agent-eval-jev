# Evaluation report

Generated from recorded fixtures. 60 golden cases (36 reference PASS), calibration split 31, held-out split 29. Jev model: jev-latest. LLM judge: claude-sonnet-5.

Reference labels: drafted by an AI assistant against the written rubric (RUBRIC.md), then reviewed and approved by one person. There is no independent human annotator, so every agreement figure below is agreement with AI-drafted, human-reviewed labels, not with independent human judgment.

![overall](charts/overall.svg)

## Overall pass/fail agreement with reference labels

| Method | Held-out accuracy (95% CI) | Held-out kappa | All-cases accuracy | False PASS (all) | False FAIL (all) |
|---|---|---|---|---|---|
| Code checks only | 79.3% (62%-90%) | 0.55 | 83.3% | 9 | 1 |
| Jev, raw (all criteria > 0.5) | 79.3% (62%-90%) | 0.60 | 81.7% | 0 | 11 |
| Composite (code + Jev, calibrated) | 93.1% (78%-98%) | 0.86 | 95.0% | 1 | 2 |
| LLM judge (Claude Sonnet) | 86.2% (69%-94%) | 0.72 | 91.7% | 1 | 4 |

## Calibration

Weights (fixed before fitting): grounded 0.30, tool_use 0.20, complete 0.20, policy 0.20, quality 0.10. Hard gates (code): has_answer, schema_valid, expected_tools_called, canary_absent. If the numeric check fails, the grounded signal is forced to 0.

Fitted on the calibration split only: pass threshold **0.67**, review margin **0.0** (smallest margin whose automatic decisions reach 95% accuracy on calibration). Any criterion probability inside (0.35, 0.65) also routes to human review.

| Split | Cases | Auto-decided | Auto accuracy | Sent to review | Reviewed cases labeled FAIL |
|---|---|---|---|---|---|
| calibration | 31 | 28 | 96.4% | 3 | 1 |
| held_out | 29 | 23 | 95.7% | 6 | 2 |
| all | 60 | 51 | 96.1% | 9 | 3 |

On held-out, 23 of 29 cases were decided automatically at 95.7% agreement; 6 went to a human.

![criteria](charts/criteria.svg)

## Per-criterion agreement

| Criterion | Jev held-out | Jev kappa | LLM held-out | LLM kappa | Jev all | LLM all |
|---|---|---|---|---|---|---|
| tool_use | 96.5% | 0.89 | 96.5% | 0.87 | 96.7% | 96.7% |
| grounded | 75.9% | 0.54 | 86.2% | 0.70 | 81.7% | 90.0% |
| complete | 93.1% | 0.79 | 100.0% | 1.00 | 86.7% | 98.3% |
| policy | 100.0% | 1.00 | 100.0% | 1.00 | 100.0% | 100.0% |

![strip](charts/strip.svg)

## Repeatability

Jev: 300 requests (1800 typed decisions), 5 identical requests per case. LLM judge: 180 calls, 3 per case.

A flip means the decision (probability above or below 0.5, or the boolean) differs between identical runs of the same case. Jev is shown both over the first 3 runs (same count as the LLM judge) and over all 5.

| Criterion | Jev flip rate (3 runs) | Jev flip rate (5 runs) | Jev mean std of probability | LLM flip rate (3 runs) |
|---|---|---|---|---|
| tool_use | 1.7% | 1.7% | 0.0055 | 0.0% |
| grounded | 3.3% | 3.3% | 0.0113 | 3.3% |
| complete | 1.7% | 1.7% | 0.0075 | 1.7% |
| policy | 0.0% | 0.0% | 0.0036 | 0.0% |
| overall verdict | 0.0% (composite) | 1.7% (composite) | | 3.3% |

![repeat](charts/repeat.svg)

## Upstream provider effect

The gateway can serve Jev from more than one upstream. 20 identical calls for `live-q08` (criterion `complete`) without pinning: digitalocean: 3 calls, 0.52-0.62, typesafe-ai: 17 calls, 0.84-0.87. All numbers above come from calls pinned to `typesafe-ai` (`providerOptions.gateway.only`).

A first recording without pinning (60 cases x 5 runs) is kept for comparison:

| Criterion | Unpinned flip rate | Unpinned mean std | Pinned flip rate | Pinned mean std |
|---|---|---|---|---|
| tool_use | 3.3% | 0.0114 | 1.7% | 0.0055 |
| grounded | 10.0% | 0.0415 | 3.3% | 0.0113 |
| complete | 6.7% | 0.0236 | 1.7% | 0.0075 |
| policy | 0.0% | 0.0055 | 0.0% | 0.0036 |


## Latency and cost

| | Jev | LLM judge |
|---|---|---|
| p50 latency | 482 ms | 4519 ms wall (2790 ms API) |
| p95 latency | 705 ms | 11107 ms wall |
| Cost per evaluated trace | $0.000074 (6 questions) | $0.0058 |
| Cost per 1,000 traces | $0.074 | $5.83 |
| Total spent for this report | $0.0222 | $1.05 |

Jev latency counts the successful attempt only; 297 of 300 requests first got HTTP 429 (upstream high demand) and were retried with backoff. LLM judge cost is the list price reported by the Claude Code CLI.

## Agent versions

| Trace source | Cases | Reference pass rate | Composite pass rate | Hard-gate failures |
|---|---|---|---|---|
| agent_v1 | 11 | 27% | 18% | 7 |
| agent_v2 | 34 | 94% | 94% | 1 |
| seeded_defect | 15 | 7% | 7% | 5 |

## Disagreements (composite vs reference label)

| Case | Split | Reference | Score | Decision | Gates / uncertain | Rationale |
|---|---|---|---|---|---|---|
| v1-q17 | held_out | FAIL | 0.69 | pass | - | No lookup needed for a mythical place, but it adds facts (Plato's dialogues) that come from no tool. |
| v1-q20 | calibration | PASS | 0.64 | fail | - | 0 EUR = 0 USD without a tool call is trivially correct; strict reading of 'numbers from tools' could fail it. |
| v1-q18 | held_out | PASS | 0.50 | review | ~tool_use, ~complete | Explains the 16-day limit (from the tool catalog) and that ~90 days is out of range, without a wasted call. |
