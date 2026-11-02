# plain-holdout-base-r2

fusion-agent loop, model `gemma4-12b:q8_0`, prompt `cad12`, think=False; tasks: plain_holdout.json.

Passed 21/25; time per task: median 7.7 s, max 35.4 s.

| Task | Result | Status | Model calls | Nudges | Time, s |
|---|---|---|---|---|---|
| P-brick | PASS | answered | 2 | 0 | 11 |
| P-pill | PASS | answered | 2 | 0 | 6 |
| P-plate-corner-holes | PASS | answered | 2 | 0 | 8 |
| P-cup | FAIL | answered | 3 | 0 | 18 |
| P-angle-g | PASS | answered | 3 | 1 | 11 |
| P-step | FAIL | answered | 4 | 0 | 35 |
| P-cap | FAIL | answered | 3 | 0 | 8 |
| P-edit-longer | PASS | answered | 4 | 0 | 32 |
| P-edit-drill-center | PASS | answered | 2 | 0 | 7 |
| P-edit-round-corners | PASS | answered | 2 | 0 | 6 |
| P-button | PASS | answered | 2 | 0 | 8 |
| P-photo-frame | PASS | answered | 2 | 0 | 8 |
| P-cutting-board | PASS | answered | 2 | 0 | 5 |
| P-coin | PASS | answered | 3 | 0 | 10 |
| P-bar-long-hole | PASS | answered | 2 | 0 | 8 |
| P-pencil-case | PASS | answered | 2 | 0 | 6 |
| P-pencil-holder | PASS | answered | 6 | 0 | 32 |
| P-little-table | PASS | answered | 3 | 0 | 23 |
| P-edit-square-window | PASS | answered | 2 | 0 | 6 |
| P-edit-thicker-disk | PASS | answered | 2 | 0 | 5 |
| P-edit-cut-top-edges | PASS | answered | 2 | 0 | 6 |
| P-napkin-ring | PASS | answered | 2 | 0 | 7 |
| P-axle | PASS | answered | 2 | 0 | 5 |
| P-ring-pyramid | PASS | answered | 2 | 0 | 6 |
| P-plug | FAIL | answered | 2 | 0 | 7 |

- **P-cup:** body 1: volume 5133.362 instead of 21419.379 mm3; body 1: extents [6.0, 50.0, 50.0] instead of [50.0, 50.0, 60.0] mm
- **P-step:** body 1: extents [40.0, 40.0, 90.0] instead of [40.0, 40.0, 60.0] mm
- **P-cap:** body 1: volume 5301.438 instead of 2201.864 mm3; body 1: cylinder diameters [15.0, 30.0] instead of [27.0, 30.0] mm
- **P-plug:** body 1: volume 2500.708 instead of 5921.902 mm3; body 1: extents [4.0, 30.0, 30.0] instead of [13.0, 30.0, 30.0] mm
