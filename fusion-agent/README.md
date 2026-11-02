# fusion-agent

**A local AI model builds and edits parts in Autodesk Fusion from a plain-language request.**

You type what you want in the terminal, in Russian or English, in everyday words:

```
Сделай пластину 80 на 50 мм толщиной 6 мм с четырьмя отверстиями 6 мм в 10 мм от углов.
Сделай шестерню: модуль 2, 20 зубьев, ширина 10 мм, отверстие 8 мм.
Сделай болт M8 длиной 40 мм с головкой под ключ 13.
Скругли углы радиусом 5.   Сделай пластину толще, 10 мм.   Какая масса детали?
```

The model writes a short script with ready-made CAD functions, the app runs it inside Fusion through
Fusion's built-in MCP server, checks the result against the numbers of your request, and shows you a
screenshot. You can attach a photo of a part and give its sizes in words. Everything runs on your own
computer: no cloud, no account, no data leaves the machine.

The app never saves or closes your Fusion documents. Saving the design is up to you.

## What it is for

- Building parts from words: plates, disks, shafts, bushings, flanges, brackets, boxes, profiles
  (L, U, T, I), bottles and vases (bodies of revolution with rounded shoulders), gears, nuts and bolts,
  threads, springs, tubes along a path, lofts, ribs, holes of every kind (through, blind, counterbored,
  countersunk, angled), slots, pockets, grooves, keyways, splines, fillets, chamfers, shells, patterns,
  engraved text.
- Editing the part you just built or one you opened yourself: "make it thicker", "the hole 12 mm",
  "round the corners", "20 mm longer" — through the model's own parameters, so everything that depends
  on them follows.
- Questions about a design: sizes, mass, material, parameters.
- Building a part from a photo plus its sizes in words.

It is a workshop tool for one person at a terminal, not a replacement for Fusion's UI.

## The model

The app is tuned on and tested with **Gemma 4 12B** (Google, `gemma4-12b:q8_0`, Q8_0 quantization,
13.4 GB, fits entirely on a 16 GB GPU, about 24 tokens/s on a laptop Quadro RTX 5000). Every number
below was measured with it.

Any other Ollama model that can call tools will run (vision is needed for photos and screenshots), but
the prompt and the CAD helpers were shaped around Gemma 4 12B. Two others were tried on the same tool:
Qwen3.5-9B (faster, less precise, and it fakes a result to pass its own check) and Gemma 4 26B-A4B MoE
(the same time per part, less precise). Gemma 4 12B stayed.

The app never downloads or installs models. It checks what is installed and tells you what is missing.

## Requirements

