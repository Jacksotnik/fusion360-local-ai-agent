# user-holdout-base-r1

fusion-agent loop, model `gemma4-12b:q8_0`, prompt `cad12`, think=False; tasks: user_models_holdout.json.

Passed 9/11; time per task: median 13.2 s, max 21.7 s.

| Task | Result | Status | Model calls | Nudges | Time, s |
|---|---|---|---|---|---|
| V-flange-bigger-bore | PASS | answered | 4 | 0 | 13 |
| V-flange-taller-hub | FAIL | answered | 3 | 0 | 7 |
| V-flange-ask-outer | PASS | answered_unchanged | 5 | 2 | 16 |
| V-flange-ask-hole | PASS | answered_unchanged | 6 | 2 | 15 |
| V-flange-list-parameters | FAIL | answered_unchanged | 4 | 2 | 15 |
| V-block-wider | PASS | answered | 3 | 0 | 7 |
| V-block-bigger-rounding | PASS | answered | 3 | 0 | 8 |
| V-block-drill | PASS | answered | 2 | 0 | 6 |
| V-block-ask-size | PASS | answered_unchanged | 5 | 2 | 9 |
| V-block-ask-rounding | PASS | answered_unchanged | 6 | 2 | 22 |
| V-block-ask-weight | PASS | answered_unchanged | 5 | 2 | 18 |

- **V-flange-taller-hub:** body 1: volume 40658.492 instead of 39527.519 mm3
- **V-flange-list-parameters:** the answer has none of [8, 0.8]; the answer has none of [20, 2]
