# plain-holdout-tuned-r3

fusion-agent loop, model `gemma4-12b:q8_0`, prompt `cad12`, think=False; tasks: plain_holdout.json.

Passed 24/25; time per task: median 6.7 s, max 129.8 s.

| Task | Result | Status | Model calls | Nudges | Time, s |
|---|---|---|---|---|---|
| P-brick | PASS | answered | 2 | 0 | 5 |
| P-pill | PASS | answered | 2 | 0 | 6 |
| P-plate-corner-holes | PASS | answered | 2 | 0 | 8 |
| P-cup | PASS | answered | 2 | 0 | 6 |
| P-angle-g | PASS | answered | 2 | 0 | 6 |
| P-step | PASS | answered | 3 | 0 | 19 |
| P-cap | PASS | answered | 2 | 0 | 6 |
| P-edit-longer | FAIL | max_calls | 20 | 0 | 130 |
| P-edit-drill-center | PASS | answered | 2 | 0 | 7 |
| P-edit-round-corners | PASS | answered | 2 | 0 | 5 |
| P-button | PASS | answered | 3 | 0 | 13 |
| P-photo-frame | PASS | answered | 2 | 0 | 8 |
| P-cutting-board | PASS | answered | 2 | 0 | 6 |
| P-coin | PASS | answered | 2 | 0 | 6 |
| P-bar-long-hole | PASS | answered | 5 | 0 | 24 |
| P-pencil-case | PASS | answered | 2 | 0 | 6 |
| P-pencil-holder | PASS | answered | 5 | 0 | 26 |
| P-little-table | PASS | answered | 3 | 0 | 22 |
| P-edit-square-window | PASS | answered | 2 | 0 | 7 |
| P-edit-thicker-disk | PASS | answered | 3 | 0 | 6 |
| P-edit-cut-top-edges | PASS | answered | 2 | 0 | 5 |
| P-napkin-ring | PASS | answered | 2 | 0 | 7 |
| P-axle | PASS | answered | 3 | 0 | 5 |
| P-ring-pyramid | PASS | answered | 2 | 0 | 7 |
| P-plug | PASS | answered | 2 | 0 | 8 |

- **P-edit-longer:** body 1: volume 22853.448 instead of 36000.000 mm3; body 1: extents [14.434, 50.0, 80.0] instead of [6.0, 50.0, 120.0] mm
