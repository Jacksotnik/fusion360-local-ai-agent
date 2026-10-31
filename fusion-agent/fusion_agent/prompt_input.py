"""The prompt_toolkit input line: history, completion, labels for pictures and long pastes, keys."""
import os

from prompt_toolkit import PromptSession
from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.history import FileHistory, InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

from fusion_agent import config, fusion_scripts, images, models

ON_OFF_COMMANDS = ("/think", "/verbose", "/screenshots")


class LabelHistory(FileHistory):
    """Stores picture labels as their file paths, so a recalled request finds its pictures again."""

    def __init__(self, path, labels):
        super().__init__(str(path))
        self.labels = labels

    def append_string(self, string):
        super().append_string(self.labels.for_history(string))


class CommandCompleter(Completer):
    def __init__(self, app):
        self.app = app
        self.paths = PathCompleter(expanduser=True)

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/"):
            return
        if " " not in text:
            from fusion_agent.repl import COMMANDS
            for name, args, help_text in COMMANDS:
                if name.startswith(text.lower()):
                    yield Completion(name, start_position=-len(text), display_meta=help_text)
            return
        command, _, rest = text.partition(" ")
        command = command.lower()
        if command == "/image":
            sub_document = Document(rest, len(rest))
            for completion in self.paths.get_completions(sub_document, complete_event):
                yield completion
            return
        choices = []
        if command in ON_OFF_COMMANDS:
            choices = ["on", "off"]
        elif command == "/screenshot":
            choices = fusion_scripts.VIEW_NAMES
        elif command == "/model":
            choices = self.model_names()
        for choice in choices:
            if choice.startswith(rest):
                yield Completion(choice, start_position=-len(rest))

    def model_names(self):
        try:
            return [info["name"] for info in models.tool_models(self.app.ollama)]
        except Exception:
            return []


def build_prompt_session(app):
    labels = app.labels
    bindings = KeyBindings()

    def say(text):
        run_in_terminal(lambda: print(text))

    def attach_clipboard(event):
        try:
            attachments = images.grab_clipboard()
        except images.ImageError as error:
            say("Nothing attached: %s." % error)
            return
        for attachment in attachments:
            app.save_attachment(attachment)
            event.current_buffer.insert_text(labels.add_image(attachment) + " ")

    @bindings.add("escape", "v")
    def _alt_v(event):
        attach_clipboard(event)

    @bindings.add("c-v")
    def _ctrl_v(event):
        attach_clipboard(event)

    @bindings.add(Keys.BracketedPaste)
    def _paste(event):
        data = event.data.replace("\r\n", "\n").replace("\r", "\n")
        if data.endswith("\n"):
            data = data[:-1]
        bare_path = data.strip().strip('"')
        if bare_path.lower().endswith(images.IMAGE_EXTENSIONS) and os.path.isfile(bare_path):
            # A dropped or pasted path with spaces but without quotes: quote it so it is read as one path.
            event.current_buffer.insert_text('"%s" ' % bare_path)
            return
        if data.count("\n") + 1 > 3:
            event.current_buffer.insert_text(labels.add_paste(data))
            return
        event.current_buffer.insert_text(data.replace("\n", "↵"))

    @bindings.add("c-c")
    def _ctrl_c(event):
        buffer = event.current_buffer
        if buffer.text:
            buffer.reset()
            return
        event.app.exit(exception=KeyboardInterrupt())

    try:
        config.data_dir().mkdir(parents=True, exist_ok=True)
        history = LabelHistory(config.history_path(), labels)
    except OSError:
        history = InMemoryHistory()

    session = PromptSession(history=history, completer=CommandCompleter(app), key_bindings=bindings,
                            complete_while_typing=True, enable_open_in_editor=False)

    def relabel(buffer):
        """A picture path typed or dropped into the line becomes a label like [Image: part.png]."""
        if buffer.text.lstrip().startswith("/"):
            return  # commands such as /image take the path itself
        found = images.find_image_paths(buffer.text)
        if not found:
            return
        text = buffer.text
        cursor = buffer.cursor_position
        has_change = False
        for start, end, path in reversed(found):
            try:
                attachment = images.load_image(path)
            except images.ImageError as error:
                if path not in labels.rejected_paths:
                    labels.rejected_paths.add(path)
                    say("Not attached: %s" % error)
                continue
            label = labels.add_image(attachment)
            text = text[:start] + label + text[end:]
            if cursor >= end:
                cursor += len(label) - (end - start)
            elif cursor > start:
                cursor = start + len(label)
            has_change = True
        if has_change:
            buffer.document = Document(text, min(cursor, len(text)))

    session.default_buffer.on_text_changed += relabel
    return session
