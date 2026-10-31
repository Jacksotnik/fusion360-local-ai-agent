# plain-holdout-r1

fusion-agent loop, model `gemma4-12b:q8_0`, prompt `cad12`, think=False; tasks: plain_holdout.json.

Passed 23/25; time per task: median 7.7 s, max 48.9 s.

| Task | Result | Status | Model calls | Nudges | Time, s |
|---|---|---|---|---|---|
| P-brick | PASS | answered | 2 | 0 | 5 |
| P-pill | PASS | answered | 2 | 0 | 6 |
| P-plate-corner-holes | PASS | answered | 2 | 0 | 8 |
| P-cup | PASS | answered | 4 | 0 | 32 |
| P-angle-g | PASS | answered | 2 | 0 | 6 |
| P-step | PASS | answered | 4 | 0 | 49 |
| P-cap | PASS | answered | 2 | 0 | 7 |
| P-edit-longer | PASS | answered | 4 | 0 | 14 |
| P-edit-drill-center | PASS | answered | 3 | 0 | 8 |
| P-edit-round-corners | PASS | answered | 2 | 0 | 5 |
| P-button | PASS | answered | 2 | 0 | 8 |
| P-photo-frame | PASS | answered | 2 | 0 | 8 |
| P-cutting-board | PASS | answered | 2 | 0 | 6 |
| P-coin | PASS | answered | 2 | 0 | 6 |
| P-bar-long-hole | PASS | answered | 2 | 0 | 8 |
| P-pencil-case | PASS | answered | 2 | 0 | 6 |
| P-pencil-holder | PASS | answered | 2 | 0 | 8 |
| P-little-table | PASS | answered | 4 | 0 | 32 |
| P-edit-square-window | PASS | answered | 3 | 0 | 8 |
| P-edit-thicker-disk | PASS | answered | 4 | 0 | 9 |
| P-edit-cut-top-edges | PASS | answered | 2 | 0 | 5 |
| P-napkin-ring | PASS | answered | 2 | 0 | 7 |
| P-axle | PASS | answered | 3 | 0 | 5 |
| P-ring-pyramid | FAIL | answered | 2 | 0 | 7 |
| P-plug | FAIL | answered | 2 | 0 | 8 |

- **P-ring-pyramid:** body 1: volume 4398.230 instead of 43982.297 mm3; body 1: extents [3.0, 60.0, 60.0] instead of [30.0, 60.0, 60.0] mm
- **P-plug:** body 1: volume 2500.708 instead of 5921.902 mm3; body 1: extents [4.0, 30.0, 30.0] instead of [13.0, 30.0, 30.0] mm
