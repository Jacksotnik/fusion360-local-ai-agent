"""Unit tests of the agent loop pieces that need neither Fusion nor Ollama."""
import os
import re
import traceback
import unittest
from unittest import mock

from fusion_agent import agent
from fusion_agent.cad_api import CAD_PRELUDE
from fusion_agent.ollama import base_url_from_env


def error_prelude():
    """The parts of the real CAD prelude that map errors to model lines, without the Fusion imports."""
    match = re.search(r"\ndef _report_model_error\(.*?\n(?=\S)", CAD_PRELUDE, re.DOTALL)
    return ("import sys as _sys_for_lines\nimport traceback as _traceback_for_lines\n"
            + match.group(0) + "\n\ndef helper_that_fails():\n    raise ValueError('helper said no')\n")


def run_wrapped(model_script):
    """Run a model script the way Fusion would and return the traceback text it reports."""
    wrapped = agent.wrap_script(model_script, error_prelude())
    namespace = {}
    exec(compile(wrapped, "<fusion script>", "exec"), namespace)
    try:
        namespace["run"]("")
    except Exception:
        return traceback.format_exc()
    return ""


class WrapScriptTest(unittest.TestCase):
    def test_bare_body_is_wrapped_into_run(self):
        wrapped = agent.wrap_script("box(1, 2, 3, corner=(0, 0, 0))", "PRELUDE")
        self.assertTrue(wrapped.startswith("PRELUDE"))
        self.assertIn("def run(_context: str):", wrapped)
        self.assertIn("        box(1, 2, 3, corner=(0, 0, 0))", wrapped)

    def test_script_with_own_run_is_kept(self):
        script = "def run(_context: str):\n    print(1)\n"
        self.assertEqual(agent.wrap_script(script, "PRELUDE"), "PRELUDE\n\n" + script)

    def test_error_reports_the_model_line(self):
        script = "a = 1\nb = 2\nc = 1 / 0\nd = 4"
        text = agent.short_error(run_wrapped(script), script)
        self.assertIn("line 3 of your script: c = 1 / 0", text)
        self.assertIn("ZeroDivisionError", text)
        self.assertTrue(text.startswith("Script failed."))

    def test_error_inside_a_helper_reports_the_calling_line(self):
        script = "x = 5\nhelper_that_fails()"
        text = agent.short_error(run_wrapped(script), script)
        self.assertIn("line 2 of your script: helper_that_fails()", text)
        self.assertIn("ValueError: helper said no", text)

    def test_error_on_the_first_line(self):
        script = "undefined_name + 1"
        text = agent.short_error(run_wrapped(script), script)
        self.assertIn("line 1 of your script: undefined_name + 1", text)
        self.assertIn("NameError", text)

    def test_error_without_model_line_keeps_the_message(self):
        traceback_text = 'Traceback (most recent call last):\n  File "x", line 3, in run\n    foo()\nRuntimeError: 3 : boom'
        self.assertEqual(agent.short_error(traceback_text, "foo()"), "Script failed.\nRuntimeError: 3 : boom")

    def test_empty_error_text(self):
        self.assertEqual(agent.short_error("", "foo()"), "Script failed.\nunknown error")


class StatePrefixTest(unittest.TestCase):
    def test_empty_design(self):
        prefix = agent.state_prefix("bodies: 0\n  timeline (0 steps): \n")
        self.assertEqual(prefix + "Сделай куб", "The design is empty.\n\nСделай куб")

    def test_design_with_a_body(self):
        state = "bodies: 1\n  Body1: volume 8000 mm3\n  timeline (2 steps): Sketch1, Extrude1 [d1=20.00 mm]\n"
        prefix = agent.state_prefix(state)
        self.assertTrue(prefix.startswith("Current design (describe()):\nbodies: 1\n"))
        self.assertTrue(prefix.endswith("Extrude1 [d1=20.00 mm]\n\n"))


