# plain-holdout2-r1

fusion-agent loop, model `gemma4-12b:q8_0`, prompt `cad12`, think=False; tasks: plain_holdout2.json.

Passed 16/20; time per task: median 7.3 s, max 153.4 s.

| Task | Result | Status | Model calls | Nudges | Time, s |
|---|---|---|---|---|---|
| Q-domino | PASS | answered | 2 | 0 | 6 |
| Q-dice-side-hole | PASS | answered | 2 | 0 | 8 |
| Q-flowerpot | PASS | answered | 2 | 0 | 6 |
| Q-tray | PASS | answered | 2 | 0 | 6 |
| Q-spacer | PASS | answered | 2 | 0 | 7 |
| Q-wheel | PASS | answered | 2 | 0 | 7 |
| Q-tower | PASS | answered | 2 | 0 | 8 |
| Q-hook-plate | PASS | answered | 2 | 0 | 7 |
| Q-thick-ring | PASS | answered | 2 | 0 | 7 |
| Q-jar-lid | PASS | answered | 2 | 0 | 6 |
| Q-l-bracket | FAIL | answered | 4 | 0 | 18 |
| Q-smooth-bar | PASS | answered | 2 | 0 | 7 |
| Q-edit-wider | FAIL | answered | 10 | 0 | 127 |
| Q-edit-hole-wider | PASS | answered | 2 | 0 | 6 |
| Q-edit-three-holes | PASS | answered | 3 | 0 | 15 |
| Q-edit-round-top | FAIL | answered | 5 | 0 | 16 |
| Q-candle-holder | PASS | answered | 3 | 0 | 16 |
| Q-tag | PASS | answered | 2 | 0 | 7 |
| Q-shelf | FAIL | answered | 10 | 0 | 153 |
| Q-ask-size | PASS | answered | 1 | 0 | 2 |

- **Q-l-bracket:** body 1: volume 21250.000 instead of 12750.000 mm3; body 1: extents [40.0, 50.0, 50.0] instead of [30.0, 40.0, 50.0] mm
- **Q-edit-wider:** body 1: volume 1813317.746 instead of 48000.000 mm3; body 1: extents [60.0, 247.846, 287.846] instead of [10.0, 60.0, 80.0] mm
- **Q-edit-round-top:** body 1: volume 36874.698 instead of 37286.905 mm3
- **Q-shelf:** body 1: volume 240000.000 instead of 260000.000 mm3; body 1: extents [30.0, 100.0, 200.0] instead of [40.0, 100.0, 200.0] mm
