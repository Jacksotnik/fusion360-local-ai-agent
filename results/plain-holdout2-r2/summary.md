# plain-holdout2-r2

fusion-agent loop, model `gemma4-12b:q8_0`, prompt `cad12`, think=False; tasks: plain_holdout2.json.

Passed 19/20; time per task: median 7.4 s, max 71.7 s.

| Task | Result | Status | Model calls | Nudges | Time, s |
|---|---|---|---|---|---|
| Q-domino | PASS | answered | 2 | 0 | 5 |
| Q-dice-side-hole | PASS | answered | 2 | 0 | 7 |
| Q-flowerpot | PASS | answered | 2 | 0 | 6 |
| Q-tray | PASS | answered | 2 | 0 | 6 |
| Q-spacer | PASS | answered | 2 | 0 | 7 |
| Q-wheel | PASS | answered | 2 | 0 | 8 |
| Q-tower | PASS | answered | 2 | 0 | 8 |
| Q-hook-plate | PASS | answered | 2 | 0 | 7 |
| Q-thick-ring | PASS | answered | 3 | 0 | 8 |
| Q-jar-lid | PASS | answered | 2 | 0 | 6 |
| Q-l-bracket | PASS | answered | 2 | 0 | 6 |
| Q-smooth-bar | PASS | answered | 2 | 0 | 7 |
| Q-edit-wider | PASS | answered | 3 | 0 | 38 |
| Q-edit-hole-wider | PASS | answered | 3 | 0 | 8 |
| Q-edit-three-holes | PASS | answered | 4 | 0 | 20 |
| Q-edit-round-top | PASS | answered | 7 | 0 | 72 |
| Q-candle-holder | PASS | answered | 3 | 0 | 17 |
| Q-tag | PASS | answered | 2 | 0 | 7 |
| Q-shelf | FAIL | answered | 7 | 0 | 52 |
| Q-ask-size | PASS | answered | 1 | 0 | 2 |

- **Q-shelf:** body 1: extents [40.0, 110.0, 200.0] instead of [40.0, 100.0, 200.0] mm
