"""The session design in Fusion (marked with fusion-agent/session=<id>) and the session log."""
import json
import random
import time

from fusion_agent import fusion_scripts
from fusion_agent.agent import must


def new_session_id():
    return time.strftime("%Y%m%d-%H%M%S") + "-%04x" % random.randrange(0x10000)


class DesignSession:
    """Which Fusion document the app works in. It only ever works in the design it marked."""

    def __init__(self, fusion, session_id):
        self.fusion = fusion
        self.session_id = session_id
        self.design_name = None

    @property
    def has_design(self):
        return self.design_name is not None

    def active_info(self):
        """What the active document is (see fusion_scripts.ACTIVE_DOCUMENT_SCRIPT), or None."""
        is_success, text = self.fusion.run_script(fusion_scripts.ACTIVE_DOCUMENT_SCRIPT, read_only=True)
        if not is_success:
            return None
        try:
            return json.loads(text)
        except ValueError:
            return None

    def new_design(self, is_selftest=False):
        script = fusion_scripts.new_design_script(self.session_id, is_selftest=is_selftest)
        self.design_name = must(self.fusion.run_script(script), "new design").strip()
        return self.design_name

    def adopt_active(self):
        """Mark the active design as the session design (the user chose it)."""
        self.design_name = must(self.fusion.run_script(fusion_scripts.mark_active_script(self.session_id)),
                                "mark design").strip()
        return self.design_name

    def mark_user_steps(self):
        """Record the current timeline steps as the user's own part (the test runner builds such parts)."""
        return must(self.fusion.run_script(fusion_scripts.MARK_USER_STEPS_SCRIPT), "mark user steps").strip()

    def is_active(self):
        script = fusion_scripts.active_is_session_script(self.session_id)
        return must(self.fusion.run_script(script, read_only=True), "active check").strip() == "session"

    def activate(self):
        """Bring the session design back to the front; False when it was closed."""
        script = fusion_scripts.activate_session_script(self.session_id)
        name = must(self.fusion.run_script(script), "activate").strip()
        if name == "missing":
            self.design_name = None
            return False
        self.design_name = name
        return True

    def close_selftest_documents(self):
        script = fusion_scripts.close_selftest_documents_script(self.session_id)
        return must(self.fusion.run_script(script), "close self-test documents").strip()


class SessionLog:
    """JSONL log of one run: requests, scripts, results, answers and timings. Never breaks the session."""

    def __init__(self, folder):
        self.folder = folder
        self.path = folder / "log.jsonl"
        self.picture_count = 0

    def write(self, event, **fields):
        record = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event}
        record.update(fields)
        try:
            with open(self.path, "a", encoding="utf-8") as file:
                file.write(json.dumps(record, ensure_ascii=False) + "\n")
        except (OSError, TypeError, ValueError):
            pass

    def picture_path(self, prefix, extension="png"):
        self.picture_count += 1
        return self.folder / ("%s-%03d.%s" % (prefix, self.picture_count, extension))
