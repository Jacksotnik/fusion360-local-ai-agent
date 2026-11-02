# plain-holdout3-r1

fusion-agent loop, model `gemma4-12b:q8_0`, prompt `cad12`, think=False; tasks: plain_holdout3.json.

Passed 16/18; time per task: median 7.0 s, max 42.7 s.

| Task | Result | Status | Model calls | Nudges | Time, s |
|---|---|---|---|---|---|
| R-soap-dish | PASS | answered | 2 | 0 | 13 |
| R-washer | PASS | answered | 2 | 0 | 7 |
| R-stick | PASS | answered | 2 | 0 | 6 |
| R-block-blind-hole | PASS | answered | 2 | 0 | 8 |
| R-square-coaster | PASS | answered | 2 | 0 | 6 |
| R-stamp | PASS | answered | 4 | 0 | 20 |
| R-u-holder | FAIL | answered | 4 | 0 | 10 |
| R-bead | PASS | answered | 2 | 0 | 7 |
| R-door-wedge | PASS | answered | 2 | 0 | 9 |
| R-plate-slot | PASS | answered | 6 | 0 | 40 |
| R-edit-shorter | FAIL | answered | 3 | 0 | 7 |
| R-edit-taller | PASS | answered | 3 | 0 | 6 |
| R-edit-corner-hole | PASS | answered | 2 | 0 | 6 |
| R-edit-chamfer-top | PASS | answered | 2 | 0 | 5 |
| R-ask-weight | PASS | answered | 1 | 0 | 2 |
| R-ask-hole | PASS | answered | 1 | 0 | 4 |
| R-dumbbell | PASS | answered | 3 | 0 | 43 |
| R-round-frame | PASS | answered | 2 | 0 | 7 |

- **R-u-holder:** body 1: volume 3680.000 instead of 2280.000 mm3
- **R-edit-shorter:** body 1: volume 350000.000 instead of 28000.000 mm3; body 1: extents [50.0, 70.0, 100.0] instead of [8.0, 50.0, 70.0] mm
