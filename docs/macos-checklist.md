# macOS checklist

fusion-agent was built and tested on Windows 11. **Every macOS path is untested** until this list has
been run on a Mac. Write down what each step printed, especially anything marked ❓.

## 1. Install

1. Python 3.10 or newer: `python3 --version`. The `python3` that comes with the Xcode tools is 3.9, which
   is too old. Install 3.12 from https://www.python.org/downloads/macos/ or `brew install python@3.12`.
2. Ollama for macOS: https://ollama.com/download/mac. Open the app once; it runs in the menu bar.
3. A model that can call tools, and preferably has vision. The prompt was tuned on Gemma 4 12B
   (`gemma4-12b:q8_0` on the Windows laptop). `ollama list` shows what is installed; the app lists the
   usable ones itself. The app never downloads models.
4. Autodesk Fusion, signed in. Turn on its MCP server: click your profile name in the upper-right
   corner > Preferences > General > API > under "Preferences for Scripting and Programming" tick
   "Fusion MCP Server" (port 27182) > Apply > OK.
   - ❓ Does the Preferences dialog open the same way on the Mac? (Some guides mention Cmd+,.)
     Note the exact menu path you used.
5. The code: `git clone https://github.com/Jacksotnik/fusion360-local-ai-agent.git`, then `cd fusion360-local-ai-agent`.

## 2. Launch

1. `./fusion-agent --version` in Terminal. The first run creates `.venv` and installs the
   requirements (needs the internet once). Expected: `fusion-agent 0.1.0`.
   - ❓ If it says "Permission denied": `chmod +x fusion-agent fusion-agent.command` and tell me
     (the executable bit is committed, so it should not happen).
2. `./fusion-agent doctor`. Expected: every line ✔ (Memory may be ! on a small Mac).
   - ❓ The "Fusion" line uses `pgrep -f "Autodesk Fusion"`. Run `pgrep -lf "Autodesk Fusion"` yourself
     and note what it prints, so the process name can be confirmed.
   - ❓ The "Memory" line reads `sysctl -n hw.memsize`: is the number right?
3. Double-click `fusion-agent.command` in Finder. Expected: Terminal opens and the app starts.
   - ❓ If macOS blocks it ("cannot be opened"): right-click > Open, and note the message.

## 3. Checks inside the app

Run each and note the result.

| # | Do | Expected |
|---|---|---|
| 1 | Quit Ollama (menu bar > Quit), start the app | ✖ Ollama with "Open the Ollama app ..." steps; start Ollama, press Enter: it goes on |
| 2 | Quit Fusion, start the app | ✖ Fusion "Start Autodesk Fusion ..." |
| 3 | Turn the MCP server off in Fusion, start the app | ✖ Fusion MCP with the Preferences steps |
| 4 | Open a design with a body in it, start the app | the question "already has 1 body ... Work in it anyway? [y/N]"; Enter = no |
| 5 | `/new`, then `Сделай пластину 80 на 50 толщиной 6 мм с четырьмя отверстиями 6 мм в 10 мм от углов` | a spinner with seconds, one grey line per script, the answer, a grey stats line |
| 6 | The same in iTerm2 | the screenshot appears inline below the answer |
| 7 | The same in Terminal.app | "Screenshot: <path>"; `/open` opens it in Preview |
| 8 | Drag a PNG from Finder into the Terminal window | the path turns into `[Image: name.png]` |
| 9 | Copy a screenshot to the clipboard (Cmd+Ctrl+Shift+4), press **Ctrl+V** | `[Image: clipboard.png]` |
| 10 | The same with `/paste` | "Attached [Image: clipboard.png ...]" |
| 11 | Option+V | works only with "Use Option as Meta key" (Terminal) / "Esc+" (iTerm2); note what happens |
| 12 | Send a long request and press Ctrl+C while the spinner runs | "Stopped. ..." and the prompt comes back; the next request works |
| 13 | Ctrl+C on an empty line, and Ctrl+D | the app quits with "Bye." |
| 14 | `fusion-agent --selftest` | 4/4 PASS; the self-test designs are closed again |

Session logs and screenshots are in `~/Library/Application Support/fusion-agent/sessions/`; send the
newest folder along with the notes.