class RepeatDetectorTest(unittest.TestCase):
    def call(self, script):
        return {"function": {"name": "fusion_script", "arguments": {"script": script}}}

    def test_same_call_and_same_output_is_a_repeat(self):
        detector = agent.RepeatDetector()
        self.assertFalse(detector.check(self.call("box()"), "CHECK FAILED"))
        self.assertTrue(detector.check(self.call("box()"), "CHECK FAILED"))

    def test_different_output_is_not_a_repeat(self):
        detector = agent.RepeatDetector()
        detector.check(self.call("box()"), "CHECK FAILED")
        self.assertFalse(detector.check(self.call("box()"), "CHECK OK"))

    def test_different_script_is_not_a_repeat(self):
        detector = agent.RepeatDetector()
        detector.check(self.call("box()"), "CHECK FAILED")
        self.assertFalse(detector.check(self.call("cylinder()"), "CHECK FAILED"))

    def test_only_the_previous_call_counts(self):
        detector = agent.RepeatDetector()
        detector.check(self.call("box()"), "out")
        detector.check(self.call("other()"), "out")
        self.assertFalse(detector.check(self.call("box()"), "out"))


class ToolsAndThinkingTest(unittest.TestCase):
    def test_tools_without_vision_have_no_screenshot(self):
        names = [tool["function"]["name"] for tool in agent.build_tools(has_vision=False)]
        self.assertEqual(names, ["fusion_script", "fusion_api_docs"])

    def test_tools_with_vision_match_the_bench(self):
        names = [tool["function"]["name"] for tool in agent.build_tools(has_vision=True)]
        self.assertEqual(names, ["fusion_script", "fusion_screenshot", "fusion_api_docs"])

    def test_strip_thinking_drops_only_assistant_thinking(self):
        messages = [{"role": "assistant", "content": "", "thinking": "hmm"},
                    {"role": "user", "content": "x", "thinking": "kept"}]
        agent.strip_thinking(messages)
        self.assertNotIn("thinking", messages[0])
        self.assertIn("thinking", messages[1])

    def test_truncate(self):
        self.assertEqual(agent.truncate("abc"), "abc")
        long_text = "x" * (agent.TOOL_OUTPUT_CHARS + 10)
        self.assertTrue(agent.truncate(long_text).endswith("[truncated, %d chars total]" % len(long_text)))

    def test_prompt_is_package_data(self):
        self.assertIn("CAD helper API", agent.load_prompt())


class OllamaHostTest(unittest.TestCase):
    def check(self, value, expected):
        with mock.patch.dict(os.environ, {"OLLAMA_HOST": value}):
            self.assertEqual(base_url_from_env(), expected)

    def test_default(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(base_url_from_env(), "http://127.0.0.1:11434")

    def test_forms(self):
        self.check("0.0.0.0", "http://127.0.0.1:11434")
        self.check("127.0.0.1:12345", "http://127.0.0.1:12345")
        self.check("http://gpu-box:11434", "http://gpu-box:11434")


class FakeFusion:
    def __init__(self):
        self.scripts = []

    def run_script(self, script, read_only=False):
        self.scripts.append(script)
        return True, "ok"


class DocumentGuardTest(unittest.TestCase):
    def run_model_script(self, script):
        fusion = FakeFusion()
        model_agent = agent.Agent(fusion, ollama=None, session_id="s", system_prompt="x")
        call = {"function": {"name": "fusion_script", "arguments": {"script": script}}}
        return model_agent.run_tool(call, []), fusion.scripts

    def test_scripts_that_touch_documents_never_reach_fusion(self):
        for script in ["app.documents.add(0)", "doc.save('x')", "doc.saveAs('a', None, '', '')",
                       "app.activeDocument.close(False)", "app.executeTextCommand('Commands.Start Undo')"]:
            output, sent = self.run_model_script(script)
            self.assertTrue(output.startswith("Error: this task does not allow working with documents"), script)
            self.assertEqual(sent, [], script)

    def test_a_normal_script_runs(self):
        output, sent = self.run_model_script("box(10, 10, 10, corner=(0, 0, 0))")
        self.assertEqual(output, "ok")
        self.assertEqual(len(sent), 1)


class ShortNameTest(unittest.TestCase):
    def test_short_names(self):
        from fusion_agent.models import short_name
        self.assertEqual(short_name("gemma4-12b:q8_0"), "gemma4-12b")
        self.assertEqual(short_name("gemma4-uncensored:e2b"), "gemma4-uncensored:e2b")
        self.assertEqual(short_name("gemma4-uncensored:26b"), "gemma4-uncensored:26b")
        self.assertEqual(short_name("hf.co/HauhauCS/Gemma4-12B-QAT:Q4_K_M"), "Gemma4-12B-QAT")
        self.assertEqual(short_name("hf.co/nvidia/Bolt-GGUF:latest"), "Bolt-GGUF")
        self.assertEqual(short_name("llama3.2"), "llama3.2")


if __name__ == "__main__":
    unittest.main()
