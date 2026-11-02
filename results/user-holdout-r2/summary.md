# user-holdout-r2

fusion-agent loop, model `gemma4-12b:q8_0`, prompt `cad12`, think=False; tasks: user_models_holdout.json.

Passed 11/11; time per task: median 5.2 s, max 24.2 s.

| Task | Result | Status | Model calls | Nudges | Time, s |
|---|---|---|---|---|---|
| V-flange-bigger-bore | PASS | answered | 4 | 0 | 24 |
| V-flange-taller-hub | PASS | answered | 3 | 0 | 9 |
| V-flange-ask-outer | PASS | answered | 1 | 0 | 2 |
| V-flange-ask-hole | PASS | answered | 1 | 0 | 2 |
| V-flange-list-parameters | PASS | answered | 1 | 0 | 5 |
| V-block-wider | PASS | answered | 3 | 0 | 7 |
| V-block-bigger-rounding | PASS | answered | 4 | 0 | 9 |
| V-block-drill | PASS | answered | 2 | 0 | 6 |
| V-block-ask-size | PASS | answered | 1 | 0 | 2 |
| V-block-ask-rounding | PASS | answered | 1 | 0 | 2 |
| V-block-ask-weight | PASS | answered | 1 | 0 | 2 |

