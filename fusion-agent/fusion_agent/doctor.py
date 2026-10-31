"""Startup checks. Each prints OK or a short, numbered, OS-specific hint (`fusion-agent doctor`)."""
import json
import os
import platform
import subprocess
import sys

from fusion_agent import fusion_scripts, models, term
from fusion_agent.agent import TUNED_MODEL
from fusion_agent.fusion_mcp import FUSION_URL, FusionMcp, FusionUnavailable
from fusion_agent.ollama import Ollama, OllamaError

OK, WARN, FAIL, SKIP = "ok", "warn", "fail", "skip"


def fusion_url():
    return os.environ.get("FUSION_MCP_URL", FUSION_URL)


class CheckResult:
    def __init__(self, name, status, detail, hint=None, is_blocking=False, code=""):
        self.name = name
        self.status = status
        self.detail = detail
        self.hint = hint or []
        self.is_blocking = is_blocking
        self.code = code

    @property
    def blocks_start(self):
        return self.is_blocking and self.status == FAIL


# --- Hints ----------------------------------------------------------------------------------------

def ollama_hint(base_url):
    if term.IS_MAC:
        steps = ["Open the Ollama app (in Applications), or run in a terminal: ollama serve",
                 "Not installed? Download it from https://ollama.com/download/mac"]
    elif term.IS_WINDOWS:
        steps = ["Start Ollama from the Start menu (it then runs in the tray), or run in a terminal: ollama serve",
                 "Not installed? Download it from https://ollama.com/download/windows"]
    else:
        steps = ["Start Ollama: ollama serve (or: systemctl start ollama)",
                 "Not installed? See https://ollama.com/download/linux"]
    if base_url != "http://127.0.0.1:11434":
        steps.append("The app looks for Ollama at %s (from OLLAMA_HOST)." % base_url)
    return steps


MODEL_UNUSABLE = "model_unusable"


def model_hint(usable_models):
    """The app installs nothing: it names what is needed and what is installed already."""
    if usable_models:
        names = [info["name"] for info in usable_models]
        shown = ", ".join(names[:8]) + (", ..." if len(names) > 8 else "")
        return ["Pick an installed model that can call tools: fusion-agent --model <name>",
                "Installed: %s" % shown]
    return ["Install a model in Ollama that can call tools; it also needs vision for pictures and screenshots.",
            "Recommended: Gemma 4 12B: the prompt and the CAD helpers were tuned on it (as %s)." % TUNED_MODEL,
            "Then run the check again."]


FUSION_START_HINT =["Start Autodesk Fusion and wait until it has fully opened (signed in, a design visible)."]

# From Autodesk's help ("Connecting to the Fusion MCP server") and the Fusion blog
# ("Build Your Own Fusion Add-ins with the Fusion MCP"): Preferences > General > API.
MCP_ENABLE_HINT = [
    "In Fusion, click your profile name in the upper-right corner > Preferences.",
    "Open General > API.",
    "Under \"Preferences for Scripting and Programming\", tick \"Fusion MCP Server\"; the port must be 27182.",
    "Click Apply, then OK, and run the check again.",
]

NEW_DESIGN_HINT = ["In Fusion: File > New Design, or type /new here (the app opens one itself)."]


