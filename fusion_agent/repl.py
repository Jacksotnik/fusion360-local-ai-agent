"""The interactive session: prompt, commands, turns with a spinner, pictures in and out."""
import base64
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time

from fusion_agent import __version__, config, console, display, doctor, fusion_scripts, images, models, term
from fusion_agent.agent import TUNED_MODEL, Agent, AgentListener, NUM_CTX, TurnCancelled, must
from fusion_agent.fusion_mcp import FusionUnavailable
from fusion_agent.ollama import OllamaError
from fusion_agent.session import DesignSession, SessionLog, new_session_id

COMMANDS = [
    ("/help", "", "show the commands and keys"),
    ("/new", "", "open a new empty design in Fusion and work in it"),
    ("/state", "", "describe the design: bodies, sizes, timeline"),
    ("/screenshot", "[view]", "show the design (iso-top-right, front, top, ...)"),
    ("/image", "<path>", "attach a picture to the next request"),
    ("/paste", "", "attach the picture from the clipboard (also Alt+V)"),
    ("/model", "[name]", "list the models, or switch to one"),
    ("/think", "on|off", "slow, more accurate mode: the model thinks first"),
    ("/undo", "[n]", "undo the last n changes (design and conversation; questions are skipped)"),
    ("/reset", "", "start a new conversation; the design stays"),
    ("/verbose", "on|off", "show the scripts the model runs"),
    ("/screenshots", "on|off", "a screenshot after each change of the design"),
    ("/open", "", "open the last screenshot in the system viewer"),
    ("/doctor", "", "run the startup checks again"),
    ("/exit", "", "quit (also Ctrl+D)"),
]

IMAGE_LABEL = re.compile(r"\[Image: [^\]\n]+\]")
PASTE_LABEL = re.compile(r"\[Pasted text #\d+, \d+ lines\]")
NEWLINE_MARK = "↵"
LONG_PASTE_LINES = 3

STATUS_NOTES = {
    "max_calls": "The model stopped after 20 calls without a final answer.",
    "answered_unchanged": "The design did not change.",
    "left_session_design": "The active document in Fusion changed during the request: stopped there.",
}

STATUS_TEXT = {
    "model": "model",
    "fusion_script": "running a script in Fusion",
    "fusion_screenshot": "taking a screenshot",
    "fusion_api_docs": "reading the Fusion API docs",
}


def terminal_width():
    return max(40, shutil.get_terminal_size((100, 24)).columns)


def clip(text, width):
    text = " ".join(text.split())
    if len(text) <= width:
        return text
    return text[:max(0, width - 1)] + "…"


def read_answer(text):
    """One line of input. In a terminal it goes through prompt_toolkit, which reads Ctrl+C as a key
    (see console.py); from a pipe it is plain input()."""
    if sys.stdin.isatty() and sys.stdout.isatty():
        from prompt_toolkit import prompt
        try:
            return prompt(text)
        finally:
            console.keep_ctrl_c_as_key()
    return input(text)


