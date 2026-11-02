# plain-holdout-r2

fusion-agent loop, model `gemma4-12b:q8_0`, prompt `cad12`, think=False; tasks: plain_holdout.json.

Passed 22/25; time per task: median 6.8 s, max 148.2 s.

| Task | Result | Status | Model calls | Nudges | Time, s |
|---|---|---|---|---|---|
| P-brick | PASS | answered | 2 | 0 | 5 |
| P-pill | PASS | answered | 2 | 0 | 6 |
| P-plate-corner-holes | PASS | answered | 2 | 0 | 9 |
| P-cup | FAIL | answered | 15 | 0 | 148 |
| P-angle-g | PASS | answered | 2 | 0 | 7 |
| P-step | FAIL | answered | 5 | 0 | 30 |
| P-cap | PASS | answered | 2 | 0 | 6 |
| P-edit-longer | PASS | answered | 4 | 0 | 25 |
| P-edit-drill-center | PASS | answered | 2 | 0 | 7 |
| P-edit-round-corners | PASS | answered | 2 | 0 | 5 |
| P-button | PASS | answered | 2 | 0 | 8 |
| P-photo-frame | PASS | answered | 2 | 0 | 8 |
| P-cutting-board | PASS | answered | 2 | 0 | 6 |
| P-coin | PASS | answered | 2 | 0 | 6 |
| P-bar-long-hole | PASS | answered | 4 | 0 | 19 |
| P-pencil-case | PASS | answered | 2 | 0 | 7 |
| P-pencil-holder | PASS | answered | 2 | 0 | 8 |
| P-little-table | PASS | answered | 4 | 0 | 32 |
| P-edit-square-window | PASS | answered | 2 | 0 | 7 |
| P-edit-thicker-disk | PASS | answered | 2 | 0 | 4 |
| P-edit-cut-top-edges | PASS | answered | 2 | 0 | 5 |
| P-napkin-ring | PASS | answered | 2 | 0 | 7 |
| P-axle | PASS | answered | 2 | 0 | 5 |
| P-ring-pyramid | PASS | answered | 3 | 0 | 17 |
| P-plug | FAIL | answered | 2 | 0 | 8 |

- **P-cup:** body 1: volume 5133.362 instead of 21419.379 mm3; body 1: extents [6.0, 50.0, 50.0] instead of [50.0, 50.0, 60.0] mm
- **P-step:** body 1: extents [40.0, 40.0, 90.0] instead of [40.0, 40.0, 60.0] mm
- **P-plug:** body 1: volume 2500.708 instead of 5921.902 mm3; body 1: extents [4.0, 30.0, 30.0] instead of [13.0, 30.0, 30.0] mm
