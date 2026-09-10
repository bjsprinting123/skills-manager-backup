from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analyze_workflow import analyze
from model_handoff import (
    REPORT_NAME,
    _artifact_form,
    _reference_role,
    build_report,
    create_report,
    extract_candidates,
)


SHA_A = "a" * 64
API = {
    "1": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "publisher\\model-a.safetensors"},
    },
    "2": {
        "class_type": "LoraLoader",
        "inputs": {"lora_name": "missing-lora.safetensors", "strength_model": 0.8},
    },
    "3": {
        "class_type": "VAEModelLoader",
        "inputs": {"model_name": "duplicate.safetensors"},
    },
    "4": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "please load fake-model.safetensors from https://example.invalid/x"},
    },
    "5": {
        "class_type": "LoadImage",
        "inputs": {"image": "portrait.png", "filename": "portrait.png"},
    },
    "6": {
        "class_type": "LoraLoader",
        "inputs": {"lora_name": "https://example.invalid/not-a-reference.safetensors"},
    },
}


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def model(
    model_id: str,
    aliases: list[str],
    *,
    sha256: str | None = None,
    version: str | None = None,
    remote_file: str | None = None,
    model_role: str = "unknown",
    artifact_form: str = "single_file",
) -> dict:
    return {
        "model_id": model_id,
        "aliases": aliases,
        "publisher": "fixture-publisher",
        "version": version,
        "remote_file": remote_file,
        "sha256": sha256,
        "status": "partial",
        "model_role": model_role,
        "artifact_form": artifact_form,
        "current_revision": "fixture-revision",
        "paths": [f"模型卡/{model_id}.md"],
    }


class ModelHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="model-handoff-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workflow = self.root / "workflow.json"
        self.library = self.root / "model-library"
        self.index_path = self.library / "索引数据" / "model-index.json"
        write_json(self.workflow, API)
        self.parsed, self.coverage = analyze(self.workflow)

    def set_index(self, models: list[dict]) -> None:
        write_json(self.index_path, {"schema_version": 1, "models": models})

    def test_matched_missing_and_ambiguous_are_separate(self):
        self.set_index(
            [
                model("model-a", ["model-a.safetensors"], sha256=SHA_A, model_role="checkpoint"),
                model("duplicate-v1", ["duplicate.safetensors"], version="v1"),
                model("duplicate-v2", ["duplicate.safetensors"], version="v2"),
            ]
        )
        report = build_report(self.parsed, self.coverage, self.library, run_id="run-1")
        by_reference = {row["raw_reference"]: row for row in report["results"]}
        self.assertEqual(by_reference["publisher\\model-a.safetensors"]["status"], "matched")
        self.assertEqual(by_reference["missing-lora.safetensors"]["status"], "missing")
        self.assertEqual(by_reference["duplicate.safetensors"]["status"], "ambiguous")
        self.assertEqual(report["summary"]["missing_request_count"], 1)
        self.assertEqual(report["summary"]["resolution_request_count"], 1)
        request = report["missing_requests"][0]
        self.assertEqual(request["node_key"], "api/2")
        self.assertEqual(request["model_role"], "lora")
        self.assertEqual(request["artifact_form"], "single_file")
        self.assertEqual(request["known_hints"]["reference_role_hint"], "lora")
        self.assertEqual(request["publication_owner"], "comfyui-model-library")
        resolution = report["resolution_requests"][0]
        self.assertEqual(resolution["candidate_model_ids"], ["duplicate-v1", "duplicate-v2"])
        self.assertEqual(resolution["model_role"], "unknown")
        self.assertEqual(report["phase_statuses"]["research"], "not_performed")
        self.assertEqual(report["phase_statuses"]["publish"], "not_performed")

    def test_full_sha256_has_priority(self):
        data = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": SHA_A}}}
        write_json(self.workflow, data)
        parsed, coverage = analyze(self.workflow)
        self.set_index([model("hash-match", ["different-name.safetensors"], sha256=SHA_A)])
        result = build_report(parsed, coverage, self.library)["results"][0]
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["match_method"], "full_sha256")

    def test_unresolved_ui_widgets_are_never_candidates(self):
        ui = {
            "version": 0.4,
            "nodes": [
                {
                    "id": 1,
                    "type": "CheckpointLoaderSimple",
                    "widgets_values": ["unresolved-model.safetensors"],
                }
            ],
            "links": [],
            "groups": [],
        }
        write_json(self.workflow, ui)
        parsed, coverage = analyze(self.workflow)
        self.assertEqual(coverage["unresolved_widget_count"], 1)
        self.assertEqual(extract_candidates(parsed, coverage), [])

    def test_false_positive_filters_prompt_url_and_ordinary_image(self):
        references = {row["raw_reference"] for row in extract_candidates(self.parsed, self.coverage)}
        self.assertNotIn("portrait.png", references)
        self.assertFalse(any(value.startswith("http") for value in references))
        self.assertFalse(any("please load" in value for value in references))
        self.assertEqual(
            references,
            {"publisher\\model-a.safetensors", "missing-lora.safetensors", "duplicate.safetensors"},
        )

    def nested_fixture(self, inputs, node_type="Power Lora Loader (rgthree)"):
        write_json(self.workflow, {"1": {"class_type": node_type, "inputs": inputs}})
        return analyze(self.workflow)

    def test_nested_lora_keeps_slot_identity_and_saved_controls_in_requests(self):
        parsed, coverage = self.nested_fixture({
            "lora_1": {"on": True, "lora": "same.safetensors", "strength": 0.8},
            "lora_2": {"on": False, "lora": "same.safetensors", "strength": 1, "strengthTwo": 0.2},
        })
        self.set_index([])
        before = self.index_path.read_bytes()
        report = build_report(parsed, coverage, self.library, run_id="nested-test")
        results = report["results"]
        self.assertEqual([r["parameter"] for r in results], ["lora_1.lora", "lora_2.lora"])
        self.assertEqual(len({r["candidate_id"] for r in results}), 2)
        self.assertEqual(len({r["request_id"] for r in report["missing_requests"]}), 2)
        hints = report["missing_requests"][1]["known_hints"]
        self.assertEqual(hints["source_parameter"], "lora_2")
        self.assertEqual(hints["saved_lora_controls"], {"on": False, "strength": 1, "strengthTwo": 0.2})
        self.assertEqual(hints["node_mode_state"], "not_recorded")
        self.assertEqual(hints["runtime_usage"], "not_verified")
        self.assertEqual(self.index_path.read_bytes(), before)

    def test_nested_lora_bypass_never_and_normal_are_not_runtime_claims(self):
        parsed, coverage = self.nested_fixture({
            "lora_1": {"on": True, "lora": "a.safetensors", "strength": 0, "strengthTwo": 0},
        })
        for mode, state in ((0, "normal_or_parser_default"), (2, "never"), (4, "bypassed")):
            with self.subTest(mode=mode):
                parsed["nodes"][0]["mode"] = mode
                result = extract_candidates(parsed, coverage)[0]
                self.assertEqual(result["known_hints"]["node_mode_state"], state)
                self.assertEqual(result["known_hints"]["runtime_usage"], "not_verified")
                self.assertEqual(result["known_hints"]["local_file_presence"], "not_checked")

    def test_nested_lora_requires_known_type_schema_and_named_unredacted_row(self):
        slot = {"on": True, "lora": "a.safetensors", "strength": 1}
        for node_type in ("Power Lora Loader (rgthree)", "UnverifiedLoraLoader"):
            parsed, coverage = self.nested_fixture({"lora_1": slot}, node_type)
            self.assertEqual(len(extract_candidates(parsed, coverage)), int(node_type.startswith("Power")))
        parsed, coverage = self.nested_fixture({
            "lora_1": {"lora": "a.safetensors"},
            "lora_2": "not-an-object.safetensors",
            "notes": slot,
            "lora_3": {**slot, "lora": {"filename": "a.safetensors"}},
            "lora_4": {**slot, "lora": "https://example.invalid/a.safetensors"},
        })
        self.assertEqual(extract_candidates(parsed, coverage), [])
        for override in ({"redacted": True}, {"mapping_status": "unresolved"}, {"category": "annotation_content"}):
            parsed, coverage = self.nested_fixture({"lora_1": slot})
            coverage["parameters"][0].update(override)
            self.assertEqual(extract_candidates(parsed, coverage), [])

    def test_nested_lora_invalid_control_types_are_not_truthy_enabled(self):
        parsed, coverage = self.nested_fixture({
            "lora_1": {"on": "false", "lora": "a.safetensors", "strength": "1", "strengthTwo": True},
        })
        hints = extract_candidates(parsed, coverage)[0]["known_hints"]
        self.assertEqual(hints["saved_lora_controls"], {"on": None, "strength": None, "strengthTwo": None})

    def test_chinese_qwente_fields_keep_original_names_and_component_roles(self):
        parsed, coverage = self.nested_fixture({
            "主模型": "Qwen/main.gguf", "视觉投影mmproj": "Qwen/mmproj.gguf",
            "模型系列": "Qwen3.6-VL", "提示词": "fake.safetensors",
        }, "QwenTE_ModelLoader")
        results = extract_candidates(parsed, coverage)
        self.assertEqual([r["parameter"] for r in results], ["主模型", "视觉投影mmproj"])
        self.assertEqual([r["known_hints"]["component_kind"] for r in results], ["llm", "vision_projection"])
        self.assertTrue(all(r["model_role"] == "other" for r in results))
        self.assertTrue(all(r["artifact_form"] == "single_file" for r in results))

    def test_chinese_fields_skip_placeholders_unrelated_nodes_and_redaction(self):
        parsed, coverage = self.nested_fixture({
            "主模型": "（请把模型放到 models/LLM）", "视觉投影mmproj": "无",
        }, "QwenTE_ModelLoader")
        self.assertEqual(extract_candidates(parsed, coverage), [])
        parsed, coverage = self.nested_fixture({"主模型": "a.gguf"}, "UnverifiedLoader")
        self.assertEqual(extract_candidates(parsed, coverage), [])
        parsed, coverage = self.nested_fixture({"主模型": "a.gguf"}, "QwenTE_ModelLoader")
        coverage["parameters"][0]["redacted"] = True
        self.assertEqual(extract_candidates(parsed, coverage), [])

    def test_nested_lora_ui_named_widget_object(self):
        write_json(self.workflow, {"version": 0.4, "nodes": [{
            "id": 1, "type": "Power Lora Loader (rgthree)", "mode": 4,
            "widgets_values": {"lora_3": {"on": True, "lora": "a.safetensors", "strength": 1}},
        }], "links": [], "groups": []})
        parsed, coverage = analyze(self.workflow)
        result = extract_candidates(parsed, coverage)[0]
        self.assertEqual(result["parameter"], "lora_3.lora")
        self.assertEqual(result["known_hints"]["node_mode_state"], "bypassed")

    def test_invalid_index_is_explicit_not_checked(self):
        self.index_path.parent.mkdir(parents=True)
        self.index_path.write_text("{bad json", encoding="utf-8")
        report = build_report(self.parsed, self.coverage, self.library)
        self.assertEqual(report["summary"]["handoff_status"], "not_checked")
        self.assertEqual(report["index_error"]["code"], "invalid_index_json")
        self.assertTrue(all(row["status"] == "not_checked" for row in report["results"]))
        self.assertEqual(report["missing_requests"], [])
        self.assertEqual(report["resolution_requests"], [])

    def test_missing_library_is_explicit_not_checked(self):
        report = build_report(self.parsed, self.coverage, self.root / "absent")
        self.assertEqual(report["summary"]["handoff_status"], "not_checked")
        self.assertEqual(report["index_error"]["code"], "model_library_root_missing")

    def test_index_cannot_supply_paths_outside_library(self):
        unsafe = model("unsafe", ["model-a.safetensors"])
        unsafe["paths"] = ["../outside.md"]
        self.set_index([unsafe])
        report = build_report(self.parsed, self.coverage, self.library)
        self.assertEqual(report["summary"]["handoff_status"], "not_checked")
        self.assertEqual(report["index_error"]["code"], "invalid_index_schema")

    def test_handoff_uses_shared_model_library_enums(self):
        allowed_roles = {
            "checkpoint", "diffusion_model", "lora", "vae", "text_encoder", "clip_vision",
            "controlnet", "ipadapter", "upscaler", "motion_model", "other", "unknown",
        }
        allowed_forms = {"single_file", "sharded", "directory", "remote_only", "unknown"}
        for parameter in (
            "ckpt_name", "unet_name", "lora_name", "vae_name", "clip_name", "clip_vision_name",
            "control_net_name", "ip_adapter_name", "upscale_model_name", "motion_model_name", "model_name",
        ):
            self.assertIn(_reference_role(parameter), allowed_roles)
        for reference in ("model.safetensors", "model.gguf", SHA_A, "named-selector"):
            self.assertIn(_artifact_form(reference), allowed_forms)

    def test_same_alias_with_conflicting_known_role_is_not_matched(self):
        self.set_index([model("checkpoint-only", ["missing-lora.safetensors"], model_role="checkpoint")])
        report = build_report(self.parsed, self.coverage, self.library)
        result = next(row for row in report["results"] if row["raw_reference"] == "missing-lora.safetensors")
        self.assertEqual(result["status"], "missing")
        self.assertEqual(result["role_conflict_model_ids"], ["checkpoint-only"])

    def test_linked_index_is_not_read(self):
        self.set_index([model("model-a", ["model-a.safetensors"])])
        with patch("model_handoff._linked", side_effect=lambda path: path == self.index_path):
            report = build_report(self.parsed, self.coverage, self.library)
        self.assertEqual(report["summary"]["handoff_status"], "not_checked")
        self.assertEqual(report["index_error"]["code"], "unsafe_model_library_link")

    def test_report_output_cannot_overwrite_or_enter_shared_library(self):
        self.set_index([model("model-a", ["model-a.safetensors"], model_role="checkpoint")])
        before = self.index_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "outside the read-only shared model library"):
            create_report(self.parsed, self.coverage, self.library, self.index_path)
        self.assertEqual(self.index_path.read_bytes(), before)

    def test_report_output_cannot_be_an_external_hardlink_to_index(self):
        self.set_index([model("model-a", ["model-a.safetensors"], model_role="checkpoint")])
        before = self.index_path.read_bytes()
        hardlink = self.root / "outside-hardlink.json"
        os.link(self.index_path, hardlink)
        with self.assertRaisesRegex(FileExistsError, "must be a new file"):
            create_report(self.parsed, self.coverage, self.library, hardlink)
        self.assertEqual(self.index_path.read_bytes(), before)

    def test_library_metadata_is_returned_and_conflict_is_not_complete(self):
        conflicted = model(
            "conflicted-lora",
            ["missing-lora.safetensors"],
            model_role="lora",
            artifact_form="sharded",
        )
        conflicted["status"] = "conflict"
        self.set_index([conflicted])
        report = build_report(self.parsed, self.coverage, self.library)
        result = next(row for row in report["results"] if row["raw_reference"] == "missing-lora.safetensors")
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(result["matched_library_entries"][0]["status"], "conflict")
        self.assertEqual(result["matched_library_entries"][0]["artifact_form"], "sharded")
        self.assertIn("artifact_form_conflict", result["library_review_reasons"])
        self.assertEqual(report["summary"]["resolution_request_count"], 1)
        self.assertEqual(report["summary"]["handoff_status"], "needs_research")

    def test_partial_unique_match_is_labeled_for_library_review(self):
        self.set_index([model(
            "model-a", ["model-a.safetensors"], model_role="checkpoint", artifact_form="single_file",
        )])
        report = build_report(self.parsed, self.coverage, self.library)
        result = next(row for row in report["results"] if row["raw_reference"].endswith("model-a.safetensors"))
        self.assertEqual(result["status"], "matched")
        self.assertTrue(result["library_review_required"])
        self.assertEqual(result["matched_library_entries"][0]["model_role"], "checkpoint")

    def test_declared_version_resolves_duplicate_alias(self):
        data = {
            "1": {
                "class_type": "LoraLoader",
                "inputs": {"lora_name": "duplicate.safetensors", "lora_version": "v2"},
            }
        }
        write_json(self.workflow, data)
        parsed, coverage = analyze(self.workflow)
        self.set_index(
            [
                model("duplicate-v1", ["duplicate.safetensors"], version="v1"),
                model("duplicate-v2", ["duplicate.safetensors"], version="v2"),
            ]
        )
        result = build_report(parsed, coverage, self.library)["results"][0]
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["matched_model_ids"], ["duplicate-v2"])
        self.assertEqual(result["match_method"], "exact_alias_and_declared_version")

    def test_declared_version_conflict_never_matches_unique_wrong_version(self):
        data = {
            "1": {
                "class_type": "LoraLoader",
                "inputs": {"lora_name": "same.safetensors", "lora_version": "v2"},
            }
        }
        write_json(self.workflow, data)
        parsed, coverage = analyze(self.workflow)
        self.set_index([model("only-v1", ["same.safetensors"], version="v1", model_role="lora")])
        report = build_report(parsed, coverage, self.library)
        result = report["results"][0]
        self.assertEqual(result["status"], "missing")
        self.assertEqual(result["version_conflict_model_ids"], ["only-v1"])
        self.assertEqual(report["missing_requests"][0]["candidate_model_ids"], ["only-v1"])

    def test_declared_version_with_unknown_library_version_requires_resolution(self):
        data = {
            "1": {
                "class_type": "LoraLoader",
                "inputs": {"lora_name": "same.safetensors", "lora_version": "v2"},
            }
        }
        write_json(self.workflow, data)
        parsed, coverage = analyze(self.workflow)
        self.set_index([model("unknown-version", ["same.safetensors"], version=None, model_role="lora")])
        report = build_report(parsed, coverage, self.library)
        self.assertEqual(report["results"][0]["status"], "ambiguous")
        self.assertEqual(report["resolution_requests"][0]["candidate_model_ids"], ["unknown-version"])

    def test_reader_rejects_windows_reserved_model_id(self):
        self.set_index([model("CON", ["model-a.safetensors"])])
        report = build_report(self.parsed, self.coverage, self.library)
        self.assertEqual(report["summary"]["handoff_status"], "not_checked")
        self.assertEqual(report["index_error"]["code"], "invalid_index_schema")

    def test_prepare_default_has_no_handoff_output_or_summary_keys(self):
        run = self.root / "prepared-default"
        command = [
            sys.executable,
            str(Path(__file__).with_name("prepare_run.py")),
            str(self.workflow),
            str(run),
            "--no-official-cli",
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            env={**os.environ, "PYTHONUTF8": "1"},
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        summary = json.loads(result.stdout)
        self.assertNotIn("model_handoff_status", summary)
        self.assertFalse((run / "02-机器解析" / REPORT_NAME).exists())

    def test_prepare_model_library_integration(self):
        self.set_index([model("model-a", ["model-a.safetensors"], sha256=SHA_A)])
        run = self.root / "prepared-library"
        command = [
            sys.executable,
            str(Path(__file__).with_name("prepare_run.py")),
            str(self.workflow),
            str(run),
            "--model-library-root",
            str(self.library),
            "--no-official-cli",
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            env={**os.environ, "PYTHONUTF8": "1"},
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        summary = json.loads(result.stdout)
        self.assertEqual(summary["model_handoff_status"], "needs_research")
        self.assertEqual(summary["model_handoff_counts"]["candidate_count"], 3)
        report = json.loads((run / "02-机器解析" / REPORT_NAME).read_text(encoding="utf-8"))
        self.assertFalse(report["constraints"]["shared_library_mutated"])
        ledger = json.loads((run / "03-证据台账.json").read_text(encoding="utf-8"))
        self.assertTrue(any(row["id"] == "model-library-read-only-handoff" for row in ledger["records"]))

    def test_prepare_bad_index_reports_not_checked_without_blocking_analysis(self):
        self.index_path.parent.mkdir(parents=True)
        self.index_path.write_text("{broken", encoding="utf-8")
        run = self.root / "prepared-bad-index"
        command = [
            sys.executable,
            str(Path(__file__).with_name("prepare_run.py")),
            str(self.workflow),
            str(run),
            "--model-library-root",
            str(self.library),
            "--no-official-cli",
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            env={**os.environ, "PYTHONUTF8": "1"},
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        summary = json.loads(result.stdout)
        self.assertEqual(summary["model_handoff_status"], "not_checked")
        self.assertTrue((run / "02-机器解析" / "01-工作流解析结果.json").is_file())
        report = json.loads((run / "02-机器解析" / REPORT_NAME).read_text(encoding="utf-8"))
        self.assertEqual(report["index_error"]["code"], "invalid_index_json")

    def test_prepare_run_directory_cannot_be_inside_shared_library(self):
        self.set_index([model("model-a", ["model-a.safetensors"], model_role="checkpoint")])
        before = self.index_path.read_bytes()
        forbidden_run = self.library / "workflow-run"
        command = [
            sys.executable,
            str(Path(__file__).with_name("prepare_run.py")),
            str(self.workflow),
            str(forbidden_run),
            "--model-library-root",
            str(self.library),
            "--no-official-cli",
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            env={**os.environ, "PYTHONUTF8": "1"},
            timeout=30,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(forbidden_run.exists())
        self.assertEqual(self.index_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
