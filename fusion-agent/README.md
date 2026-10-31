# fusion-agent

A terminal bridge between a local model and Autodesk Fusion. You type a request ("make a plate 80 by 50,
6 mm thick, with four 6 mm holes 10 mm from the corners"), attach a picture if you have one, and the
model builds or edits the part in Fusion through Fusion's built-in MCP server. No UI except the
terminal. Windows and macOS (macOS is untested yet, see below).

The app works with **any Ollama model that can call tools**; it needs vision for pictures and
screenshots. It never downloads or installs models: it checks what is there and says what is missing.
Recommended: **Gemma 4 12B** — the system prompt and the CAD helpers were tuned and measured on it
(`gemma4-12b:q8_0`, Q8_0, fully on a 16 GB GPU).

## Requirements

- Windows 10/11 or macOS, Python 3.10 or newer.
- [Ollama](https://ollama.com/download), running, with a model that can call tools.
- Autodesk Fusion, running, with its MCP server turned on (see [Troubleshooting](#troubleshooting)).

## Run

| | |
|---|---|
| Windows | double-click `fusion-agent.cmd`, or run `fusion-agent.cmd` in cmd or PowerShell |
| macOS | double-click `fusion-agent.command` in Finder, or run `./fusion-agent` in Terminal |

The first run creates a Python environment in `.venv` and installs `prompt_toolkit` and `Pillow`
(needs the internet once); later runs start at once. Arguments are passed through, e.g.
`fusion-agent.cmd --new --verbose`.

Optional: `pipx install .` (or `pip install .`) in this folder gives a global `fusion-agent` command.

```
fusion-agent [--model NAME] [--think] [--verbose] [--no-screenshots] [--new]
fusion-agent doctor        # only the startup checks, with a hint for each problem
fusion-agent --selftest    # four quick tasks in new designs, pass/fail with seconds
fusion-agent --version
```

## How a session goes

At start the app checks Python, Ollama, the model, GPU memory, Fusion, its MCP server, a test script
and the active document. Each problem gets short numbered steps; fix them and press Enter to check
again. If the chosen model is missing but usable ones are installed, the app lists them to pick one.

The app works in **one design** and marks it (design attribute `fusion-agent/session`):

- an empty design that is active in Fusion is taken as it is;
- a design you opened or made yourself is taken after one question (Enter means yes): the app can
  change it or answer questions about it;
- `/new` (or `--new`) opens a new empty design.

Before every request it checks that this design is still the active document; if not, it asks: back
to the session design, work with the design that is active now, a new design, or skip. It never saves
or closes a document, and it refuses model scripts that reach for documents. Saving the design is up
to you.

**Your own models.** Open a part in Fusion, start the app and ask, in plain words:

- questions: "Какая толщина у пластины?", "Сколько она весит?", "Перечисли параметры модели",
  "Из чего она сделана?" The model answers from the design state (bodies, sizes, user parameters, the
  dimensions of every sketch and feature, material and mass) and does not change the design;
- changes: "Сделай пластину толще — 10 мм", "Отверстие сделай побольше, 12 мм", "Скругли углы на 5 мм".
  Sizes are changed through the model's own parameters (a user parameter when the dimension uses one,
  so everything that depends on it follows); holes, fillets and chamfers are added on top.

The steps you made yourself are protected: the model cannot delete them (`clear()` refuses, `undo()`
stops at them), and `/undo` takes back only what the app changed, parameter values included.

Type requests in any language and in plain words ("пластинка", "дырочка", "полсантиметра", "сними
острые края"); sizes can be in centimeters (the app adds the mm value for the model: "7 см (70 мм)").
The model answers in the language of the question (the prompt's examples are Russian, and so were the
measured requests). While the model works you see a spinner with
seconds and one grey line per script it runs (`/verbose on` shows the scripts themselves). After the
answer comes a grey line like `8.1 s · 2 model calls · 24 t/s · context 5.1k/32k`, and, when the design
changed, a screenshot.

## Commands

| Command | |
|---|---|
| `/help` | commands and keys |
| `/new` | open a new empty design in Fusion and work in it |
| `/state` | describe the design: bodies, sizes, round faces, timeline with dimensions |
| `/screenshot [view]` | show the design: `iso-top-right` (default), `front`, `top`, `left`, ... |
| `/image <path>` | attach a picture to the next request |
| `/paste` | attach the picture from the clipboard (also Alt+V) |
| `/model [name]` | list the installed models that can call tools, or switch to one |
| `/think on\|off` | thinking mode: slower (1.5-3 minutes per part), more accurate for parts of many operations |
| `/undo [n]` | undo the last n changes: the design (timeline, changed dimensions and parameters) and the conversation; questions are skipped |
| `/reset` | new conversation; the design stays |
| `/verbose on\|off` | show the scripts the model runs |
| `/screenshots on\|off` | a screenshot after each change |
| `/open` | open the last screenshot in the system viewer |
| `/doctor` | run the startup checks again |
| `/exit` | quit (also Ctrl+D) |

Keys: **Ctrl+C** stops the current answer (the conversation goes back to before the request; the design
keeps what finished scripts changed, `/undo` removes it); a second Ctrl+C quits. Ctrl+C on an empty line
or Ctrl+D quits. Tab completes commands, views, model names and the path after `/image`.

`/think`, `/verbose`, `/screenshots` and the model chosen with `/model` are remembered; command-line
flags apply to one run.

## Pictures

**In.** Drag a PNG, JPEG or WebP file (up to 10 MB) into the terminal window or type its path: it turns
into a label like `[Image: part.png]`; add the request and press Enter. Quoted Windows paths
(`"C:\a b\x.png"`), escaped macOS paths (`/Users/a\ b/x.png`) and `file://` links work. A copied picture
goes in with **Alt+V** or `/paste`; on macOS also **Ctrl+V** (Cmd+V pastes text only). In Windows Terminal
Ctrl+V is the terminal's own paste and cannot see pictures: use Alt+V. Pictures are downscaled to 1024 px
on the long side. A paste longer than three lines shows as `[Pasted text #1, 12 lines]` and is sent whole.

**Out.** After a request that changed the design the app takes a fitted iso screenshot, saves it in the
session folder and draws it in the terminal where it can: Windows Terminal 1.22+ (Sixel), iTerm2 and
WezTerm, Kitty and Ghostty. Elsewhere (the classic Windows console, macOS Terminal) it prints the path;
`/open` opens it. `FUSION_AGENT_INLINE_IMAGES=off` turns inline pictures off.

## Model choice

`/model` lists the installed models that can call tools, with their size and whether they have vision
and thinking, and marks the one the prompt was tuned on. Any of them can be used; a model without vision
works without pictures and screenshots. The app gives the model the same tools and limits as the
measured setup: num_ctx 32768, replies capped at 1200 tokens (4000 with thinking), up to 20 model calls
per request, the design state attached to every request.

## Troubleshooting

| Startup line | What to do |
|---|---|
| ✖ Ollama does not answer | Start Ollama (Windows: Start menu, it runs in the tray; macOS: the Ollama app), or `ollama serve`. Another address: set `OLLAMA_HOST`. |
| ✖ Model ... is not installed / cannot call tools | Pick one of the installed models the app lists (or `--model <name>`). If none can call tools, install such a model in Ollama yourself; Gemma 4 12B is recommended. |
| ! Memory | The model does not fit in free GPU memory (Windows: `nvidia-smi`; macOS: unified memory). It still works, partly on the CPU and slower. Close other GPU programs or pick a smaller model. |
| ✖ Fusion is not running | Start Autodesk Fusion and wait until it has fully opened. |
| ✖ Fusion MCP does not answer | In Fusion: your profile name (upper right) > Preferences > General > API > under "Preferences for Scripting and Programming" tick **Fusion MCP Server**, port 27182 > Apply > OK (Autodesk help: "Connecting to the Fusion MCP server"). Another address: set `FUSION_MCP_URL`. |
| ✖ Script run: output was lost | Fusion's MCP lost script output; restart Fusion. (The app guards against the known cause on every script.) |
| ! Design: no document / not a design / not in the Design workspace / direct modeling | Open a new design (File > New Design), switch to the DESIGN workspace, or type `/new`. The app needs a parametric design with a timeline. |
| ✔ Design: "X" has N bodies | The app asks once and then works with it (changes or questions); `/new` gives a clean design. |

Windows: if Russian text shows as question marks, use Windows Terminal (the launcher sets UTF-8).

## Files

| | Windows | macOS |
|---|---|---|
| settings, input history | `%LOCALAPPDATA%\fusion-agent\` | `~/Library/Application Support/fusion-agent/` |
| session log (JSONL: requests, scripts, results, timings) and pictures | `...\fusion-agent\sessions\<date-time>\` | `.../fusion-agent/sessions/<date-time>/` |

Environment variables: `OLLAMA_HOST`, `FUSION_MCP_URL`, `FUSION_AGENT_INLINE_IMAGES` (`off`, `sixel`,
`iterm`, `kitty`), `NO_COLOR`.

## Validation

- Unit tests (no Fusion needed): `.venv\Scripts\python -m unittest discover -s tests`.
- `fusion-agent --selftest`: a plate with holes, the edit "make it thicker", the question "how thick is
  it now" (the design must stay as it is) and a stepped shaft through the real loop, checked against
  hand-computed volumes. On the Windows laptop: 4/4 in 21 s.
- Task sets of this app (`cases/`, runner `tools/run_cases.py`, every reference checked against a
  hand-computed volume): requests in plain words (`plain_dev.json`, 25, and `plain_holdout.json`, 25)
  and the user's own models (`user_models_dev.json`, 12, and `user_models_holdout.json`, 11: plates,
  a bracket in a component, a flange held by user parameters, a filleted block; changes and questions
  about parameters, size, mass and material). The holdout sets are honest: nothing was tuned on them
  before their first numbers were written down. With `gemma4-12b:q8_0`, fast mode, 2026-10-31:

  | Set | Before (v0.1.0) | After, honest (first runs) | After tuning on it |
  |---|---|---|---|
  | plain words, `plain_holdout` (25) | 20/25, 21/25 | 23/25, 22/25 | 25/25, 25/25, 24/25 |
  | plain words, `plain_holdout2` (20) | | 16/20, 19/20 | |
  | plain words, `plain_holdout3` (18), final configuration | | 16/18, 15/18 | |
  | your own models, `user_models_holdout` (11) | 9/11 | 11/11, 11/11, 11/11 | |
  | plain words, `plain_dev` (25) | | | 25/25, 25/25 |
  | your own models, `user_models_dev` (12) | | | 12/12 (four runs) |

  Each tuning round fixed what the previous honest set showed (sizes in centimeters copied as mm, a
  wall thickness counted once instead of on each side, a fillet of a round edge listed as a diameter);
  the newest honest set, written before the final configuration ran, gives about 86 %. Its misses:
  "make it shorter" on a plate the app built (the model changes the thickness dimension), the argument
  order of a П-shaped strip, a rounded slot made rectangular. Questions are answered in 2-5 s.
  Summaries: `results/plain-*/`, `results/user-*/`.
- No regression against the bench: `tools/ladder_regression.py` runs fusion-ladder's graded tasks
  (`cases.json`, 11, and `cases_holdout2.json`, 12) through this package's loop and compares with the
  bench's reference geometry. With `gemma4-12b:q8_0`, fast mode, 2026-10-31: **23/23 and 22/23, median
  7.4 s per task** (the bench itself: 23/23, median 9-10 s). The one failure was the model reading "total
  length 20" of a flanged bushing as 20 + 3 mm. Summaries: `results/reg-r1/`, `results/reg-r2/`. With the
  changes for plain words and your own models: **23/23, median 7.4 s** (`results/reg-r9/`).
- The REPL was driven in a Windows pseudo-console (ConPTY, the layer Windows Terminal uses): startup
  hints, a non-empty design, a switched or closed session design, pictures by path, paste and Alt+V,
  model switching, Ctrl+C during an answer.

## Known limits

- The CAD helpers build in the root component only, sketches on the XY/XZ/YZ planes (with offsets), and no
  threads, sweeps, lofts or text; the model can still try the raw Fusion API. In a design you made,
  bodies inside components are described and checked and their parameters can be changed, but new
  features go into the root component.
- Your own model is changed through its parameters and dimensions. A size that no dimension holds (a
  sketch drawn without sizes, an imported body) is changed by adding or cutting material.
- The weakest edit is the length or width of a plate the app built itself ("make it shorter, 7 cm"):
  the model sometimes changes the thickness instead. `/undo` and "build it again 70 x 50 x 8 mm" fix it.
- The weak spot of the 12B model is spatial placement in parts of many operations (which end, which
  flange, groove width versus depth). `/think on` helps, at 3-4 times the time.
- `/undo` restores the timeline and changed dimensions; a change made outside them is reported, and
  Fusion's own Undo goes further.
- **macOS is untested**: launchers, process check, memory check, clipboard and inline pictures were
  written for it but never run. `docs/macos-checklist.md` lists what to check.
- Inline screenshots in Windows Terminal (Sixel) were checked by decoding the output, not yet by eye.

## Where things come from

The CAD helper API (`fusion_agent/cad_api.py`), the system prompt (`fusion_agent/prompts/cad12.md`) and
the agent loop (`fusion_agent/agent.py`) come from the bench `fusion-ladder` (the parent folder), where
they were measured. **This app is now their source of truth**; the bench keeps its copies as the
history of the measurements. The plan this app was built from is `PLAN.md`.
