"""The agent loop measured in fusion-ladder (`run_ladder.py`), as a reusable class.

Behaviour is kept identical to the bench: the current design state is attached to every request,
errors are shortened to "line N of your script" plus the message, a final answer that left the
design unchanged gets up to two nudges, an exact repeat of a script with the same result is flagged,
and the reply is capped (1200 tokens, 4000 with thinking). Only the printing moved into a listener.
"""
import base64
import json
import re
import threading
import time
from importlib import resources

from fusion_agent import fusion_scripts
from fusion_agent.cad_api import CAD_PRELUDE
from fusion_agent.ollama import OllamaCancelled

TUNED_MODEL = "gemma4-12b:q8_0"
NUM_CTX = 32768
MAX_MODEL_CALLS = 20
MAX_NUDGES = 2
TOOL_OUTPUT_CHARS = 6000
KEEP_ALIVE = "30m"

MAX_REPLY_TOKENS = 1200
# With thinking on, the reasoning counts against the cap too and needs room.
MAX_REPLY_TOKENS_THINKING = 4000

# The texts below go to the model and were tuned with it: keep them as they are.
TOO_LONG_TEXT = ("Твой ответ оборвался: он слишком длинный. Вызови fusion_script сразу, "
                 "в скрипте только код, без комментариев.")

REPEAT_TEXT = ("Note: this is exactly the script you already ran, with the same result. Repeating it will not "
               "help. Read the message again, find which number or which part is wrong, and change the approach.")

NUDGE_TEXT = ("Модель в Fusion не изменилась: геометрия та же, что была до задачи. "
              "Сделай это через fusion_script и проверь результат.")

# Scripts that touch documents could reach the owner's own designs, so the runner refuses them.
FORBIDDEN_SCRIPT_PATTERNS = [r"\.documents\b", r"\.save\s*\(", r"\.saveAs\s*\(", r"\.close\s*\(", r"executeTextCommand"]

SCREENSHOT_DIRECTIONS = ["current", "front", "back", "bottom", "top", "left", "right",
                         "iso-bottom-left", "iso-bottom-right", "iso-top-left", "iso-top-right"]

HELPER_SCRIPT_DESCRIPTION = ("Run Python inside Fusion on the active design. The CAD helper API from the system "
                             "prompt is already defined (all lengths in mm), so write only the statements, without "
                             "imports and without def run. Text printed with print() is returned. Do not catch "
                             "exceptions: the error text is returned to you.")


def load_prompt(name="cad12"):
    return resources.files("fusion_agent").joinpath("prompts", name + ".md").read_text(encoding="utf-8")


def build_tools(has_vision=True):
    """The tools of the bench (helpers mode). A model without vision gets no screenshot tool."""
    tools = [
        {"type": "function", "function": {
            "name": "fusion_script",
            "description": HELPER_SCRIPT_DESCRIPTION,
            "parameters": {"type": "object", "properties": {
                "script": {"type": "string", "description": "Python source to run."},
                "readOnly": {"type": "boolean",
                             "description": "true only when the script reads the design and changes nothing."},
            }, "required": ["script"]},
        }},
        {"type": "function", "function": {
            "name": "fusion_screenshot",
            "description": "Take a screenshot of the Fusion view of the active design. The image comes back to you.",
            "parameters": {"type": "object", "properties": {
                "direction": {"type": "string", "enum": SCREENSHOT_DIRECTIONS,
                              "description": "Camera direction before the capture."},
            }, "required": []},
        }},
        {"type": "function", "function": {
            "name": "fusion_api_docs",
            "description": ("Search the Fusion API documentation. Returns classes with their members, or full "
                            "descriptions of members."),
            "parameters": {"type": "object", "properties": {
                "searchPattern": {"type": "string", "description": "Regular expression for class or member names."},
                "apiCategory": {"type": "string", "enum": ["class", "member", "description", "all"],
                                "description": "What to search: class names, member names, descriptions or all."},
                "filter": {"type": "string",
                           "description": "Limit to a namespace or class, e.g. 'adsk.fusion' or 'adsk.fusion.ExtrudeFeatures'."},
            }, "required": ["searchPattern"]},
        }},
    ]
    if not has_vision:
        tools = [tool for tool in tools if tool["function"]["name"] != "fusion_screenshot"]
    return tools


