#!/usr/bin/env bash
# macOS: a double-click on this file in Finder opens Terminal and starts fusion-agent.
cd "$(dirname "$0")" || exit 1
./fusion-agent "$@"
code=$?
if [ "$code" -ne 0 ] && [ "$code" -ne 130 ]; then
    echo
    read -r -p "Press Enter to close this window. " _
fi
exit "$code"
