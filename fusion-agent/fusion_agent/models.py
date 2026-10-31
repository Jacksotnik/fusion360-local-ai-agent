"""Which Ollama models are installed and what they can do."""
import re

from fusion_agent.agent import TUNED_MODEL
from fusion_agent.ollama import capabilities


def normalize(name):
    """Ollama treats "name" and "name:latest" as the same model."""
    name = name.strip()
    if ":" not in name.split("/")[-1]:
        return name + ":latest"
    return name


QUANT_TAG = re.compile(r"^(i?q\d\w*|f16|fp16|bf16|f32|latest)$", re.IGNORECASE)


def short_name(name):
    """A short label for the prompt: the last path part; the tag is dropped only when it is just the
    quantization or "latest" ("gemma4-12b:q8_0" -> "gemma4-12b", "gemma4-uncensored:e2b" stays)."""
    last = name.split("/")[-1]
    base, _, tag = last.partition(":")
    if not tag or QUANT_TAG.match(tag):
        return base or name
    return last


def find_installed(installed, name):
    """The /api/tags entry of a model, or None."""
    wanted = normalize(name).lower()
    for entry in installed:
        entry_name = str(entry.get("name") or entry.get("model") or "")
        if normalize(entry_name).lower() == wanted:
            return entry
    return None


def model_info(ollama, name, installed=None):
    """Name, size and capabilities of an installed model, or None when it is not installed."""
    if installed is None:
        installed = ollama.tags()
    entry = find_installed(installed, name)
    if entry is None:
        return None
    found = capabilities(ollama.show(name))
    return {
        "name": str(entry.get("name") or name),
        "size": int(entry.get("size") or 0),
        "capabilities": found,
        "has_tools": "tools" in found,
        "has_vision": "vision" in found,
        "has_thinking": "thinking" in found,
        "is_tuned": normalize(name) == normalize(TUNED_MODEL),
    }


def tool_models(ollama):
    """Every installed model that can call tools, the tuned one first."""
    installed = ollama.tags()
    result = []
    for entry in installed:
        name = str(entry.get("name") or entry.get("model") or "")
        if not name:
            continue
        info = model_info(ollama, name, installed)
        if info is not None and info["has_tools"]:
            result.append(info)
    result.sort(key=lambda info: (not info["is_tuned"], info["name"]))
    return result


def gigabytes(size_bytes):
    return "%.1f GB" % (size_bytes / 1e9)
