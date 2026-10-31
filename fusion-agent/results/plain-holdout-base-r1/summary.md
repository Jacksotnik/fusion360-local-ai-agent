# plain-holdout-base-r1

fusion-agent loop, model `gemma4-12b:q8_0`, prompt `cad12`, think=False; tasks: plain_holdout.json.

Passed 20/25; time per task: median 36.5 s, max 253.8 s.

| Task | Result | Status | Model calls | Nudges | Time, s |
|---|---|---|---|---|---|
| P-brick | PASS | answered | 2 | 0 | 17 |
| P-pill | PASS | answered | 2 | 0 | 6 |
| P-plate-corner-holes | PASS | answered | 2 | 0 | 8 |
| P-cup | FAIL | answered | 3 | 0 | 10 |
| P-angle-g | PASS | answered | 2 | 0 | 6 |
| P-step | FAIL | answered | 3 | 0 | 30 |
| P-cap | FAIL | answered | 3 | 0 | 9 |
| P-edit-longer | FAIL | answered | 8 | 0 | 254 |
| P-edit-drill-center | PASS | answered | 2 | 0 | 42 |
| P-edit-round-corners | PASS | answered | 2 | 0 | 34 |
| P-button | PASS | answered | 2 | 0 | 55 |
| P-photo-frame | PASS | answered | 2 | 0 | 56 |
| P-cutting-board | PASS | answered | 2 | 0 | 33 |
| P-coin | PASS | answered | 2 | 0 | 36 |
| P-bar-long-hole | PASS | answered | 2 | 0 | 51 |
| P-pencil-case | PASS | answered | 2 | 0 | 39 |
| P-pencil-holder | PASS | answered | 2 | 0 | 56 |
| P-little-table | PASS | answered | 3 | 0 | 164 |
| P-edit-square-window | PASS | answered | 2 | 0 | 40 |
| P-edit-thicker-disk | PASS | answered | 3 | 0 | 32 |
| P-edit-cut-top-edges | PASS | answered | 2 | 0 | 34 |
| P-napkin-ring | PASS | answered | 2 | 0 | 47 |
| P-axle | PASS | answered | 3 | 0 | 30 |
| P-ring-pyramid | PASS | answered | 2 | 0 | 50 |
| P-plug | FAIL | answered | 2 | 0 | 55 |

- **P-cup:** body 1: volume 5133.362 instead of 21419.379 mm3; body 1: extents [6.0, 50.0, 50.0] instead of [50.0, 50.0, 60.0] mm
- **P-step:** body 1: extents [40.0, 40.0, 90.0] instead of [40.0, 40.0, 60.0] mm
- **P-cap:** body 1: volume 5301.438 instead of 2201.864 mm3; body 1: cylinder diameters [15.0, 30.0] instead of [27.0, 30.0] mm
- **P-edit-longer:** body 1: volume 22853.448 instead of 36000.000 mm3; body 1: extents [14.434, 50.0, 80.0] instead of [6.0, 50.0, 120.0] mm
- **P-plug:** body 1: volume 2500.708 instead of 5921.902 mm3; body 1: extents [4.0, 30.0, 30.0] instead of [13.0, 30.0, 30.0] mm
