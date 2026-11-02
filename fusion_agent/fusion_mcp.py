"""Minimal client for Fusion's built-in MCP server (Streamable HTTP, JSON-RPC). Ported from fusion-ladder."""
import json
import urllib.error
import urllib.request

FUSION_URL = "http://127.0.0.1:27182/mcp"

# The Fusion MCP wraps sys.stdout/sys.stderr on every run and never unwraps, so the wrappers chain up.
# Each wrapper caps the text it passes on, and an old wrapper that reached the cap silently swallows
# all later output. Every script therefore starts by cutting the chain back to the real stream;
# stderr goes nowhere, as it did before (otherwise an internal pydevd traceback leaks into the output).
# Measured in fusion-ladder: without this guard all print output is lost after a few hundred runs.
OUTPUT_GUARD = '''import sys as _guard_sys


class _GuardSink:
    def write(self, text):
        return len(text)

    def flush(self):
        pass


def _guard_reset(writer, target):
    if hasattr(writer, "_original"):
        writer._original = target
        writer._written = 0
        writer._truncated = False


_guard_reset(_guard_sys.stdout, _guard_sys.__stdout__)
_guard_reset(_guard_sys.stderr, _GuardSink())

'''


class FusionUnavailable(Exception):
    """Fusion's MCP server did not answer (Fusion closed, MCP turned off, wrong port)."""


class FusionMcp:
    def __init__(self, url=FUSION_URL, timeout_sec=600, connect_timeout_sec=10):
        self.url = url
        self.timeout_sec = timeout_sec
        self.connect_timeout_sec = connect_timeout_sec
        self.session_id = None
        self.next_id = 1
        self.connect()

    def connect(self):
        """Open a new MCP session (also after Fusion was restarted)."""
        self.session_id = None
        self._send("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "fusion-agent", "version": "0"},
        }, timeout_sec=self.connect_timeout_sec)
        self._send("notifications/initialized", None, is_notification=True, timeout_sec=self.connect_timeout_sec)

    def _send(self, method, params, is_notification=False, timeout_sec=None):
        body = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        if not is_notification:
            body["id"] = self.next_id
            self.next_id += 1

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        timeout = timeout_sec if timeout_sec is not None else self.timeout_sec
        request = urllib.request.Request(self.url, data=json.dumps(body).encode("utf-8"), headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                session_id = response.headers.get("Mcp-Session-Id")
                if session_id:
                    self.session_id = session_id
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            raise FusionUnavailable("Fusion MCP answered HTTP %d to %s" % (error.code, method)) from None
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as error:
            reason = getattr(error, "reason", error)
            raise FusionUnavailable("Fusion MCP at %s did not answer: %s" % (self.url, reason)) from None

        if is_notification or not raw.strip():
            return None
        return parse_response(raw)

    def call(self, tool_name, arguments):
        """Call a tool and return its content list (text and image items)."""
        reply = self._send("tools/call", {"name": tool_name, "arguments": arguments})
        if "error" in reply:
            raise RuntimeError("MCP error: " + json.dumps(reply["error"], ensure_ascii=False))
        return reply.get("result", {}).get("content", [])

    def run_script(self, script, read_only=False):
        """Run a Fusion Python script; return (is_success, text)."""
        script_object = {"script": OUTPUT_GUARD + script}
        if read_only:
            script_object["readOnly"] = True
        content = self.call("fusion_mcp_execute", {"featureType": "script", "object": script_object})
        text = content_text(content)
        try:
            parsed = json.loads(text)
        except ValueError:
            return False, text
        if parsed.get("success"):
            return True, parsed.get("message", "")
        return False, parsed.get("error", text)

    def screenshot(self, direction="current", width=1000, height=800, transparent_background=True):
        """Return base64 PNG of the active view, or None."""
        content = self.call("fusion_mcp_read", {
            "queryType": "screenshot",
            "direction": direction,
            "width": width,
            "height": height,
            "transparentBackground": transparent_background,
        })
        for item in content:
            if item.get("type") == "image":
                return item.get("data")
        text = content_text(content)
        try:
            parsed = json.loads(text)
        except ValueError:
            return None
        return parsed.get("base64Data")

    def api_docs(self, search_pattern, api_category=None, api_filter=None):
        arguments = {"queryType": "apiDocumentation", "searchPattern": search_pattern}
        if api_category:
            arguments["apiCategory"] = api_category
        if api_filter:
            arguments["filter"] = api_filter
        return content_text(self.call("fusion_mcp_read", arguments))


def parse_response(raw):
    """The server may answer with plain JSON or with an SSE stream."""
    stripped = raw.strip()
    if stripped.startswith("{"):
        return json.loads(stripped)
    last_data = None
    for line in stripped.splitlines():
        if line.startswith("data:"):
            last_data = line[len("data:"):].strip()
    if last_data is None:
        raise RuntimeError("unexpected MCP response: " + stripped[:300])
    return json.loads(last_data)


def content_text(content):
    parts = []
    for item in content:
        if item.get("type") == "text":
            parts.append(item.get("text") or "")
    return "\n".join(parts)
