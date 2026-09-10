from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from analyze_workflow import analyze
from collect_cli_evidence import (
    DEFAULT_CLI_PYTHON,
    REPORT_NAME,
    collect,
    digest,
    write_json,
)

# Synthetic schema only. It does not claim to describe a user's installation.
INFO = {
    "EmptyLatentImage": {"input": {"required": {
        "width": ["INT", {"default": 512, "min": 16, "max": 16384}],
        "height": ["INT", {"default": 512, "min": 16, "max": 16384}],
        "batch_size": ["INT", {"default": 1, "min": 1, "max": 4096}]}},
        "output": ["LATENT"], "output_name": ["LATENT"], "output_node": False},
    "SaveLatent": {"input": {"required": {
        "samples": ["LATENT"], "filename_prefix": ["STRING", {"default": "latents/ComfyUI"}]}},
        "output": [], "output_name": [], "output_node": True},
}
API = {"1": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 768, "batch_size": 1}},
       "2": {"class_type": "SaveLatent", "inputs": {"samples": ["1", 0], "filename_prefix": "audit-fixture"}}}
UI = {"version": 0.4, "nodes": [
    {"id": 1, "type": "EmptyLatentImage", "mode": 0, "order": 0,
     "inputs": [], "outputs": [{"name": "LATENT", "type": "LATENT", "links": [1]}],
     "widgets_values": [512, 768, 1]},
    {"id": 2, "type": "SaveLatent", "mode": 0, "order": 1,
     "inputs": [{"name": "samples", "type": "LATENT", "link": 1}], "outputs": [],
     "widgets_values": ["audit-fixture"]},
    {"id": 3, "type": "Note", "mode": 0, "widgets_values": ["人工测试备注，不是生产工作流。"]}],
    "links": [[1, 1, 0, 2, 0, "LATENT"]], "groups": []}


class CliEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="comfy-cli-audit-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workflow = self.root / "workflow.json"
        self.schema = self.root / "object_info.json"
        write_json(self.schema, INFO)

    def run_case(self, value, **kwargs):
        write_json(self.workflow, value)
        return collect(self.workflow, self.root / "run", object_info=self.schema, **kwargs)

    def test_api_preflight_and_unchanged_inputs(self):
        report = self.run_case(API)
        self.assertTrue(report["tool_ready"])
        self.assertEqual(report["preflight_status"], "PASS")
        self.assertTrue(report["source_unchanged"])
        self.assertEqual(report["runtime_execution"], "not_performed")
        self.assertEqual(report["checks"]["notes"]["status"], "not_applicable")
        self.assertEqual(report["node_types_absent_from_supplied_schema"], [])

    def test_ui_notes_and_no_automatic_widget_naming(self):
        report = self.run_case(UI)
        self.assertEqual(report["preflight_status"], "PASS")
        self.assertEqual(report["checks"]["notes"]["response"]["data"]["count"], 1)
        _, coverage = analyze(self.workflow)
        self.assertGreaterEqual(coverage["unresolved_widget_count"], 4)
        self.assertTrue(report["checks"]["validate"]["response"]["data"]["converted_from_ui"])

    def test_unknown_node_is_not_hidden(self):
        data = copy.deepcopy(API)
        data["1"]["class_type"] = "DefinitelyMissingAuditNode"
        report = self.run_case(data)
        self.assertEqual(report["preflight_status"], "FAIL")
        self.assertIn("DefinitelyMissingAuditNode", report["node_types_absent_from_supplied_schema"])

    def test_broken_link_on_known_node(self):
        data = copy.deepcopy(API)
        data["2"]["inputs"]["samples"] = ["999", 0]
        report = self.run_case(data)
        self.assertEqual(report["preflight_status"], "FAIL")
        self.assertGreater(report["checks"]["validate"]["response"]["data"]["error_count"], 0)

    def test_unknown_node_dangling_candidate_is_retained(self):
        data = copy.deepcopy(API)
        data["2"]["class_type"] = "DefinitelyMissingAuditNode"
        data["2"]["inputs"]["samples"] = ["999", 0]
        report = self.run_case(data)
        self.assertEqual(report["candidate_dangling_links"][0]["referenced_node_id"], "999")
        self.assertEqual(report["candidate_dangling_links"][0]["status"], "candidate_dangling_link")

    def test_short_prompt_does_not_corrupt_version_or_hash(self):
        data = copy.deepcopy(API)
        data["1"]["inputs"]["text"] = "1"
        report = self.run_case(data)
        self.assertTrue(report["tool_ready"])
        self.assertEqual(report["checks"]["version"]["response"]["data"]["version"], "1.20.0")
        self.assertEqual(report["inputs_sha256"][str(self.workflow)], digest(self.workflow))

    def test_invalid_schema_still_produces_a_report(self):
        self.schema.write_text("{bad json", encoding="utf-8")
        report = self.run_case(API)
        self.assertEqual(report["object_info_status"], "invalid_input")
        self.assertEqual(report["preflight_status"], "NOT_VERIFIED")

    def test_prompt_equal_to_status_does_not_corrupt_protocol(self):
        data = copy.deepcopy(API)
        data["1"]["inputs"]["text"] = "not_performed"
        report = self.run_case(data)
        self.assertEqual(report["runtime_execution"], "not_performed")
        self.assertEqual(report["inputs_sha256"][str(self.workflow)], digest(self.workflow))

    def test_credentials_in_note_are_redacted(self):
        data = copy.deepcopy(UI)
        fake = "FAKE_NOT_A_REAL_PASSWORD"
        data["nodes"][2]["widgets_values"] = ["password=" + fake]
        self.run_case(data)
        for path in (self.root / "run").rglob("*.json"):
            self.assertNotIn(fake, path.read_text(encoding="utf-8"))
        parsed, coverage = analyze(self.workflow)
        self.assertNotIn(fake, json.dumps([parsed, coverage]))

    def test_no_schema_is_not_a_pass(self):
        write_json(self.workflow, API)
        report = collect(self.workflow, self.root / "run")
        self.assertEqual(report["preflight_status"], "NOT_VERIFIED")
        self.assertEqual(report["checks"]["validate"]["status"], "not_provided")

    def test_missing_cli_does_not_fake_evidence(self):
        report = self.run_case(API, cli_python=self.root / "nonexistent-python.exe")
        self.assertFalse(report["tool_ready"])
        self.assertEqual(report["preflight_status"], "NOT_VERIFIED")

    def test_existing_evidence_is_preserved(self):
        self.run_case(API)
        path = self.root / "run" / "02-机器解析" / REPORT_NAME
        old_hash = digest(path)
        with self.assertRaises(ValueError):
            collect(self.workflow, self.root / "run", object_info=self.schema)
        self.assertEqual(digest(path), old_hash)

    def test_named_secret_is_not_in_official_evidence(self):
        data = copy.deepcopy(API)
        fake_secret = "FAKE_TEST_CREDENTIAL_NEVER_REAL_9f29"
        data["1"]["inputs"]["api_key"] = fake_secret
        data["1"]["inputs"]["width"] = fake_secret
        self.run_case(data)
        for path in (self.root / "run").rglob("*.json"):
            self.assertNotIn(fake_secret, path.read_text(encoding="utf-8"))

    def test_dependencies_use_explicit_python(self):
        workspace = self.root / "synthetic-comfy"
        pack = workspace / "custom_nodes" / "AuditTestPack"
        pack.mkdir(parents=True)
        (pack / "requirements.txt").write_text("pip>=1\nnonexistent-audit-fixture-package>=999\n", encoding="utf-8")
        report = self.run_case(API, workspace=workspace, target_python=DEFAULT_CLI_PYTHON)
        dep = report["checks"]["dependencies"]
        self.assertEqual(dep["backend"], "official-library-build_report")
        self.assertEqual(Path(dep["response"]["data"]["python"]), DEFAULT_CLI_PYTHON)
        statuses = {r["name"]: r["status"] for r in dep["response"]["data"]["packs"][0]["requirements"]}
        self.assertEqual(statuses["pip"], "satisfied")
        self.assertEqual(statuses["nonexistent-audit-fixture-package"], "missing")

    def test_prepare_run_wires_evidence_ledger(self):
        write_json(self.workflow, API)
        command = [sys.executable, str(Path(__file__).with_name("prepare_run.py")),
                   str(self.workflow), str(self.root / "prepared"), "--object-info", str(self.schema)]
        result = subprocess.run(command, capture_output=True, env={**os.environ, "PYTHONUTF8": "1"}, timeout=45, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        summary = json.loads(result.stdout)
        self.assertEqual(summary["official_preflight"], "PASS")
        ledger = json.loads((self.root / "prepared" / "03-证据台账.json").read_text(encoding="utf-8"))
        record = next(r for r in ledger["records"] if r["id"] == "official-cli-preflight")
        self.assertEqual(record["sha256"], digest(self.root / "prepared" / record["path"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
