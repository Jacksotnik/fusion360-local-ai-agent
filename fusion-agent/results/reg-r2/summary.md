# reg-r2

fusion-agent loop, model `gemma4-12b:q8_0`, fast mode; tasks from fusion-ladder: cases.json, cases_holdout2.json.

Passed 22/23; time per task (whole case, like the bench): median 7.4 s, max 27.5 s.

| Task | Result | Status | Model calls | Nudges | Time, s |
|---|---|---|---|---|---|
| L1-cube | PASS | answered | 2 | 0 | 5 |
| L1-cylinder | PASS | answered | 2 | 0 | 6 |
| L1-plate | PASS | answered | 2 | 0 | 5 |
| L2-plate-center-hole | PASS | answered | 2 | 0 | 7 |
| L2-plate-4-holes | PASS | answered | 2 | 0 | 8 |
| L2-bushing | PASS | answered | 2 | 0 | 7 |
| L3-bigger-holes | PASS | answered | 2 | 0 | 5 |
| L3-round-corners | PASS | answered | 2 | 0 | 6 |
| L3-chamfer | PASS | answered | 2 | 0 | 6 |
| L4-flange | PASS | answered | 2 | 0 | 14 |
| L4-revolve-knob | PASS | answered | 2 | 0 | 6 |
| H2-disk-square-hole | PASS | answered | 2 | 0 | 8 |
| H2-block-axial-hole | PASS | answered | 2 | 0 | 8 |
| H2-channel | PASS | answered | 4 | 0 | 13 |
| H2-flanged-bushing | FAIL | answered | 3 | 0 | 18 |
| H2-plate-rounded-holes | PASS | answered | 5 | 0 | 28 |
| H2-cube-chamfer-all | PASS | answered | 2 | 0 | 6 |
| H2-pin-cross-hole | PASS | answered | 2 | 0 | 6 |
| H2-button | PASS | answered | 4 | 0 | 16 |
| H2-edit-axial-hole | PASS | answered | 2 | 0 | 7 |
| H2-edit-shaft-chamfer | PASS | answered | 3 | 0 | 10 |
| H2-edit-longer | PASS | answered | 2 | 0 | 16 |
| H2-square-flange | PASS | answered | 2 | 0 | 10 |

- **H2-flanged-bushing:** body 1: volume 3571.991 instead of 3204.425 mm3; body 1: extents [23.0, 24.0, 24.0] instead of [20.0, 24.0, 24.0] mm
