# fusion360-local-ai-agent

A local AI model builds and edits parts in Autodesk Fusion from a request in plain words.
Everything runs on your own computer: Fusion, Ollama and the model Gemma 4 12B. No cloud, no account.

**The tool is the folder [`fusion-agent/`](fusion-agent/)**: a terminal app. Its README tells what it can
build, what has to be installed, how to start it and what the measurements showed (96.6 % of the tasks
solved on sets the tool was never tuned on).

In short:

- You type a request: "Сделай пластину 80 на 50 мм толщиной 6 мм с четырьмя отверстиями 6 мм",
  "Make a gear: module 2, 20 teeth, 10 mm wide", "Make the plate thicker, 10 mm", "What is the mass of
  the part?". You can attach a photo of a part and give its sizes in words.
- The model writes a short script of ready-made CAD functions, the app runs it inside Fusion through
  Fusion's built-in MCP server, checks the result against the numbers of the request and shows a
  screenshot.
- Needed: Windows 10/11, Python 3.10+, Autodesk Fusion with the Fusion MCP Server turned on, Ollama and
  the model Gemma 4 12B Q8_0 (a 16 GB GPU keeps the model entirely in video memory). The app never saves
  or closes your Fusion documents.
- Start: `fusion-agent\fusion-agent.cmd` (a double-click works). The first start creates a Python
  environment and installs two packages; after that the app checks Fusion, Ollama and the model itself
  and tells you what to fix.

The rest of this repository (the bench `fusion-ladder`) is where the tool was tuned and measured: task sets with
hand-computed references, runners and the history of the measurements (`cases*.json`, `run_ladder.py`,
`results/`, `HANDOFF.md`). A user of the tool does not need it.
