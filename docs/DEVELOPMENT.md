# Development

How the tool is built, how a change is measured, and what Fusion's MCP does that is not obvious.
The user-facing overview is the [README](../README.md).

## Layout

| Path | What |
|---|---|
| `fusion_agent/agent.py` | the agent loop: one request in, tool calls until a final answer |
| `fusion_agent/cad_api.py` | the CAD helper API the model writes its scripts against (`box`, `cylinder`, `outline`, `thread`, `check`, ...) |
| `fusion_agent/prompts/cad12.md` | the system prompt: the helper API and how to use it |
| `fusion_agent/fusion_mcp.py` | the client of Fusion's MCP server, with `OUTPUT_GUARD` |
| `fusion_agent/repl.py`, `cli.py`, `doctor.py` | the terminal app, its commands and the start-up checks |
| `cases/` | task sets with references (`tools/run_cases.py`) |
| `bench/` | the 23 graded tasks of the original bench (`tools/ladder_regression.py`) |
| `tools/` | runners, the Gallery scan and task generator |
| `tests/` | unit tests (no Fusion needed) |

## The agent loop

Every request goes to the model with the current state of the design attached (the output of
`describe()`), so the model does not spend a call on it. The model answers with `fusion_script` calls;
each script runs in Fusion and its output (or a short error with the model's own line number) goes back.
The loop also:

- nudges (up to twice) when the model says it is done but the geometry did not change (not for a question);
- detects a script repeated with the same result and says so, stops after five repeats;
- caps the reply length and gives a turn 300 seconds before asking for a final answer;
- marks an answer whose last `check()` failed, so the user sees the part may not match.

The user's text is never changed; only the copy sent to the model gets additions:

- sizes in centimeters also in mm (`10 by 4 cm (100 by 40 mm)`, `4 и 3 см (40 и 30 мм)`);
- the helper of a round part's everyday name (`disc [cylinder()]`, `кружок [cylinder()]`);
- for parts with named dimensions, the dimension an edit verb means (`wider [width]`, `расширь [width]`).

**English and Russian are supported at the same level.** Every word list, hint or loop text that
understands one language has its counterpart in the other; a one-language rule is a bug. The model
answers in the language of the request.

## The helpers

- `rect()` and `circle()` put dimensions on what they draw ("length, along X", "width, along Y",
  "diameter"), so every size of a part the app built can be changed with `set_parameter()`, and the
  model picks a dimension by its name. Name-based dimensions worked where prompt rules about length
  versus width did not.
- `check(size=, diameters=, volume=, bodies=, operations=)` compares the part with what the model
  expects and explains a mismatch from the geometry (leftover bodies of an earlier attempt, a join that
  adds nothing, nominal sizes of gears, threads and hexagons, the volume each step added).
- A helper or a hint is added only when a measured failure asks for it, and it is general: a failure is
  closed with something every similar part benefits from, never with a patch for one part. After three
  fixes of one symptom without result, move the meaning into the tool (a helper, a name in `describe()`,
  a hint computed in `check()`) instead of adding prompt rules.

## Fusion MCP quirks

- `setAllExtent(Symmetric)` cuts only one way: a through cut uses two `ThroughAllExtentDefinition` sides.
- A through-all cut into a side with no body fails.
- A failed MCP script is rolled back completely.
- A new feature can invalidate a BRepFace found before it: read what you need from the face before
  `threads.add()`; reading it after raises a bare `InternalValidationError: pFace`.
- After moving a sketch circle, `design.computeAll()` is needed.
- The MCP loses all `print` output after a few hundred runs: every script starts with `OUTPUT_GUARD`
  (`fusion_agent/fusion_mcp.py`). Never send a script without it.

The app works only in the design it marked with the attribute `fusion-agent/session`, never saves a
document and closes only documents it created itself. Two Fusion runners at the same time (the app,
the self-test, the regression scripts) switch the active document under each other: run one at a time.

## Task sets

A task has a prompt, an optional start script, a reference script and a hand-computed volume (or a size
when there is no hand formula); a task passes when the model's part matches the reference in volume,
size, round faces and body count.

- **Honest sets** (`*_holdout*.json`) are never tuned on: record their numbers before looking at the
  failures. For the next honest measurement, write a new set.
- **Dev sets** (`plain_dev`, `revolve_dev`, `parts_dev`, `edits_dev`, `steps_dev`, ...) may be tuned on;
  a failure seen on an honest set is reproduced on a dev set first, then fixed and measured there.
- English copies with the same ids and references (`*_en.json`) exist for `plain_dev`, `revolve_dev`,
  `parts_dev`, `edits_dev`, `steps_dev`, `plain_holdout8` and the Gallery sets.
- `cases/expected_signatures.json` caches the references; delete it after a change to `cad_api.py` and
  run `tools/run_cases.py <sets> --check-references`.

**Fusion 360 Gallery sets** are not stored in the repository (neither the pictures nor the tasks): they
are rebuilt from the reconstruction data on Hugging Face (`harrisonxliang/Fusion360Dataset`) through the
datasets-server API, without downloading the parquet files:

```
python -X utf8 tools/gallery_scan.py test scanned.json [--ids ids.txt]
python -X utf8 tools/gallery_cases.py scanned.json cases/gallery_holdout.json [--language en]
```

`--ids` rebuilds a set measured before exactly (the ids are the case file names of its results folder).
Run `gallery_cases.py` right after the scan: the picture URLs expire. Their references are cached in the
git-ignored `cases/expected_signatures_local.json`.

## Validating a change

After changing `cad_api.py`, the prompt or the loop:

```
python -m unittest discover -s tests
fusion-agent --selftest
python tools/ladder_regression.py cases.json cases_holdout2.json --tag <name>
```

and the dev set of the feature (`python tools/run_cases.py cases/<set>.json --tag <name>`, `--model` for
another model, `--cases` for a few ids). The model is random (temperature 1): compare 2-3 runs before
calling a difference real. Results go to `results/<tag>/` (one JSON per task with the whole
conversation, and `summary.md`).

## Models

The app works with any Ollama model that can call tools and see pictures; it never downloads or installs
models. The prompt and the helpers were tuned on Gemma 4 12B: after a change, measure on it first, then
on the others. The sampler is the model's own (its Modelfile); change it only on a measured gain.