def ask_yes_no(question, default=False):
    """A y/N question on its own line; Ctrl+C or end of input counts as the default."""
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = read_answer(question + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    if not answer:
        return default
    return answer in ("y", "yes")


def ask_choice(question, choices):
    """One letter out of choices (a dict letter -> label); Ctrl+C or empty input gives None."""
    line = " · ".join("[%s] %s" % (letter, label) for letter, label in choices.items())
    while True:
        print(question)
        try:
            answer = read_answer(line + "\n" + term.SYMBOLS["prompt"] + " ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if not answer:
            return None
        if answer[:1] in choices:
            return answer[:1]


def print_model_rows(found, current, numbered):
    """One line per model: name, size, vision/thinking, and which one the prompt was tuned on."""
    width = max(len(info["name"]) for info in found)
    for number, info in enumerate(found, start=1):
        if numbered:
            marker = "%2d." % number
        elif current and models.normalize(info["name"]) == models.normalize(current):
            marker = " " + term.SYMBOLS["prompt"]
        else:
            marker = "  "
        features = [name for name in ("vision", "thinking") if name in info["capabilities"]]
        tuned = "  (tuned)" if info["is_tuned"] else ""
        print(" %s %s  %8s  %s%s" % (marker, info["name"].ljust(width), models.gigabytes(info["size"]),
                                     ", ".join(features) or "text only", tuned))


def open_in_viewer(path):
    if term.IS_WINDOWS:
        os.startfile(str(path))
    elif term.IS_MAC:
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


class Spinner:
    """A one-line "⠋ 12 s  model" indicator; other threads print above it with print_line()."""

    def __init__(self):
        self.lock = threading.Lock()
        self.is_enabled = sys.stdout.isatty()
        self.started = time.time()
        self.status = ""
        self.frame = 0
        self.shown_width = 0

    def start(self, status):
        with self.lock:
            self.started = time.time()
            self.status = status
            self.frame = 0

    def set_status(self, status):
        with self.lock:
            self.status = status

    def tick(self):
        with self.lock:
            if not self.is_enabled:
                return
            frames = term.SPINNER_FRAMES
            text = "%s %d s  %s" % (frames[self.frame % len(frames)], time.time() - self.started, self.status)
            self.frame += 1
            text = clip(text, terminal_width() - 2)
            self._clear()
            sys.stdout.write(term.paint(text, term.GREY))
            sys.stdout.flush()
            self.shown_width = len(text)

    def _clear(self):
        if self.shown_width:
            sys.stdout.write("\r" + " " * self.shown_width + "\r")
            self.shown_width = 0

    def print_line(self, text):
        with self.lock:
            self._clear()
            sys.stdout.write(text + "\n")
            sys.stdout.flush()

    def stop(self):
        with self.lock:
            self._clear()
            sys.stdout.flush()


class TurnPrinter(AgentListener):
    """Prints the tool calls of a turn and writes them to the session log."""

    def __init__(self, app):
        self.app = app
        self.has_changing_script = False

    def status(self, text):
        self.app.spinner.set_status(STATUS_TEXT.get(text, text))

    def model_call(self, stats):
        self.app.log.write("model_call", **stats)

    def nudged(self, count):
        self.app.log.write("nudge", count=count)
        if self.app.settings["verbose"]:
            self.app.spinner.print_line(term.paint("  the model said it was done, but the design did not change: "
                                                   "asked it to do the work", term.GREY))

    def tool_result(self, name, arguments, output):
        if not isinstance(arguments, dict):
            arguments = {}
        self.app.log.write("tool", name=name, arguments=arguments, output=output)
        bullet = term.SYMBOLS["bullet"]
        width = terminal_width() - 4
        if name == "fusion_script":
            if arguments.get("readOnly") is not True:
                self.has_changing_script = True
            if self.app.settings["verbose"]:
                lines = [term.paint("%s script:" % bullet, term.CYAN)]
                for line in str(arguments.get("script", "")).strip().splitlines():
                    lines.append(term.paint("    " + line, term.GREY))
                for line in output.strip().splitlines()[:4]:
                    lines.append("  → " + clip(line, width))
                self.app.spinner.print_line("\n".join(lines))
                return
            first = " · ".join(line.strip() for line in output.strip().splitlines()[:2])
            self.app.spinner.print_line(term.paint(clip("%s script → %s" % (bullet, first), width), term.GREY))
            return
        if name == "fusion_screenshot":
            text = "%s screenshot (%s)" % (bullet, arguments.get("direction") or "iso-top-right")
        elif name == "fusion_api_docs":
            text = "%s API docs: %s" % (bullet, arguments.get("searchPattern", ""))
        else:
            text = "%s %s" % (bullet, name)
        self.app.spinner.print_line(term.paint(clip(text, width), term.GREY))


class InputLabels:
    """Labels shown in the input line instead of pictures and long pastes, and what they stand for."""

    def __init__(self):
        self.images = {}
        self.pastes = {}
        self.paste_count = 0
        self.rejected_paths = set()

    def add_image(self, attachment):
        label = "[Image: %s]" % attachment.name
        number = 2
        while label in self.images and self.images[label] is not attachment:
            label = "[Image: %s #%d]" % (attachment.name, number)
            number += 1
        self.images[label] = attachment
        return label

    def add_paste(self, text):
        self.paste_count += 1
        label = "[Pasted text #%d, %d lines]" % (self.paste_count, len(text.splitlines()))
        self.pastes[label] = text
        return label

    def expand(self, text):
        """(request text for the model, attachments in order of their labels)."""
        attachments = []
        for match in IMAGE_LABEL.finditer(text):
            attachment = self.images.get(match.group(0))
            if attachment is not None:
                attachments.append(attachment)
        request = IMAGE_LABEL.sub(lambda match: "" if match.group(0) in self.images else match.group(0), text)
        request = PASTE_LABEL.sub(lambda match: self.pastes.get(match.group(0), match.group(0)), request)
        request = request.replace(NEWLINE_MARK, "\n")
        request = re.sub(r"[ \t]{2,}", " ", request).strip()
        return request, attachments

    def for_history(self, text):
        """The history keeps paths instead of picture labels, so a recalled line works again."""
        def picture_path(match):
            attachment = self.images.get(match.group(0))
            if attachment is None or not attachment.source_path:
                return match.group(0)
            path = str(attachment.source_path)
            return '"%s"' % path if " " in path else path
        text = IMAGE_LABEL.sub(picture_path, text)
        return PASTE_LABEL.sub(lambda match: self.pastes.get(match.group(0), match.group(0)).replace("\n", NEWLINE_MARK),
                               text)


class App:
    def __init__(self, args):
        self.args = args
        self.settings = config.load_settings()
        if args.model:
            self.settings["model"] = args.model
        if args.think:
            self.settings["think"] = True
        if args.verbose:
            self.settings["verbose"] = True
        if args.no_screenshots:
            self.settings["screenshots"] = False
        self.spinner = Spinner()
        self.labels = InputLabels()
        self.log = None
        self.fusion = None
        self.ollama = None
        self.design = None
        self.agent = None
        self.model_details = None
        self.undo_stack = []
        self.last_picture = None
        self.has_warned_untuned = False
        self.pending_input = ""
        self.prompt_session = None
        self.is_interactive = sys.stdin.isatty() and sys.stdout.isatty()

    # --- Start ----------------------------------------------------------------------------------

    def run(self):
        print("fusion-agent %s" % __version__)
        if self.is_interactive:
            console.take_ctrl_c_as_key()
        try:
            checks = doctor.wait_until_ready(self.settings["model"], read_line=read_answer,
                                             include_document=not self.args.new, choose_model=self.pick_model)
        except (KeyboardInterrupt, EOFError):
            print()
            return 130
        self.fusion = checks.fusion
        self.ollama = checks.ollama
        self.model_details = checks.model_details
        if checks.model != self.settings["model"]:
            self.settings["model"] = checks.model
            config.save_settings(self.settings)
        session_folder = config.new_session_dir()
        self.log = SessionLog(session_folder)
        session_id = new_session_id()
        self.design = DesignSession(self.fusion, session_id)
        self.agent = Agent(self.fusion, self.ollama, session_id, model=self.settings["model"],
                           think=self.settings["think"] and self.model_details["has_thinking"],
                           has_vision=self.model_details["has_vision"],
                           has_thinking=self.model_details["has_thinking"], listener=TurnPrinter(self))
        if self.settings["think"] and not self.model_details["has_thinking"]:
            print("The model %s cannot think: thinking is off." % self.settings["model"])
        self.log.write("start", version=__version__, session_id=session_id, model=self.settings["model"],
                       think=self.agent.think, platform=sys.platform)

        if self.args.new:
            self.open_new_design()
        else:
            self.choose_start_design(checks.document)
        self.print_banner(session_folder)
        if self.is_interactive:
            return self.prompt_loop()
        return self.plain_loop()

    def pick_model(self, usable_models):
        """At start, when the chosen model is missing: pick one of the installed ones that call tools."""
        print("Pick a model from the ones installed in Ollama:")
        print_model_rows(usable_models, current=None, numbered=True)
        while True:
            try:
                answer = read_answer("Model number (Enter = 1, Ctrl+C quits): ").strip()
            except EOFError:
                return None
            if not answer:
                return usable_models[0]["name"]
            if answer.isdigit() and 1 <= int(answer) <= len(usable_models):
                return usable_models[int(answer) - 1]["name"]

    def choose_start_design(self, info):
        kind = doctor.document_kind(info)
        if kind == "empty":
            name = self.design.adopt_active()
            print("Working in the empty design \"%s\"." % name)
            return
        if kind == "has_content":
            self.offer_design_with_content(info)
            return
        print("No design to work in yet: type /new, or open an empty design in Fusion (File > New Design).")

    def offer_design_with_content(self, info):
        name = info.get("name", "")
        if info.get("session"):
            question = "\"%s\" was made in an earlier fusion-agent session. Continue in it?" % name
        else:
            question = ("The open design \"%s\" has %s. Work with it (change it or ask about it; "
                        "nothing is saved)?" % (name, doctor.plural(info.get("bodies", 0), "body", "bodies")))
        if ask_yes_no(question, default=True):
            self.design.adopt_active()
            print("Working with \"%s\". Ask about it or ask for a change; /undo takes a change back." %
                  self.design.design_name)
            return True
        print("Not touching \"%s\". Type /new, or open an empty design in Fusion (File > New Design)." % name)
        return False

    def open_new_design(self):
        name = self.design.new_design()
        self.agent.reset()
        self.undo_stack = []
        self.log.write("new_design", name=name)
        print("New design \"%s\" is open in Fusion." % name)

    def print_banner(self, session_folder):
        mode = " · thinking on" if self.agent.think else ""
        print("Model %s%s. Session files: %s" % (self.settings["model"], mode, session_folder))
        print(term.paint("Type a request in any language. /help lists the commands. "
                         "Ctrl+C stops an answer, Ctrl+D quits.", term.GREY))
        print(term.paint("Examples: \"Сделай пластину 80 на 50 мм толщиной 6 мм с четырьмя отверстиями 6 мм\", "
                         "\"Сделай шестерню: модуль 2, 20 зубьев, ширина 10 мм\", "
                         "\"Сделай пластину толще, 10 мм\", \"Какая масса детали?\"; "
                         "drag a picture into the window to build a part from a photo.", term.GREY))

    # --- Input ----------------------------------------------------------------------------------

    def prompt_text(self):
        name = models.short_name(self.settings["model"])
        parts = [("ansicyan", name)]
        if self.agent.think:
            parts.append(("ansiyellow", " think"))
        parts.append(("", " %s " % term.SYMBOLS["prompt"]))
        return parts

    def build_prompt_session(self):
        from fusion_agent.prompt_input import build_prompt_session
        return build_prompt_session(self)

    def prompt_loop(self):
        self.prompt_session = self.build_prompt_session()
        while True:
            default = self.pending_input
            self.pending_input = ""
            try:
                line = self.prompt_session.prompt(self.prompt_text, default=default)
            except (KeyboardInterrupt, EOFError):
                return self.quit()
            finally:
                console.keep_ctrl_c_as_key()
            if not self.handle_line(line):
                return self.quit()

    def plain_loop(self):
        """Input from a pipe or a file: one request per line, no prompt_toolkit."""
        for raw_line in sys.stdin:
            line = raw_line.rstrip("\r\n")
            print(term.SYMBOLS["prompt"] + " " + line)
            line = self.relabel_paths(line)
            if not self.handle_line(line):
                break
        return self.quit()

    def quit(self):
        print("Bye. The design stays open in Fusion; saving it is up to you.")
        if self.log:
            self.log.write("exit")
        return 0

    def relabel_paths(self, text):
        """Replace picture paths in the text by labels; a path that cannot be read stays as it is."""
        found = images.find_image_paths(text)
        if not found:
            return text
        result = text
        for start, end, path in reversed(found):
            try:
                attachment = images.load_image(path)
            except images.ImageError as error:
                if path not in self.labels.rejected_paths:
                    self.labels.rejected_paths.add(path)
                    print("Not attached: %s" % error)
                continue
            label = self.labels.add_image(attachment)
            result = result[:start] + label + result[end:]
        return result

    def handle_line(self, line):
        """Returns False when the session should end."""
        stripped = line.strip()
        if not stripped:
            return True
        if stripped.startswith("/"):
            return self.handle_command(stripped)
        self.handle_request(line)
        return True

    # --- Requests -------------------------------------------------------------------------------

    def handle_request(self, line):
        request, attachments = self.labels.expand(line)
        if not request:
            print("Add what to do with the picture, then press Enter.")
            self.pending_input = line.strip() + " "
            return
        if attachments and not self.agent.has_vision:
            print("The model %s cannot see pictures: the request was not sent. Remove the picture or "
                  "switch the model (/model)." % self.settings["model"])
            self.pending_input = line
            return
        if not self.ensure_design():
            self.pending_input = line
            return
        saved = []
        for attachment in attachments:
            saved.append(self.save_attachment(attachment))
        self.log.write("request", text=request, images=saved)
        self.run_turn(request, attachments)

    def save_attachment(self, attachment):
        """Keep a copy of every picture sent, so the log and the history can point at it."""
        path = self.log.picture_path("input")
        try:
            with open(path, "wb") as file:
                file.write(attachment.png_bytes)
        except OSError:
            return attachment.name
        if not attachment.source_path:
            attachment.source_path = str(path)
        return str(path)

    def ensure_design(self):
        """True when the session design is the active document; otherwise ask what to do."""
        try:
            if not self.design.has_design:
                info = self.design.active_info()
                kind = doctor.document_kind(info)
                if kind == "empty":
                    self.design.adopt_active()
                    print("Working in the empty design \"%s\"." % self.design.design_name)
                    return True
                if kind == "has_content":
                    return self.offer_design_with_content(info)
                result = doctor.document_result(info)
                print("No design to work in: %s." % result.detail)
                for step in result.hint:
                    print("  " + step)
                return False
            if self.design.is_active():
                return True
            return self.recover_session_design()
        except FusionUnavailable as error:
            self.report_fusion_lost(error)
            return False
        except RuntimeError as error:
            print("Could not check the active document: %s" % error)
            return False

    def recover_session_design(self):
        info = self.design.active_info() or {}
        active_name = info.get("name", "")
        if not active_name:
            active = "another document"
        elif active_name == self.design.design_name:
            # Every unsaved design in Fusion is called "Untitled": the name alone does not tell them apart.
            active = "another document (also named \"%s\")" % active_name
        else:
            active = "\"%s\"" % active_name
        choices = {"b": "back to the session design", "n": "new design", "s": "skip this request"}
        can_switch = doctor.document_kind(info) in ("empty", "has_content")
        if can_switch:
            choices = {"w": "work with %s instead" % active, "b": "back to the session design",
                       "n": "new design", "s": "skip this request"}
        choice = ask_choice("The active document in Fusion is %s, not this session's design \"%s\"." % (
            active, self.design.design_name), choices)
        if choice == "w" and can_switch:
            self.design.adopt_active()
            self.agent.reset()
            self.undo_stack = []
            self.log.write("adopted_design", name=self.design.design_name)
            print("Working with \"%s\" now (a new conversation)." % self.design.design_name)
            return True
        if choice == "b":
            if self.design.activate():
                print("Back in \"%s\"." % self.design.design_name)
                return True
            print("The session design was closed. Type /new for a new one.")
            return False
        if choice == "n":
            self.open_new_design()
            return True
        print("Skipped.")
        return False

    def report_fusion_lost(self, error):
        self.log.write("error", kind="fusion", message=str(error))
        print("Fusion does not answer (%s). Is Fusion still running with its MCP server on? /doctor checks." % error)
        try:
            self.fusion.connect()
        except FusionUnavailable:
            pass

    def run_turn(self, request, attachments):
        snapshot = self.take_snapshot()
        history_length = len(self.agent.messages)
        printer = self.agent.listener
        printer.has_changing_script = False
        outcome = {}
        done = threading.Event()

        def work():
            try:
                outcome["result"] = self.agent.turn(request, [attachment.base64 for attachment in attachments])
            except BaseException as error:
                outcome["error"] = error
            finally:
                done.set()

        # The worker signals an Event: Thread.join() interrupted by Ctrl+C can mark a running thread as ended.
        threading.Thread(target=work, daemon=True).start()
        self.spinner.start("model")
        try:
            self.wait_for(done)
        except KeyboardInterrupt:
            self.spinner.set_status("stopping... (Ctrl+C again quits)")
            self.agent.cancel()
            try:
                self.wait_for(done)
            except KeyboardInterrupt:
                self.spinner.stop()
                print("\nQuit.")
                console.restore()
                os._exit(130)
        self.spinner.stop()

        error = outcome.get("error")
        if error is not None:
            self.report_turn_error(error, printer.has_changing_script)
            return
        result = outcome["result"]
        # Only a request that changed the design can be undone: "/undo" after a question about the
        # size must take back the change before it, not the question.
        if result["changed"]:
            self.undo_stack.append({"snapshot": snapshot, "history_length": history_length,
                                    "start_signature": result["start_signature"]})
        self.print_result(result)

    def wait_for(self, done):
        """Spin until the turn ends; Ctrl+C raises KeyboardInterrupt (as a key on Windows, see console.py)."""
        while not done.wait(0.1):
            self.spinner.tick()
            if console.ctrl_c_pressed():
                raise KeyboardInterrupt()

    def take_snapshot(self):
        try:
            text = must(self.fusion.run_script(fusion_scripts.SNAPSHOT_SCRIPT, read_only=True), "snapshot")
            return json.loads(text)
        except (RuntimeError, ValueError, FusionUnavailable):
            return None

    def report_turn_error(self, error, has_changing_script):
        if isinstance(error, TurnCancelled):
            self.log.write("cancelled")
            if has_changing_script:
                print("Stopped. The conversation is back to before this request; the design keeps what the "
                      "finished scripts changed (/state shows it).")
            else:
                print("Stopped. Nothing was changed.")
            return
        if isinstance(error, FusionUnavailable):
            self.report_fusion_lost(error)
            return
        if isinstance(error, OllamaError):
            self.log.write("error", kind="ollama", message=str(error))
            print("Ollama: %s" % error)
            return
        self.log.write("error", kind=type(error).__name__, message=str(error))
        print("Error: %s: %s" % (type(error).__name__, error))

    def print_result(self, result):
        answer = result["final_answer"].strip()
        self.log.write("answer", status=result["status"], text=answer, seconds=result["seconds"],
                       model_calls=len(result["calls"]), nudges=result["nudges"], changed=result["changed"])
        if answer:
            print(answer)
        note = STATUS_NOTES.get(result["status"])
        if note:
            print(term.paint(note, term.YELLOW))
        print(term.paint(self.stats_line(result), term.GREY))
        if result["changed"] and self.settings["screenshots"] and result["status"] != "left_session_design":
            self.show_screenshot("iso-top-right", quiet=True)

    def stats_line(self, result):
        calls = result["calls"]
        parts = ["%.1f s" % result["seconds"], "%d model call%s" % (len(calls), "" if len(calls) == 1 else "s")]
        tokens = 0
        seconds = 0.0
        for call in calls:
            if call["eval_tps"] and call["eval_tokens"]:
                tokens += call["eval_tokens"]
                seconds += call["eval_tokens"] / call["eval_tps"]
        if seconds > 0:
            parts.append("%.0f t/s" % (tokens / seconds))
        if calls:
            used = calls[-1]["prompt_tokens"] + calls[-1]["eval_tokens"]
            parts.append("context %.1fk/%dk" % (used / 1000, NUM_CTX // 1024))
            if used > 0.8 * NUM_CTX:
                parts.append("nearly full: /reset starts a new conversation")
        return " · ".join(parts)

    # --- Pictures out ---------------------------------------------------------------------------

    def show_screenshot(self, view, quiet=False):
        try:
            self.fusion.run_script(fusion_scripts.fit_view_script(view), read_only=True)
            image = self.fusion.screenshot(direction="current", width=1000, height=800, transparent_background=False)
        except FusionUnavailable as error:
            self.report_fusion_lost(error)
            return
        if image is None:
            print("The screenshot failed.")
            return
        path = self.log.picture_path("shot")
        with open(path, "wb") as file:
            file.write(base64.b64decode(image))
        self.last_picture = path
        self.log.write("screenshot", view=view, path=str(path))
        is_shown = display.show_image(path)
        if not is_shown or not quiet:
            print(term.paint("Screenshot: %s" % path, term.GREY))

    # --- Commands -------------------------------------------------------------------------------

    def handle_command(self, line):
        try:
            words = shlex.split(line, posix=not term.IS_WINDOWS)
        except ValueError:
            words = line.split()
        command = words[0].lower()
        argument = line[len(words[0]):].strip()
        self.log.write("command", text=line)
        handlers = {
            "/help": self.cmd_help, "/new": self.cmd_new, "/state": self.cmd_state,
            "/screenshot": self.cmd_screenshot, "/image": self.cmd_image, "/paste": self.cmd_paste,
            "/model": self.cmd_model, "/think": self.cmd_think, "/undo": self.cmd_undo, "/reset": self.cmd_reset,
            "/verbose": self.cmd_verbose, "/screenshots": self.cmd_screenshots, "/open": self.cmd_open,
            "/doctor": self.cmd_doctor,
        }
        if command in ("/exit", "/quit"):
            return False
        handler = handlers.get(command)
        if handler is None:
            print("Unknown command %s. /help lists the commands." % command)
            return True
        try:
            handler(argument)
        except FusionUnavailable as error:
            self.report_fusion_lost(error)
        except OllamaError as error:
            print("Ollama: %s" % error)
        return True

    def cmd_help(self, argument):
        width = max(len(name) + len(args) + 1 for name, args, _ in COMMANDS)
        for name, args, text in COMMANDS:
            print("  %s  %s" % ((name + " " + args).strip().ljust(width), text))
        print()
        print("  Pictures: drag a file into this window or type its path; Alt+V or /paste takes the clipboard.")
        print("  Keys: Ctrl+C stops an answer (twice quits), Ctrl+C on an empty line or Ctrl+D quits.")

    def cmd_new(self, argument):
        self.open_new_design()

    def cmd_state(self, argument):
        if not self.ensure_design():
            return
        print(self.agent.describe().rstrip())

    def cmd_screenshot(self, argument):
        view = argument or "iso-top-right"
        if view not in fusion_scripts.VIEW_NAMES:
            print("Views: %s" % ", ".join(fusion_scripts.VIEW_NAMES))
            return
        if not self.ensure_design():
            return
        self.show_screenshot(view)

    def cmd_image(self, argument):
        if not argument:
            print("Usage: /image <path>  (or drag the file into this window)")
            return
        found = images.find_image_paths(argument)
        path = found[0][2] if found else os.path.expanduser(argument.strip().strip('"').strip("'"))
        try:
            attachment = images.load_image(path)
        except images.ImageError as error:
            print("Not attached: %s" % error)
            return
        self.attach_for_next_request([attachment])

    def cmd_paste(self, argument):
        try:
            attachments = images.grab_clipboard()
        except images.ImageError as error:
            print("Nothing attached: %s." % error)
            return
        self.attach_for_next_request(attachments)

    def attach_for_next_request(self, attachments):
        labels = []
        for attachment in attachments:
            if not attachment.source_path:
                self.save_attachment(attachment)
            labels.append(self.labels.add_image(attachment))
        self.pending_input = " ".join(labels) + " "
        print("Attached %s: now type what to do with it." % ", ".join(labels))

    def cmd_model(self, argument):
        if not argument:
            self.list_models()
            return
        self.switch_model(argument)

    def list_models(self):
        found = models.tool_models(self.ollama)
        if not found:
            print("No installed model can call tools.")
            return
        print_model_rows(found, current=self.settings["model"], numbered=False)
        print("Switch with /model <name>. The prompt was tuned on %s." % TUNED_MODEL)

    def switch_model(self, name):
        info = models.model_info(self.ollama, name)
        if info is None:
            print("%s is not installed. /model lists the installed models." % name)
            return
        if not info["has_tools"]:
            print("%s cannot call tools, so it cannot work in Fusion." % info["name"])
            return
        self.settings["model"] = info["name"]
        self.model_details = info
        self.agent.set_model(info["name"], info["has_vision"], info["has_thinking"])
        if self.agent.think and not info["has_thinking"]:
            self.agent.think = False
            print("%s cannot think: thinking is off." % info["name"])
        config.save_settings(self.settings)
        self.log.write("model", name=info["name"])
        print("Model: %s." % info["name"])
        if not info["has_vision"]:
            print("It has no vision: pictures and screenshots for the model are off.")
        if not info["is_tuned"] and not self.has_warned_untuned:
            self.has_warned_untuned = True
            print(term.paint("Note: the prompt and the CAD helpers were tuned on %s; other models may do worse."
                             % TUNED_MODEL, term.YELLOW))

    def parse_on_off(self, argument, name, current):
        value = argument.strip().lower()
        if value in ("on", "1", "yes"):
            return True
        if value in ("off", "0", "no"):
            return False
        if not value:
            print("%s is %s. Use /%s on|off." % (name.capitalize(), "on" if current else "off", name))
            return None
        print("Use /%s on|off." % name)
        return None

    def cmd_think(self, argument):
        value = self.parse_on_off(argument, "think", self.agent.think)
        if value is None:
            return
        if value and not self.agent.has_thinking:
            print("%s cannot think." % self.settings["model"])
            return
        self.agent.think = value
        self.settings["think"] = value
        config.save_settings(self.settings)
        if value:
            print("Thinking on: slower (about 1.5-3 minutes per part), more accurate for parts of many operations.")
        else:
            print("Thinking off.")

    def cmd_verbose(self, argument):
        value = self.parse_on_off(argument, "verbose", self.settings["verbose"])
        if value is None:
            return
        self.settings["verbose"] = value
        config.save_settings(self.settings)
        print("Scripts are %s." % ("shown" if value else "hidden"))

    def cmd_screenshots(self, argument):
        value = self.parse_on_off(argument, "screenshots", self.settings["screenshots"])
        if value is None:
            return
        self.settings["screenshots"] = value
        config.save_settings(self.settings)
        print("Screenshots after changes are %s." % ("on" if value else "off"))

    def cmd_reset(self, argument):
        self.agent.reset()
        self.undo_stack = []
        print("New conversation. The design stays as it is.")

    def cmd_undo(self, argument):
        count = 1
        if argument:
            try:
                count = int(argument)
            except ValueError:
                print("Usage: /undo [n]")
                return
        if count < 1:
            print("Usage: /undo [n]")
            return
        if not self.undo_stack:
            print("Nothing to undo in this conversation.")
            return
        count = min(count, len(self.undo_stack))
        if not self.ensure_design():
            return
        target = self.undo_stack[-count]
        if target["snapshot"] is None:
            print("Cannot undo: the state before that request was not recorded.")
            return
        must(self.fusion.run_script(fusion_scripts.restore_snapshot_script(target["snapshot"])), "undo")
        del self.undo_stack[-count:]
        del self.agent.messages[target["history_length"]:]
        current = self.agent.signature()
        self.log.write("undo", count=count)
        if current == target["start_signature"]:
            print("Undone: %s. The design is as it was before." % doctor.plural(count, "change"))
        else:
            print("Undone as far as possible, but the design differs from before (a change outside the "
                  "timeline?). Fusion's own Undo (Ctrl+Z) can go further back.")

    def cmd_open(self, argument):
        if self.last_picture is None:
            print("No screenshot yet. /screenshot takes one.")
            return
        try:
            open_in_viewer(self.last_picture)
        except OSError as error:
            print("Could not open it: %s" % error)

    def cmd_doctor(self, argument):
        results = doctor.Doctor(self.settings["model"]).run()
        doctor.print_results(results)
