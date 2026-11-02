# plain-holdout3-r2

fusion-agent loop, model `gemma4-12b:q8_0`, prompt `cad12`, think=False; tasks: plain_holdout3.json.

Passed 15/18; time per task: median 6.8 s, max 46.6 s.

| Task | Result | Status | Model calls | Nudges | Time, s |
|---|---|---|---|---|---|
| R-soap-dish | PASS | answered | 2 | 0 | 6 |
| R-washer | PASS | answered | 2 | 0 | 7 |
| R-stick | PASS | answered | 2 | 0 | 6 |
| R-block-blind-hole | PASS | answered | 2 | 0 | 8 |
| R-square-coaster | PASS | answered | 2 | 0 | 6 |
| R-stamp | PASS | answered | 3 | 0 | 22 |
| R-u-holder | FAIL | answered | 5 | 0 | 47 |
| R-bead | PASS | answered | 2 | 0 | 7 |
| R-door-wedge | PASS | answered | 2 | 0 | 7 |
| R-plate-slot | FAIL | answered | 6 | 0 | 46 |
| R-edit-shorter | FAIL | answered | 3 | 0 | 6 |
| R-edit-taller | PASS | answered | 3 | 0 | 6 |
| R-edit-corner-hole | PASS | answered | 2 | 0 | 6 |
| R-edit-chamfer-top | PASS | answered | 2 | 0 | 5 |
| R-ask-weight | PASS | answered | 1 | 0 | 2 |
| R-ask-hole | PASS | answered | 1 | 0 | 2 |
| R-dumbbell | PASS | answered | 5 | 0 | 38 |
| R-round-frame | PASS | answered | 3 | 0 | 8 |

- **R-u-holder:** body 1: volume 5250.000 instead of 2280.000 mm3
- **R-plate-slot:** body 1: volume 11600.000 instead of 11685.841 mm3; body 1: cylinder diameters [] instead of [10.0] mm
- **R-edit-shorter:** body 1: volume 350000.000 instead of 28000.000 mm3; body 1: extents [50.0, 70.0, 100.0] instead of [8.0, 50.0, 70.0] mm
