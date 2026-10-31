@echo off
rem Chat with Gemma 4 12B in Fusion 360: requests in Russian, the model builds and edits the part in a new document.
rem Needs Fusion running with its MCP server on, and Ollama with the model gemma4-12b:q8_0.
chcp 65001 >nul
python -I -X utf8 "%~dp0fusion_chat.py" %*
pause
