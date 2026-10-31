# user-holdout-r1

fusion-agent loop, model `gemma4-12b:q8_0`, prompt `cad12`, think=False; tasks: user_models_holdout.json.

Passed 11/11; time per task: median 5.2 s, max 60.7 s.

| Task | Result | Status | Model calls | Nudges | Time, s |
|---|---|---|---|---|---|
| V-flange-bigger-bore | PASS | answered | 3 | 0 | 16 |
| V-flange-taller-hub | PASS | answered | 4 | 0 | 13 |
| V-flange-ask-outer | PASS | answered | 1 | 0 | 3 |
| V-flange-ask-hole | PASS | answered | 1 | 0 | 2 |
| V-flange-list-parameters | PASS | answered | 1 | 0 | 5 |
| V-block-wider | PASS | answered | 3 | 0 | 7 |
| V-block-bigger-rounding | PASS | answered | 5 | 0 | 61 |
| V-block-drill | PASS | answered | 2 | 0 | 7 |
| V-block-ask-size | PASS | answered | 1 | 0 | 2 |
| V-block-ask-rounding | PASS | answered | 1 | 0 | 2 |
| V-block-ask-weight | PASS | answered | 1 | 0 | 2 |

