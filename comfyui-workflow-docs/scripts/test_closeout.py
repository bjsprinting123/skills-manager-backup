import copy
from pathlib import Path
import tempfile
import unittest
from validate_closeout import AREAS, initial_checklist, validate


class CloseoutTests(unittest.TestCase):
    def setUp(self):
        self.data = {"scope": "evidence supplement", "destinations": [
            {"area": a, "status": "no_change", "reason": "checked; no new evidence"} for a in sorted(AREAS)]}

    def test_checked_no_change_closes(self):
        self.assertEqual(validate(self.data)["status"], "PASS_CLOSED")

    def test_initial_run_never_claims_knowledge_complete(self):
        result = validate(initial_checklist("json_only"))
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(set(result["pending"]), AREAS)

    def test_prepare_run_emits_pending_checklist(self):
        import json
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "workflow.json"
            source.write_text(json.dumps({"nodes": [], "links": []}), encoding="utf-8")
            run = Path(folder) / "run"
            result = subprocess.run([sys.executable, "-X", "utf8",
                str(Path(__file__).with_name("prepare_run.py")), str(source), str(run),
                "--no-official-cli"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary["knowledge_closeout"], "PENDING_REVIEW")
            checklist = json.loads((run / "98-知识回写核对.json").read_text(encoding="utf-8"))
            self.assertEqual(validate(checklist)["status"], "PARTIAL")

    def test_summary_only_cannot_hide_missing_destinations(self):
        self.data["destinations"] = []
        self.assertEqual(validate(self.data)["status"], "FAIL")

    def test_pending_research_is_partial(self):
        self.data["destinations"][0].update(status="pending_research", owner="model library", next_action="verify exact version")
        self.assertEqual(validate(self.data)["status"], "PARTIAL")

    def test_pending_permission_needs_action(self):
        self.data["destinations"][0]["status"] = "pending_approval"
        self.assertEqual(validate(self.data)["status"], "FAIL")

    def test_duplicate_area_fails(self):
        self.data["destinations"].append(copy.deepcopy(self.data["destinations"][0]))
        self.assertEqual(validate(self.data)["status"], "FAIL")

    def test_published_requires_receipt(self):
        entry = next(e for e in self.data["destinations"] if e["area"] == "model_library")
        with tempfile.TemporaryDirectory() as folder:
            evidence = Path(folder) / "index.json"
            evidence.write_text("{}")
            entry.update(status="updated", evidence_paths=[str(evidence)])
            self.assertEqual(validate(self.data)["status"], "FAIL")
            entry["receipt_paths"] = [str(evidence)]
            self.assertEqual(validate(self.data)["status"], "PASS_CLOSED")

    def test_deleted_evidence_fails(self):
        self.data["destinations"][0].update(status="updated", evidence_paths=["missing.json"])
        self.assertEqual(validate(self.data)["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