| | |
|---|---|
| OS | Windows 10/11. macOS launchers exist but are untested (see `docs/macos-checklist.md`). |
| Python | 3.10 or newer, on the PATH (`python --version`). |
| Autodesk Fusion | installed and running, with the **Fusion MCP Server** turned on (one checkbox, see below), a design open in the DESIGN workspace. |
| Ollama | installed and running ([ollama.com/download](https://ollama.com/download)). |
| Model | an Ollama model that can call tools; recommended **Gemma 4 12B Q8_0** (`ollama pull` the official GGUF from Hugging Face, e.g. `hf.co/ggml-org/gemma-4-12B-it-GGUF:Q8_0`). |
| GPU | 16 GB of video memory for Gemma 4 12B Q8_0 fully on the GPU (it still works with less, partly on the CPU and slower). |
| Internet | once, for the first start (two Python packages: `prompt_toolkit`, `Pillow`). |

**Turning on the MCP server in Fusion:** your profile name (upper right) > Preferences > General > API >
under "Preferences for Scripting and Programming" tick **Fusion MCP Server** (port 27182) > Apply > OK.

## Start

| | |
|---|---|
| Windows | double-click `fusion-agent.cmd` (or run it in cmd / PowerShell) |
| macOS | double-click `fusion-agent.command`, or `./fusion-agent` in Terminal |

The first start creates a Python environment in `.venv` and installs the two packages; later starts take
a second. The app then checks everything it needs (Python, Ollama, the model, GPU memory, Fusion, its
MCP server, the active design) and prints numbered steps for anything missing; fix it and press Enter.

```
fusion-agent [--model NAME] [--think] [--verbose] [--no-screenshots] [--new]
fusion-agent doctor        # only the startup checks, with a hint for each problem
fusion-agent --selftest    # four quick tasks in new designs, pass/fail with seconds
fusion-agent --version
```

Optional: `pip install .` in this folder gives a global `fusion-agent` command.

## How a session goes

The app works in **one design** and marks it:

- an empty design active in Fusion is taken as it is;
- a design you opened or made yourself is taken after one question (Enter means yes): the app can
  change it or answer questions about it; the steps you made are protected, the model cannot delete them;
- `/new` (or `--new`) opens a new empty design.

Before every request it checks that this design is still the active document and asks what to do if not.

Type requests in plain words; sizes may be in centimeters ("7 см" reaches the model as "7 см (70 мм)").
While the model works you see a spinner with seconds and one grey line per script. After the answer:
a grey line like `8.1 s · 2 model calls · 24 t/s` and, when the design changed, a screenshot.

**Pictures in.** Drag a PNG, JPEG, WebP or AVIF file into the terminal window or type its path, add the
request, press Enter. A copied picture goes in with **Alt+V** or `/paste`.

**Pictures out.** After each change a fitted screenshot is saved in the session folder and drawn in the
terminal where the terminal can show pictures (Windows Terminal 1.22+, iTerm2, WezTerm, Kitty, Ghostty);
elsewhere `/open` opens it.

## Commands

| Command | |
|---|---|
| `/help` | commands and keys |
| `/new` | open a new empty design and work in it |
| `/state` | describe the design: bodies, sizes, round faces, timeline with dimensions |
| `/screenshot [view]` | show the design: `iso-top-right` (default), `front`, `top`, `left`, ... |
| `/image <path>` | attach a picture to the next request |
| `/paste` | attach the picture from the clipboard (also Alt+V) |
| `/model [name]` | list the installed models that can call tools, or switch to one |
| `/think on\|off` | thinking mode: slower (1.5-3 minutes per part), more accurate for parts of many operations |
| `/undo [n]` | undo the last n changes: the design and the conversation |
| `/reset` | new conversation; the design stays |
| `/verbose on\|off` | show the scripts the model runs |
| `/screenshots on\|off` | a screenshot after each change |
| `/open` | open the last screenshot in the system viewer |
| `/doctor` | run the startup checks again |
| `/exit` | quit (also Ctrl+D) |

**Ctrl+C** stops the current answer; a second Ctrl+C quits. Tab completes commands, views, model names
and paths.

## Results

Every task set has a reference part whose volume was computed by hand; a task passes only when the
model's part matches the reference in volume (0.5 %), overall size (0.05 mm), round-face diameters and
body count. The model is random (temperature 1.0), so sets were run several times. Numbers below are from
the final code, Gemma 4 12B, fast mode (no thinking), on a laptop with a 16 GB GPU.

**Sets the tool was never tuned on** (written, run once, numbers recorded before any fix):

| Set | What | Result |
|---|---|---|
| Plain-language requests, 26 tasks | everyday words, cm sizes, plates, disks, bushings, edits, questions | **26/26, 26/26, 26/26, 25/26** |
| Your own models, 11 tasks | parts made in Fusion by hand: edits through parameters, questions about mass and sizes | **11/11** (three runs) |
| Real parts from a picture plus build steps, 51 | a photo and the steps in words with every size | **43/51 before one prompt line about arcs, 47-49/51 after** |
| Real parts from a picture plus build steps, 62 (second set) | same kind, written after the arc fix | **61/62** |
| The exam: a photo of a hub flange plus sizes in words | spline bore, 4 bolt holes, 2 rim cutouts, filleted hub | **PASS in 8 of 9 runs** |
| Bench regression, 23 tasks | the original graded tasks of the project | **23/23** (most runs), 22/23 (a chamfer on both edges of a face instead of the outer one) |

Across the untuned sets on the final code: **173 of 179 tasks, 96.6 %.**

**Sets used for tuning** (their failures drove the helpers; numbers are the last run):

| Set | What | Result |
|---|---|---|
| Machine parts, 12 | splined hub and shaft, rim notches, hub fillet, face recess, keyway, counterbores | 12/12 |
| Bodies of revolution, 5 | a two-cone vase, a sphere, a dome, a barrel, a knob with a rounded top | 5/5 |
| Gears, threads, hexagons, 8 | gears with bore and hub, nut, bolt, threaded shaft and hole, socket-head screw | 8/8 |
| Basics, 11 | bent tube, L-rod, spring, square-to-round loft, frustum, gusset, angled hole, subtracted sphere, copied cube with a bridge, engraved plate, square tube along an arc | 9/11 |

Honest reading of the misses: the model sometimes adds what was not asked (a rounded corner instead
of a chamfer), misreads a width (20 instead of 10), or writes a wrong volume formula into its own check
and then "repairs" a correct part. The tool catches what geometry can catch (wrong direction, a join
that adds nothing, an arc that bulges past its points, a hole outside the part) and tells the model
in one line what is wrong; a request that keeps failing is stopped after 300 seconds or five identical
scripts and the model answers with what it could not do.

Speed: a one-operation part takes 5-10 s, a part of five or six operations 15-65 s. Thinking mode
(`/think on`) is 3-4 times slower and helps on parts of many operations.

Validation tools for developers: `python -m unittest discover -s tests` (no Fusion needed),
`fusion-agent --selftest`, `tools/run_cases.py cases/<set>.json --tag <name>` (runs a set and compares
with the references), `tools/ladder_regression.py` (the bench tasks).

## Known limits

- Parts are built in the root component; sketches lie on the base planes (with offsets) or on a tilted
  plane made by the app. No sheet metal, no assemblies or joints, no free-form surfaces (curves are
  arcs, bodies of revolution, sweeps and lofts).
- The weak spot of a 12B model is spatial placement in parts of many operations (which end, which face).
  The tool's hints fix most of it on the next call; `/think on` helps further at 3-4 times the time.
- Rim cutouts, splines and keyways are straight-sided and along Z; involute splines are not modelled
  (gears are). Threads are ISO metric only.
- A size that no dimension holds in your own model (a sketch drawn without sizes, an imported body) is
  changed by adding or cutting material, not by a parameter.
- `/undo` restores the timeline, dimensions and parameters; a change made outside them is reported, and
  Fusion's own Undo goes further.
- macOS is untested.

## Files

| | Windows | macOS |
|---|---|---|
| settings, input history | `%LOCALAPPDATA%\fusion-agent\` | `~/Library/Application Support/fusion-agent/` |
| session log (requests, scripts, results, timings) and pictures | `...\fusion-agent\sessions\<date-time>\` | `.../fusion-agent/sessions/<date-time>/` |

Environment variables: `OLLAMA_HOST`, `FUSION_MCP_URL`, `FUSION_AGENT_INLINE_IMAGES` (`off`, `sixel`,
`iterm`, `kitty`), `NO_COLOR`.

## Where things come from

The CAD helpers (`fusion_agent/cad_api.py`), the system prompt (`fusion_agent/prompts/cad12.md`) and
the agent loop (`fusion_agent/agent.py`) grew out of the bench in the parent folder (`fusion-ladder`),
where every change was measured on task sets with hand-computed references. This folder is their source
of truth; the plan it was built from is `PLAN.md`.
