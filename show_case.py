"""Print the dialogue of one result file: scripts, tool output, answers."""
import json
import sys

record = json.load(open(sys.argv[1], encoding="utf-8"))
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 600
print("calls:", [(c["eval_tokens"], c["seconds"], c.get("done_reason")) for c in record.get("calls", [])])
for message in record["messages"][1:]:
    if message.get("tool_calls"):
        for call in message["tool_calls"]:
            arguments = call["function"]["arguments"]
            print(">>> " + str(arguments.get("script", arguments))[:limit])
    elif message["role"] == "tool":
        print("<<< " + message["content"][:limit])
    else:
        print("=== [%s] %s" % (message["role"], (message.get("content") or "")[:limit]))
