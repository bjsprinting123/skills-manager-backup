from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
from datetime import datetime
from pathlib import Path

from analyze_workflow import analyze, write_outputs
from collect_cli_evidence import DEFAULT_CLI_PYTHON, collect
from model_handoff import REPORT_NAME as MODEL_HANDOFF_REPORT_NAME
from model_handoff import create_report as create_model_handoff_report
from model_handoff import path_is_within
from validate_closeout import initial_checklist


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(path: Path, role: str) -> dict[str, object]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise SystemExit(f"Missing {role}: {resolved}")
    return {
        "role": role,
        "source_path": str(resolved),
        "filename": resolved.name,
        "size_bytes": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
        "status": "obtained",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new ComfyUI documentation run")
    parser.add_argument("workflow", type=Path)
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--previous-document", type=Path)
    parser.add_argument("--video", type=Path, action="append", default=[])
    parser.add_argument("--author-material", type=Path, action="append", default=[])
    parser.add_argument("--widget-schema", type=Path)
    parser.add_argument("--cli-python", type=Path, default=DEFAULT_CLI_PYTHON)
    parser.add_argument("--object-info", type=Path)
    parser.add_argument("--comfyui-root", type=Path)
    parser.add_argument("--comfyui-python", type=Path)
    parser.add_argument("--model-library-root", type=Path)
    parser.add_argument("--no-official-cli", action="store_true")
    args = parser.parse_args()
    if (args.comfyui_root is None) != (args.comfyui_python is None):
        parser.error("Supply --comfyui-root and --comfyui-python together")
    if args.no_official_cli and (args.object_info or args.comfyui_root):
        parser.error("--no-official-cli conflicts with official evidence inputs")

    source = args.workflow.resolve()
    source_item = inventory(source, "workflow_json")
    run_root = args.run_directory.resolve()
    if args.model_library_root is not None and path_is_within(run_root, args.model_library_root):
        parser.error("run_directory must be outside the read-only shared model library")
    if run_root.exists() and any(run_root.iterdir()):
        raise SystemExit(f"Run directory must be new or empty: {run_root}")

    snapshot_dir = run_root / "01-输入快照"
    machine_dir = run_root / "02-机器解析"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    machine_dir.mkdir(parents=True, exist_ok=True)
    snapshot = snapshot_dir / "01-原始工作流.json"
    shutil.copy2(source, snapshot)
    if sha256_file(snapshot) != source_item["sha256"]:
        raise SystemExit("Snapshot hash mismatch")
    snapshot.chmod(snapshot.stat().st_mode & ~stat.S_IWRITE)

    optional_items: list[dict[str, object]] = []
    if args.previous_document:
        optional_items.append(inventory(args.previous_document, "previous_document"))
    optional_items.extend(inventory(path, "video_source") for path in args.video)
    optional_items.extend(
        inventory(path, "author_material") for path in args.author_material
    )
    if args.widget_schema:
        optional_items.append(inventory(args.widget_schema, "authoritative_widget_schema"))
    if args.object_info:
        optional_items.append(inventory(args.object_info, "object_info_snapshot"))
    manifest = {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "input_mode": (
            "json_only"
            if not optional_items and args.model_library_root is None
            else "json_with_optional_evidence"
        ),
        "required_inputs": [source_item],
        "optional_inputs": optional_items,
        "source_mutated": False,
    }
    if args.model_library_root is not None:
        manifest["lookup_inputs"] = [
            {
                "role": "shared_model_library",
                "source_path": str(args.model_library_root.resolve()),
                "access": "read_only",
                "status": "requested",
            }
        ]
    (run_root / "00-输入清单.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    parsed, coverage = analyze(snapshot, args.widget_schema)
    parsed["original_source_path"] = source_item["source_path"]
    coverage["original_source_path"] = source_item["source_path"]
    write_outputs(parsed, coverage, machine_dir)

    model_handoff = None
    if args.model_library_root is not None:
        model_handoff = create_model_handoff_report(
            parsed,
            coverage,
            args.model_library_root,
            machine_dir / MODEL_HANDOFF_REPORT_NAME,
            run_id=run_root.name,
            workflow_sha256=str(source_item["sha256"]),
        )

    evidence = {
        "generated_at": manifest["created_at"],
        "records": [
            {
                "id": "source-workflow-json",
                "level": "A",
                "status": "obtained",
                "path": "01-输入快照/01-原始工作流.json",
                "sha256": source_item["sha256"],
                "supports": ["workflow structure", "saved values", "connections"],
            }
        ],
        "video_status": "not_provided" if not args.video else "obtained_local_file",
        "author_material_status": (
            "not_provided" if not args.author_material else "obtained_local_file"
        ),
        "runtime_execution": "not_performed",
    }
    if model_handoff is not None:
        evidence["records"].append(
            {
                "id": "model-library-read-only-handoff",
                "level": "A",
                "status": model_handoff["summary"]["handoff_status"],
                "path": f"02-机器解析/{MODEL_HANDOFF_REPORT_NAME}",
                "sha256": sha256_file(machine_dir / MODEL_HANDOFF_REPORT_NAME),
                "supports": ["detected model reference lookup status", "missing model research requests"],
                "does_not_support": ["model research completed", "model card published", "workflow runtime success"],
            }
        )
    (run_root / "03-证据台账.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    template = Path(__file__).resolve().parents[1] / "assets" / "workflow-document-template.md"
    shutil.copy2(template, run_root / "90-工作流文档候选版.md")
    official = None
    if not args.no_official_cli:
        official = collect(snapshot, run_root, args.cli_python, args.object_info,
                           args.comfyui_root, args.comfyui_python)
    summary = {
        "run_directory": str(run_root),
        "source_sha256": source_item["sha256"],
        "format": parsed["format"],
        "statistics": parsed["statistics"],
        "coverage": coverage["coverage_status"],
        "official_preflight": official["preflight_status"] if official else "DISABLED",
        "official_tool_ready": official["tool_ready"] if official else False,
        "runtime_execution": "not_performed",
    }
    if model_handoff is not None:
        summary["model_handoff_status"] = model_handoff["summary"]["handoff_status"]
        summary["model_handoff_counts"] = {
            key: value
            for key, value in model_handoff["summary"].items()
            if key.endswith("_count")
        }
    closeout_path = run_root / "98-知识回写核对.json"
    closeout_path.write_text(
        json.dumps(initial_checklist(manifest["input_mode"]), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary["knowledge_closeout"] = "PENDING_REVIEW"
    summary["knowledge_closeout_path"] = str(closeout_path)
    summary["next_action"] = "评估知识目标并运行 validate_closeout.py；本次准备成功不代表知识回写完成。"
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