def must(result, what):
    is_success, text = result
    if not is_success:
        raise RuntimeError(what + " failed: " + text)
    return text


def wrap_script(script, prelude):
    """Prepend the helper API; a bare body is wrapped into run()."""
    if re.search(r"^def run\(", script, re.MULTILINE):
        return prelude + "\n\n" + script
    # The body runs inside try so that an error reports the line number of the model's own script.
    indented = "\n".join("        " + line for line in script.splitlines())
    return (prelude + "\n\ndef run(_context: str):\n"
            + "    _first_line = _sys_for_lines._getframe().f_lineno + 2\n"
            + "    try:\n" + indented + "\n"
            + "        pass\n"
            + "    except Exception as _model_error:\n"
            + "        _report_model_error(_model_error, _first_line)\n")


def short_error(traceback_text, model_script):
    """Turn a Fusion traceback into 'line N of your script: code' plus the error message.
    The traceback counts lines of the whole script sent to Fusion: the output guard, the helper
    prelude and the run() header come before the model's own lines."""
    lines = traceback_text.splitlines()
    last_frame = -1
    for index, line in enumerate(lines):
        if line.strip().startswith('File "'):
            last_frame = index
    message_lines = [line for line in lines[last_frame + 1:] if line.strip() and not line.startswith("    ")]
    if message_lines:
        message = "\n".join(message_lines)
    else:
        stripped = traceback_text.strip().splitlines()
        message = stripped[-1] if stripped else "unknown error"

    location = ""
    match = re.search(r"MODEL_LINE (\d+) \| (.*)", message, re.DOTALL)
    if match:
        model_line = int(match.group(1))
        message = match.group(2)
        model_lines = model_script.splitlines()
        if 1 <= model_line <= len(model_lines):
            location = "line %d of your script: %s\n" % (model_line, model_lines[model_line - 1].strip())
    return "Script failed.\n" + location + message


def truncate(text):
    if len(text) <= TOOL_OUTPUT_CHARS:
        return text
    return text[:TOOL_OUTPUT_CHARS] + "\n... [truncated, %d chars total]" % len(text)


def strip_thinking(messages):
    """Thinking of finished turns is dropped (Google's guidance for Gemma 4)."""
    for message in messages:
        if message.get("role") == "assistant" and "thinking" in message:
            del message["thinking"]


def loggable(messages):
    """Copy of the history without base64 images."""
    result = []
    for message in messages:
        copy = dict(message)
        if "images" in copy:
            copy["images"] = ["<png %d bytes>" % len(base64.b64decode(image)) for image in copy["images"]]
        result.append(copy)
    return result


def state_prefix(state):
    """The text put before the request: the describe() output, or a note that the design is empty."""
    if state.strip().startswith("bodies: 0"):
        return "The design is empty.\n\n"
    return "Current design (describe()):\n" + state.strip() + "\n\n"


class RepeatDetector:
    """Flags a tool call that is exactly the previous one and got exactly the same output."""

    def __init__(self):
        self.previous_key = None
        self.previous_output = None

    def check(self, call, output):
        call_key = json.dumps(call.get("function", {}), sort_keys=True, ensure_ascii=False)
        is_repeat = call_key == self.previous_key and output == self.previous_output
        self.previous_key = call_key
        self.previous_output = output
        return is_repeat


class TurnCancelled(Exception):
    """The user stopped the turn (Ctrl+C). The conversation was rolled back to before the request."""


class AgentListener:
    """Receives what happens during a turn. The REPL prints it; the default prints nothing."""

    def status(self, text):
        """What the turn is doing right now: "model" or a tool name."""
        pass

    def model_call(self, stats):
        pass

    def tool_result(self, name, arguments, output):
        pass

    def nudged(self, count):
        pass


def call_stats(response, seconds, tool_calls):
    eval_count = response.get("eval_count", 0)
    eval_seconds = response.get("eval_duration", 0) / 1e9
    prompt_count = response.get("prompt_eval_count", 0)
    prompt_seconds = response.get("prompt_eval_duration", 0) / 1e9
    return {
        "seconds": round(seconds, 2),
        "load_seconds": round(response.get("load_duration", 0) / 1e9, 2),
        "prompt_tokens": prompt_count,
        "prompt_tps": round(prompt_count / prompt_seconds, 1) if prompt_seconds else None,
        "eval_tokens": eval_count,
        "eval_tps": round(eval_count / eval_seconds, 1) if eval_seconds else None,
        "tool_calls": [call.get("function", {}).get("name") for call in tool_calls],
        "done_reason": response.get("done_reason"),
    }


