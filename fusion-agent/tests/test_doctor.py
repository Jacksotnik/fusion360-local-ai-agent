"""Unit tests of the startup checks that need neither Fusion nor Ollama."""
import unittest
from unittest import mock

from fusion_agent import doctor
from fusion_agent.fusion_mcp import FusionUnavailable

EMPTY_DESIGN = {"has_document": True, "name": "Untitled", "is_saved": False, "is_design": True,
                "is_design_workspace": True, "is_parametric": True, "bodies": 0, "sketches": 0,
                "occurrences": 0, "timeline": 0, "session": None}


def design(**changes):
    info = dict(EMPTY_DESIGN)
    info.update(changes)
    return info


class DocumentKindTest(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(doctor.document_kind(None), "unknown")
        self.assertEqual(doctor.document_kind({"has_document": False}), "none")
        self.assertEqual(doctor.document_kind(design(is_design=False)), "not_design")
        self.assertEqual(doctor.document_kind(design(is_design_workspace=False)), "other_workspace")
        self.assertEqual(doctor.document_kind(design(is_parametric=False)), "direct")
        self.assertEqual(doctor.document_kind(design()), "empty")
        self.assertEqual(doctor.document_kind(design(bodies=1, timeline=2)), "has_content")
        self.assertEqual(doctor.document_kind(design(sketches=1, timeline=1)), "has_content")

    def test_results(self):
        self.assertEqual(doctor.document_result(design()).status, doctor.OK)
        content = doctor.document_result(design(bodies=2, timeline=5))
        self.assertEqual(content.status, doctor.WARN)
        self.assertIn("2 bodies and 5 timeline steps", content.detail)
        self.assertIn("/new", doctor.document_result({"has_document": False}).hint[0])
        # A document problem never blocks the start: the user can type /new.
        for info in [None, {"has_document": False}, design(is_design=False), design(bodies=1, timeline=1)]:
            self.assertFalse(doctor.document_result(info).blocks_start)


class FusionCheckTest(unittest.TestCase):
    def run_check(self, is_running):
        with mock.patch.object(doctor, "is_fusion_process_running", return_value=is_running), \
                mock.patch.object(doctor, "FusionMcp", side_effect=FusionUnavailable("refused")):
            return doctor.Doctor().check_fusion()

    def test_fusion_not_running(self):
        results = self.run_check(False)
        self.assertEqual([result.status for result in results], [doctor.FAIL, doctor.SKIP])
        self.assertTrue(results[0].blocks_start)
        self.assertIn("Start Autodesk Fusion", results[0].hint[0])

    def test_fusion_running_but_mcp_off(self):
        results = self.run_check(True)
        self.assertEqual([result.status for result in results], [doctor.OK, doctor.FAIL])
        self.assertIn("Preferences", results[1].hint[0])
        self.assertIn("General > API", results[1].hint[1])

    def test_unknown_process_state_but_mcp_off(self):
        with mock.patch.object(doctor.term, "IS_WINDOWS", True):
            results = self.run_check(None)
        self.assertEqual(results[1].status, doctor.FAIL)


class WaitUntilReadyTest(unittest.TestCase):
    def test_retries_until_nothing_blocks(self):
        failing = [doctor.CheckResult("Ollama", doctor.FAIL, "down", is_blocking=True)]
        passing = [doctor.CheckResult("Ollama", doctor.OK, "up")]
        rounds = [failing, passing]
        presses = []
        with mock.patch.object(doctor.Doctor, "run", side_effect=lambda include_document: rounds.pop(0)), \
                mock.patch("builtins.print"), mock.patch.object(doctor, "print_results"):
            doctor.wait_until_ready("m", read_line=presses.append)
        self.assertEqual(len(presses), 1)
        self.assertEqual(rounds, [])


if __name__ == "__main__":
    unittest.main()