def run_command(args):
    """(exit code, stdout) of a small system command, or None when it cannot run. The output is
    decoded leniently: Windows tools write in the console code page, and only ASCII is read here."""
    try:
        completed = subprocess.run(args, capture_output=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.returncode, completed.stdout.decode("utf-8", errors="replace")


def gpu_memory_mib():
    """(free, total) MiB of the NVIDIA GPU with the most free memory, or None without nvidia-smi."""
    result = run_command(["nvidia-smi", "--query-gpu=memory.free,memory.total", "--format=csv,noheader,nounits"])
    if result is None or result[0] != 0:
        return None
    best = None
    for line in result[1].strip().splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 2:
            continue
        try:
            free, total = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        if best is None or free > best[0]:
            best = (free, total)
    return best


def mac_memory_bytes():
    result = run_command(["sysctl", "-n", "hw.memsize"])
    if result is None:
        return None
    try:
        return int(result[1].strip())
    except ValueError:
        return None


def is_fusion_process_running():
    """True / False, or None when this OS has no Fusion (Linux)."""
    if term.IS_WINDOWS:
        result = run_command(["tasklist", "/FI", "IMAGENAME eq Fusion360.exe", "/NH"])
        if result is None:
            return None
        return "fusion360.exe" in result[1].lower()
    if term.IS_MAC:
        # The app was renamed from "Autodesk Fusion 360" to "Autodesk Fusion": match both.
        result = run_command(["pgrep", "-f", "Autodesk Fusion"])
        if result is None:
            return None
        return result[0] == 0
    return None


# --- The checks -----------------------------------------------------------------------------------

class Doctor:
    """Runs the checks in order; later checks are skipped when what they need failed."""

    def __init__(self, model=TUNED_MODEL):
        self.model = model
        self.ollama = Ollama()
        self.fusion = None
        self.model_details = None
        self.usable_models = []
        self.document = None

    def run(self, include_document=True):
        results = [self.check_python()]
        ollama_result = self.check_ollama()
        results.append(ollama_result)
        if ollama_result.status == OK:
            model_result = self.check_model()
            results.append(model_result)
            if model_result.status in (OK, WARN):
                results.append(self.check_memory())
        else:
            results.append(CheckResult("Model", SKIP, "needs Ollama"))
        results.extend(self.check_fusion())
        if include_document and self.fusion is not None:
            results.append(self.check_document())
        return results

    def check_python(self):
        version = "%d.%d.%d" % sys.version_info[:3]
        if sys.version_info < (3, 10):
            return CheckResult("Python", FAIL, "Python %s is too old" % version,
                               ["Install Python 3.10 or newer and run the launcher again."], is_blocking=True)
        return CheckResult("Python", OK, "Python %s" % version)

    def check_ollama(self):
        try:
            version = self.ollama.version()
        except OllamaError:
            return CheckResult("Ollama", FAIL, "Ollama does not answer at %s" % self.ollama.base_url,
                               ollama_hint(self.ollama.base_url), is_blocking=True)
        return CheckResult("Ollama", OK, "Ollama %s at %s" % (version, self.ollama.base_url))

    def check_model(self):
        try:
            details = models.model_info(self.ollama, self.model)
            if details is None or not details["has_tools"]:
                self.usable_models = models.tool_models(self.ollama)
        except OllamaError as error:
            return CheckResult("Model", FAIL, "could not read the models: %s" % error, is_blocking=True)
        if details is None or not details["has_tools"]:
            if details is None:
                detail = "%s is not installed in Ollama" % self.model
            else:
                detail = "%s cannot call tools" % self.model
            return CheckResult("Model", FAIL, detail, model_hint(self.usable_models), is_blocking=True,
                               code=MODEL_UNUSABLE)
        self.model_details = details
        size = models.gigabytes(details["size"])
        if not details["has_vision"]:
            return CheckResult("Model", WARN, "%s (%s): no vision, so pictures and screenshots are off" % (
                self.model, size))
        note = "" if details["is_tuned"] else "; the prompt was tuned on %s" % TUNED_MODEL
        return CheckResult("Model", OK, "%s (%s), tools and vision%s" % (self.model, size, note))

    def check_memory(self):
        size = self.model_details["size"] if self.model_details else 0
        try:
            loaded = self.ollama.ps()
        except OllamaError:
            loaded = []
        for entry in loaded:
            if models.normalize(str(entry.get("name", ""))) != models.normalize(self.model):
                continue
            total = int(entry.get("size") or 0)
            in_vram = int(entry.get("size_vram") or 0)
            if total and in_vram >= total:
                return CheckResult("Memory", OK, "the model is loaded, fully in GPU memory (%s)" % models.gigabytes(total))
            share = 100 * in_vram // total if total else 0
            return CheckResult("Memory", WARN, "the model is loaded, only %d%% in GPU memory: answers will be slow" % share,
                               ["Close other programs that use the GPU, or pick a smaller model (/model)."])
        # About 1 GB on top of the weights for the 32K context (measured: 13.4 GB for a 12.7 GB file).
        need = size + 1_000_000_000
        if term.IS_MAC:
            total = mac_memory_bytes()
            if total is None:
                return CheckResult("Memory", SKIP, "could not read the memory size")
            if need > 0.65 * total:
                return CheckResult("Memory", WARN, "the model needs about %s, the Mac has %s in all" % (
                    models.gigabytes(need), models.gigabytes(total)),
                    ["It may not fit next to Fusion; close other programs or pick a smaller model (/model)."])
            return CheckResult("Memory", OK, "about %s needed, %s unified memory" % (
                models.gigabytes(need), models.gigabytes(total)))
        gpu = gpu_memory_mib()
        if gpu is None:
            return CheckResult("Memory", SKIP, "no NVIDIA GPU found (nvidia-smi): the model may run on the CPU, slowly")
        free_bytes = gpu[0] * 1024 * 1024
        if need > free_bytes:
            return CheckResult("Memory", WARN, "the model needs about %s, the GPU has %s free" % (
                models.gigabytes(need), models.gigabytes(free_bytes)),
                ["Part of it will run on the CPU and be slow. Close other programs that use the GPU."])
        return CheckResult("Memory", OK, "about %s needed, %s free on the GPU" % (
            models.gigabytes(need), models.gigabytes(free_bytes)))

    def check_fusion(self):
        """Fusion process, MCP server and a script round trip."""
        is_running = is_fusion_process_running()
        url = fusion_url()
        try:
            self.fusion = FusionMcp(url, connect_timeout_sec=5)
            mcp_error = None
        except (FusionUnavailable, RuntimeError, ValueError) as error:
            self.fusion = None
            mcp_error = str(error)

        results = []
        if self.fusion is not None:
            results.append(CheckResult("Fusion", OK, "running"))
            results.append(CheckResult("Fusion MCP", OK, "answers at %s" % url))
        elif is_running is False:
            results.append(CheckResult("Fusion", FAIL, "Autodesk Fusion is not running", FUSION_START_HINT,
                                       is_blocking=True))
            results.append(CheckResult("Fusion MCP", SKIP, "needs Fusion"))
            return results
        elif is_running is None and not (term.IS_WINDOWS or term.IS_MAC):
            results.append(CheckResult("Fusion", FAIL, "Autodesk Fusion runs only on Windows and macOS",
                                       ["Run fusion-agent on the computer where Fusion runs."], is_blocking=True))
            results.append(CheckResult("Fusion MCP", SKIP, "needs Fusion"))
            return results
        else:
            results.append(CheckResult("Fusion", OK, "running"))
            hint = list(MCP_ENABLE_HINT)
            if url != FUSION_URL:
                hint.append("The app looks for the MCP server at %s (from FUSION_MCP_URL)." % url)
            results.append(CheckResult("Fusion MCP", FAIL, "Fusion runs, but its MCP server does not answer at %s" % url,
                                       hint, is_blocking=True))
            return results

        results.append(self.check_round_trip())
        return results

    def check_round_trip(self):
        try:
            is_success, text = self.fusion.run_script(fusion_scripts.ROUND_TRIP_SCRIPT, read_only=True)
        except (FusionUnavailable, RuntimeError) as error:
            self.fusion = None
            return CheckResult("Script run", FAIL, "a test script failed: %s" % error,
                               ["Restart Fusion and run the check again."], is_blocking=True)
        if is_success and fusion_scripts.ROUND_TRIP_MARKER in text:
            return CheckResult("Script run", OK, "a test script ran and its output came back")
        self.fusion = None
        if is_success:
            return CheckResult("Script run", FAIL, "a test script ran, but its output was lost",
                               ["Fusion's MCP lost the script output. Restart Fusion and run the check again."],
                               is_blocking=True)
        return CheckResult("Script run", FAIL, "a test script failed: %s" % text.strip()[:200],
                           ["Restart Fusion and run the check again."], is_blocking=True)

    def check_document(self):
        try:
            is_success, text = self.fusion.run_script(fusion_scripts.ACTIVE_DOCUMENT_SCRIPT, read_only=True)
            info = json.loads(text) if is_success else None
        except (FusionUnavailable, RuntimeError, ValueError):
            info = None
        self.document = info
        return document_result(info)


def document_kind(info):
    """One word for what the active document is, as far as the app is concerned."""
    if info is None:
        return "unknown"
    if not info.get("has_document"):
        return "none"
    if not info.get("is_design"):
        return "not_design"
    if not info.get("is_design_workspace"):
        return "other_workspace"
    if not info.get("is_parametric"):
        return "direct"
    is_empty = not info.get("bodies") and not info.get("sketches") and not info.get("timeline") \
        and not info.get("occurrences")
    if is_empty:
        return "empty"
    return "has_content"


def plural(count, word, plural_word=None):
    if count == 1:
        return "1 " + word
    return "%d %s" % (count, plural_word or word + "s")


def document_result(info):
    kind = document_kind(info)
    name = (info or {}).get("name", "")
    if kind == "unknown":
        return CheckResult("Design", FAIL, "could not read the active document", ["Restart Fusion and try again."])
    if kind == "none":
        return CheckResult("Design", WARN, "no document is open in Fusion", NEW_DESIGN_HINT)
    if kind == "not_design":
        return CheckResult("Design", WARN, "the active document \"%s\" is not a design (a drawing?)" % name,
                           NEW_DESIGN_HINT)
    if kind == "other_workspace":
        return CheckResult("Design", WARN, "Fusion is not in the Design workspace",
                           ["Switch to DESIGN in the workspace menu at the top left of Fusion, or type /new."])
    if kind == "direct":
        return CheckResult("Design", WARN, "\"%s\" does not keep the design history (direct modeling)" % name,
                           ["The app needs the timeline: type /new for a new parametric design."])
    if kind == "empty":
        return CheckResult("Design", OK, "\"%s\" is an empty design: the app will work in it" % name)
    return CheckResult("Design", WARN, "\"%s\" already has %s and %s" % (
        name, plural(info.get("bodies", 0), "body", "bodies"), plural(info.get("timeline", 0), "timeline step")),
        ["The app asks before working in it. For a clean start: File > New Design, or type /new."])


def print_results(results, stream=None):
    stream = stream or sys.stdout
    width = max(len(result.name) for result in results)
    for result in results:
        stream.write("%s %s  %s\n" % (term.status_mark(result.status), result.name.ljust(width), result.detail))
        for number, step in enumerate(result.hint, start=1):
            stream.write("    %d. %s\n" % (number, step))
    stream.flush()


def wait_until_ready(model, read_line=input, include_document=True, choose_model=None):
    """Run the checks until nothing blocks the start; between rounds wait for Enter. When only the model
    is the problem and usable models are installed, choose_model(models) may pick one (None = no pick).
    Returns the Doctor of the passing round (it holds the Fusion connection, the model and the document)."""
    while True:
        doctor = Doctor(model)
        results = doctor.run(include_document=include_document)
        blocking = [result for result in results if result.blocks_start]
        if not blocking:
            print_results([result for result in results if result.status != OK or result.name in ("Model", "Design")])
            return doctor
        print_results(results)
        is_only_the_model = len(blocking) == 1 and blocking[0].code == MODEL_UNUSABLE
        if is_only_the_model and doctor.usable_models and choose_model is not None:
            chosen = choose_model(doctor.usable_models)
            if chosen:
                model = chosen
                continue
        print("Fix the items marked %s, then press Enter to check again (Ctrl+C quits)." % term.SYMBOLS["fail"])
        read_line("")


def run_doctor(model):
    """`fusion-agent doctor`: print every check; exit code 1 when a blocking one failed."""
    print("fusion-agent checks (%s %s)" % (platform.system(), platform.release()))
    results = Doctor(model).run()
    print_results(results)
    if any(result.blocks_start for result in results):
        print("Fix the items marked %s and run the check again." % term.SYMBOLS["fail"])
        return 1
    print("All set.")
    return 0
