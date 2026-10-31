# fusion-agent

A terminal app in which a local model designs and edits parts in Autodesk Fusion. You write a request
("make a plate 80 by 50, 6 mm thick, with four 6 mm holes"), attach a picture if you have one, and the
model builds the part in Fusion through Fusion's built-in MCP server. Windows and macOS.

Work in progress; see `PLAN.md`.

## Run

- Windows: double-click `fusion-agent.cmd`, or run it from cmd / PowerShell.
- macOS: double-click `fusion-agent.command` in Finder, or run `./fusion-agent` in Terminal.

The first run creates a Python environment in `.venv` and installs the requirements.

Optional global command: `pipx install .` (or `pip install .`) in this folder gives `fusion-agent`
everywhere.

## Source of truth

The CAD helper API (`fusion_agent/cad_api.py`) and the system prompt (`fusion_agent/prompts/cad12.md`)
come from the bench `fusion-ladder`, where they were measured. From now on this project owns them.