class Agent:
    """One conversation with the model about the session design."""

    def __init__(self, fusion, ollama, session_id, model=TUNED_MODEL, think=False, has_vision=True,
                 has_thinking=True, system_prompt=None, listener=None):
        self.fusion = fusion
        self.ollama = ollama
        self.session_id = session_id
        self.model = model
        self.think = think
        self.has_vision = has_vision
        self.has_thinking = has_thinking
        self.system_prompt = system_prompt if system_prompt is not None else load_prompt()
        self.listener = listener or AgentListener()
        self.prelude = CAD_PRELUDE
        self._cancel_event = threading.Event()
        self.messages = []
        self.reset()

    def reset(self):
        """Start a new conversation (the design stays as it is)."""
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def set_model(self, model, has_vision, has_thinking):
        self.model = model
        self.has_vision = has_vision
        self.has_thinking = has_thinking

    def cancel(self):
        """Ask the running turn to stop; safe to call from another thread."""
        self._cancel_event.set()
        self.ollama.cancel()

    def _check_cancelled(self):
        if self._cancel_event.is_set():
            raise TurnCancelled()

    # --- Fusion helpers -------------------------------------------------------------------------

    def run_helper(self, statements, read_only=True):
        """Run helper API statements (e.g. "describe()") in the session design."""
        return self.fusion.run_script(wrap_script(statements, self.prelude), read_only=read_only)

    def describe(self):
        return must(self.run_helper("describe()"), "describe")

    def signature(self):
        return json.loads(must(self.fusion.run_script(fusion_scripts.SIGNATURE_SCRIPT, read_only=True), "signature"))

    def is_session_active(self):
        script = fusion_scripts.active_is_session_script(self.session_id)
        return must(self.fusion.run_script(script, read_only=True), "active check").strip() == "session"

    def user_message(self, request):
        """The request, with the current design state attached (saves a describe() call)."""
        return state_prefix(self.describe()) + request

    # --- The loop -------------------------------------------------------------------------------

    def _chat(self):
        reply_cap = MAX_REPLY_TOKENS_THINKING if self.think else MAX_REPLY_TOKENS
        body = {
            "model": self.model,
            "messages": self.messages,
            "tools": build_tools(self.has_vision),
            "stream": False,
            "keep_alive": KEEP_ALIVE,
            "options": {"num_ctx": NUM_CTX, "num_predict": reply_cap},
        }
        # A model without the thinking capability rejects the field, so it is sent only when it means something.
        if self.has_thinking:
            body["think"] = self.think
        try:
            return self.ollama.chat(body, cancel_event=self._cancel_event)
        except OllamaCancelled:
            raise TurnCancelled() from None

    def turn(self, request, images=None):
        """Answer one request. On Ctrl+C (cancel()) or an error the conversation is rolled back to
        before the request; the design keeps whatever the finished scripts already changed."""
        self._cancel_event.clear()
        started = time.time()
        history_length = len(self.messages)
        try:
            strip_thinking(self.messages)
            start_signature = self.signature()
            message = {"role": "user", "content": self.user_message(request)}
            if images:
                message["images"] = list(images)
            self.messages.append(message)
            result = self._agent_turn(start_signature)
        except BaseException:
            del self.messages[history_length:]
            raise
        result["seconds"] = round(time.time() - started, 2)
        result["start_signature"] = start_signature
        return result

    def _agent_turn(self, start_signature):
        """Answer the last user message of the conversation: the model calls tools until it gives a final answer."""
        calls = []
        nudges = 0
        status = "max_calls"
        final_answer = ""
        end_signature = None
        repeats = RepeatDetector()

        for _ in range(MAX_MODEL_CALLS):
            self._check_cancelled()
            self.listener.status("model")
            started = time.time()
            response = self._chat()
            seconds = time.time() - started
            message = response.get("message", {})
            tool_calls = message.get("tool_calls") or []

            stats = call_stats(response, seconds, tool_calls)
            calls.append(stats)
            self.listener.model_call(stats)

            if response.get("done_reason") == "length" and not tool_calls:
                self.messages.append({"role": "assistant", "content": message.get("content", "")[:2000]})
                self.messages.append({"role": "user", "content": TOO_LONG_TEXT})
                continue

            assistant = {"role": "assistant", "content": message.get("content", "")}
            if tool_calls:
                assistant["tool_calls"] = tool_calls
                if message.get("thinking"):
                    assistant["thinking"] = message["thinking"]
            self.messages.append(assistant)

            if tool_calls:
                screenshots = []
                for call in tool_calls:
                    self._check_cancelled()
                    tool_name = call.get("function", {}).get("name", "")
                    self.listener.status(tool_name)
                    output = self.run_tool(call, screenshots)
                    if repeats.check(call, output):
                        output += "\n" + REPEAT_TEXT
                    self.listener.tool_result(tool_name, call.get("function", {}).get("arguments"), output)
                    tool_message = {"role": "tool", "tool_name": tool_name, "content": output}
                    if call.get("id"):
                        tool_message["tool_call_id"] = call["id"]
                    self.messages.append(tool_message)

                if not self.is_session_active():
                    status = "left_session_design"
                    break

                for shot in screenshots:
                    self.messages.append({"role": "user", "content": "Screenshot (%s)." % shot["direction"],
                                          "images": [shot["image"]]})
                continue

            final_answer = message.get("content", "")
            end_signature = self.signature()
            is_unchanged = end_signature == start_signature
            if is_unchanged and nudges < MAX_NUDGES:
                nudges += 1
                strip_thinking(self.messages)
                self.messages.append({"role": "user", "content": NUDGE_TEXT})
                self.listener.nudged(nudges)
                continue
            status = "answered_unchanged" if is_unchanged else "answered"
            break

        if end_signature is None and status != "left_session_design":
            end_signature = self.signature()
        return {
            "status": status,
            "final_answer": final_answer,
            "nudges": nudges,
            "calls": calls,
            "end_signature": end_signature,
            "changed": end_signature is not None and end_signature != start_signature,
        }

    def run_tool(self, call, screenshots):
        """Execute one tool call. Returns the text for the tool message; screenshots are collected separately."""
        function = call.get("function", {})
        name = function.get("name", "")
        arguments = function.get("arguments") or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except ValueError:
                return "Error: arguments are not valid JSON."
        if not isinstance(arguments, dict):
            return "Error: arguments must be an object."

        if name == "fusion_script":
            script = str(arguments.get("script", ""))
            if not script.strip():
                return "Error: empty script."
            for pattern in FORBIDDEN_SCRIPT_PATTERNS:
                if re.search(pattern, script):
                    return ("Error: this task does not allow working with documents (%s). "
                            "Work in the active design." % pattern)
            wrapped = wrap_script(script, self.prelude)
            is_read_only = arguments.get("readOnly") is True
            is_success, text = self.fusion.run_script(wrapped, read_only=is_read_only)
            if is_success:
                return truncate(text) if text.strip() else "Script finished, it printed nothing."
            # Fusion rolls a failed script back completely; say so and show what the design is now.
            state = self.run_helper("state_summary()")[1].strip()
            return truncate(short_error(text, script)
                            + "\nNothing of this script was kept: Fusion undid all of it. " + state)

        if name == "fusion_screenshot":
            direction = str(arguments.get("direction") or "iso-top-right")
            if direction not in SCREENSHOT_DIRECTIONS:
                direction = "iso-top-right"
            self.fusion.run_script(fusion_scripts.fit_view_script(direction), read_only=True)
            image = self.fusion.screenshot(direction="current", width=800, height=600, transparent_background=False)
            if image is None:
                return "Error: screenshot failed."
            screenshots.append({"direction": direction, "image": image})
            return "Screenshot taken (%s). The image follows in the next message." % direction

        if name == "fusion_api_docs":
            search_pattern = str(arguments.get("searchPattern", ""))
            if not search_pattern:
                return "Error: searchPattern is required."
            api_category = arguments.get("apiCategory")
            api_filter = arguments.get("filter")
            return truncate(self.fusion.api_docs(search_pattern, api_category, api_filter))

        return "Error: unknown tool " + name
