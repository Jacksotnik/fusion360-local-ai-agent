# user-holdout-final

fusion-agent loop, model `gemma4-12b:q8_0`, prompt `cad12`, think=False; tasks: user_models_holdout.json.

Passed 11/11; time per task: median 5.5 s, max 24.0 s.

| Task | Result | Status | Model calls | Nudges | Time, s |
|---|---|---|---|---|---|
| V-flange-bigger-bore | PASS | answered | 4 | 0 | 24 |
| V-flange-taller-hub | PASS | answered | 3 | 0 | 8 |
| V-flange-ask-outer | PASS | answered | 1 | 0 | 2 |
| V-flange-ask-hole | PASS | answered | 1 | 0 | 2 |
| V-flange-list-parameters | PASS | answered | 1 | 0 | 6 |
| V-block-wider | PASS | answered | 3 | 0 | 6 |
| V-block-bigger-rounding | PASS | answered | 4 | 0 | 9 |
| V-block-drill | PASS | answered | 3 | 0 | 8 |
| V-block-ask-size | PASS | answered | 1 | 0 | 2 |
| V-block-ask-rounding | PASS | answered | 1 | 0 | 2 |
| V-block-ask-weight | PASS | answered | 1 | 0 | 2 |

