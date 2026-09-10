from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from analyze_workflow import (
    ANNOTATION_TYPES,
    SECRET_NAME_RE,
    SECRET_PATTERNS,
    analyze,
    api_prompt_payload,
)

CLI_VERSION = "1.20.0"
DEFAULT_CLI_PYTHON = Path(r"E:\tools\comfyui-audit\.venv\Scripts\python.exe")
REPORT_NAME = "06-官方CLI核验.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sanitize(value: object, secrets: set[str], key: str = "") -> object:
    if SECRET_NAME_RE.search(key) and value:
        return "<REDACTED>"
    if isinstance(value, dict):
        return {k: sanitize(v, secrets, k) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(v, secrets, key) for v in value]
    if isinstance(value, str):
        # Scrub user content and diagnostics, never protocol/status/hash fields.
        if key in {"text", "prompt", "positive", "negative", "value", "actual",
                   "message", "hint", "diagnostic", "stderr", "raw", "details"}:
            if value in secrets:
                return "<REDACTED>"
            for secret in sorted(secrets, key=len, reverse=True):
                if len(secret) >= 8:
                    value = value.replace(secret, "<REDACTED>")
        for pattern in SECRET_PATTERNS:
            value = pattern.sub("<REDACTED>", value)
        value = re.sub(r"(?i)Bearer\s+[^\s\"']+", "Bearer <REDACTED>", value)
        value = re.sub(r"(?i)(https?://)[^/@\s]+@", r"\1<REDACTED>@", value)
        value = re.sub(r"(?i)([?&](?:token|key|signature|password)=)[^&#\s]+", r"\1<REDACTED>", value)
        value = re.sub(
            r"(?i)\b(password|api[_-]?key|access[_-]?token|refresh[_-]?token|"
            r"cookie|authorization|client[_-]?secret)\s*[:=]\s*"
            r"(?:\"[^\"]*\"|'[^']*'|[^\s;,]+)",
            r"\1=<REDACTED>", value,
        )
    return value


def sensitive_values(value: object, key: str = "") -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for name, child in value.items():
            found.update(sensitive_values(child, name))
    elif isinstance(value, list):
        for child in value:
            found.update(sensitive_values(child, key))
    elif isinstance(value, str) and value:
        if SECRET_NAME_RE.search(key) or key in {"text", "prompt", "positive", "negative"}:
            found.add(value)
        for pattern in SECRET_PATTERNS:
            found.update(match.group(0) for match in pattern.finditer(value))
    return found


def worker(args: argparse.Namespace) -> None:
    """Only this isolated subprocess imports the pinned official package."""
    from importlib.metadata import version

    installed = version("comfy-cli")
    if installed != CLI_VERSION:
        raise SystemExit(f"Unsupported comfy-cli version: {installed}; expected {CLI_VERSION}")
    if os.name != "nt":
        raise SystemExit("This phase-one state isolation is validated on Windows only")

    def deny_network(event: str, unused: tuple) -> None:
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
            raise OSError("Network is disabled in the read-only audit worker")

    sys.addaudithook(deny_network)
    if args.action == "version":
        print(json.dumps({"ok": True, "data": {"version": installed, "python": sys.executable}}))
        return

    # 1.20.0 has no public config-dir option. Override the path in this child
    # before importing ConfigManager; no installed package file is modified.
    from comfy_cli import constants

    constants.DEFAULT_CONFIG[constants.OS.WINDOWS] = str(args.state.resolve())
    if args.action == "dependencies":
        from comfy_cli.command.node_deps import build_report

        report, warnings = build_report(
            str(args.workspace.resolve()), python=str(args.target_python.resolve()), refresh=False
        )
        print(json.dumps({"ok": report is not None, "data": report, "warnings": warnings}))
        return

    from comfy_cli.cmdline import app

    commands = ["--json", "--skip-prompt", "--where", "local", "workflow"]
    if args.action == "notes":
        commands += ["notes", str(args.workflow.resolve())]
    elif args.action == "validate":
        commands += ["validate", "--workflow", str(args.workflow.resolve()),
                     "--input", str(args.object_info.resolve())]
    app(args=commands, prog_name="comfy")


def collect(
    workflow: Path, run_root: Path, cli_python: Path = DEFAULT_CLI_PYTHON,
    object_info: Path | None = None, workspace: Path | None = None,
    target_python: Path | None = None,
) -> dict:
    if (workspace is None) != (target_python is None):
        raise ValueError("Supply both --comfyui-root and --comfyui-python, or neither")
    workflow, run_root = workflow.resolve(), run_root.resolve()
    parsed, _ = analyze(workflow)
    paths = [workflow] + ([object_info.resolve()] if object_info else [])
    before = {str(path): digest(path) for path in paths}
    raw_workflow = json.loads(workflow.read_text(encoding="utf-8-sig"))
    secrets = sensitive_values(raw_workflow)
    output = run_root / "02-机器解析" / REPORT_NAME
    evidence_dir = run_root / "05-外部查证" / "official-cli"
    if output.exists() or evidence_dir.exists():
        raise ValueError("Official CLI evidence already exists; use a fresh run directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True)
    records: dict[str, dict] = {}
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("COMFY_") and k not in {"VIRTUAL_ENV", "CONDA_PREFIX"}}
    env.update({"DO_NOT_TRACK": "1", "COMFY_NO_TELEMETRY": "1",
                "COMFY_CLI_NO_REMOTE_REFRESH": "1", "COMFY_NO_CACHE": "1",
                "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
                "PYTHONDONTWRITEBYTECODE": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                "PIP_NO_INDEX": "1"})

    def run(action: str, extra: list[str]) -> dict:
        command = [str(cli_python.resolve()), str(Path(__file__).resolve()), "_worker",
                   action, "--state", str(evidence_dir / "state"), *extra]
        record: dict = {"action": action, "command": command,
                        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                        "backend": ("official-library-build_report" if action == "dependencies" else
                                    "official-package-metadata" if action == "version" else "official-cli"),
                        "status": "unavailable", "returncode": None}
        try:
            result = subprocess.run(command, cwd=evidence_dir, env=env, stdin=subprocess.DEVNULL,
                                    capture_output=True, timeout=45, check=False)
            record.update(returncode=result.returncode,
                          stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),
                          stderr=result.stderr.decode("utf-8", errors="replace"))
            try:
                record["response"] = json.loads(result.stdout.decode("utf-8-sig"))
                record["status"] = "obtained"
            except (ValueError, UnicodeDecodeError):
                # Unknown output is not trusted evidence; keep only a redacted diagnostic.
                record["diagnostic"] = result.stdout.decode("utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            record["reason"] = "timeout_45_seconds"
        except OSError as exc:
            record["reason"] = type(exc).__name__
        path = evidence_dir / f"{action}.json"
        write_json(path, sanitize(record, secrets))
        records[action] = {**record, "evidence_path": str(path.relative_to(run_root)),
                           "evidence_sha256": digest(path)}
        return record

    version_record = run("version", [])
    ready = (version_record.get("returncode") == 0
             and version_record.get("response", {}).get("data", {}).get("version") == CLI_VERSION)
    ui = parsed["format"] == "comfyui_ui_workflow"
    if ready and ui:
        run("notes", ["--workflow", str(workflow)])
    else:
        records["notes"] = {"status": "not_applicable" if not ui else "unavailable",
                            "reason": "API format has no canvas Notes" if not ui else "CLI unavailable"}
    if ready and object_info:
        run("validate", ["--workflow", str(workflow), "--object-info", str(object_info.resolve())])
    else:
        records["validate"] = {"status": "not_provided" if not object_info else "unavailable",
                               "reason": "Validation requires an explicit object_info snapshot and usable CLI"}
    if ready and workspace and target_python:
        run("dependencies", ["--workspace", str(workspace.resolve()),
                             "--target-python", str(target_python.resolve())])
    else:
        records["dependencies"] = {"status": "not_provided" if not workspace else "unavailable",
                                   "reason": "Target workspace and Python must both be explicit"}

    validation = records["validate"].get("response", {}).get("data") or {}
    valid = validation.get("valid")
    if valid is True and (records["validate"].get("returncode") != 0
                          or records["validate"].get("response", {}).get("ok") is not True):
        valid = None
    types = sorted({node["type"] for node in parsed["nodes"]
                    if node["type"] not in ANNOTATION_TYPES and not node.get("is_subgraph_instance")})
    info = None
    schema_status = "not_provided"
    if object_info:
        try:
            info = json.loads(object_info.read_text(encoding="utf-8-sig"))
            if not isinstance(info, dict) or not info or not all(isinstance(v, dict) for v in info.values()):
                raise ValueError("object_info must be a nonempty node-type mapping")
            schema_status = "obtained"
        except (ValueError, UnicodeError):
            info, valid, schema_status = None, None, "invalid_input"
    dangling_candidates = []
    prompt = api_prompt_payload(raw_workflow)
    if prompt is not None:
        for node_id, node in prompt.items():
            for name, value in (node.get("inputs") or {}).items():
                if (isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)
                        and isinstance(value[1], int) and value[0] not in prompt):
                    dangling_candidates.append({"node_id": node_id, "input": name,
                                                "referenced_node_id": value[0], "output_slot": value[1],
                                                "status": "candidate_dangling_link",
                                                "reason": "Two-item reference shape; confirm input schema, not a proven connection"})
    report = {
        "schema": "comfyui-workflow-docs/official-cli-evidence/1",
        "tool_version_required": CLI_VERSION, "tool_ready": ready,
        "source_format": parsed["format"], "inputs_sha256": before,
        "object_info_status": schema_status,
        "source_unchanged": all(digest(Path(path)) == checksum for path, checksum in before.items()),
        "preflight_status": "PASS" if valid is True else "FAIL" if valid is False else "NOT_VERIFIED",
        "runtime_execution": "not_performed", "production_mutations_requested": False,
        "node_types_absent_from_supplied_schema": [t for t in types if t not in info] if info is not None else None,
        "candidate_dangling_links": dangling_candidates,
        "checks": records,
        "node_package_mapping": {"status": "not_verified", "reason": "Manager-backed deps-in-workflow is intentionally disabled"},
        "limitations": [
            "Preflight is not execution success; schema presence is not proof of the current installed environment.",
            "UI conversion is advisory; original widgets remain unresolved without reviewed version-specific mapping.",
            "Python dependency report is not an execution/compatibility test; markers and nested requirements need review.",
            "CLI config is isolated by an in-memory path override, not an official config-dir option; worker networking is blocked.",
        ],
    }
    report = sanitize(report, secrets)
    write_json(output, report)
    ledger_path = run_root / "03-证据台账.json"
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8-sig"))
        ledger.setdefault("records", []).append({
            "id": "official-cli-preflight", "level": "A", "status": "obtained",
            "path": str(output.relative_to(run_root)), "sha256": digest(output),
            "supports": ["recorded CLI attempts, explicit schema preflight and dependency evidence only"],
        })
        write_json(ledger_path, ledger)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only official Comfy CLI evidence collector")
    if len(sys.argv) > 1 and sys.argv[1] == "_worker":
        parser.add_argument("action", choices=["version", "notes", "validate", "dependencies"])
        parser.add_argument("--state", type=Path, required=True)
        parser.add_argument("--workflow", type=Path)
        parser.add_argument("--object-info", type=Path)
        parser.add_argument("--workspace", type=Path)
        parser.add_argument("--target-python", type=Path)
        worker(parser.parse_args(sys.argv[2:]))
        return
    parser.add_argument("workflow", type=Path)
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--cli-python", type=Path, default=DEFAULT_CLI_PYTHON)
    parser.add_argument("--object-info", type=Path)
    parser.add_argument("--comfyui-root", type=Path)
    parser.add_argument("--comfyui-python", type=Path)
    args = parser.parse_args()
    report = collect(args.workflow, args.run_directory, args.cli_python, args.object_info,
                     args.comfyui_root, args.comfyui_python)
    print(json.dumps({"tool_ready": report["tool_ready"], "preflight_status": report["preflight_status"],
                      "runtime_execution": "not_performed"}, ensure_ascii=False))
    if not report["source_unchanged"]:
        raise SystemExit(2)
    if report["preflight_status"] == "FAIL" or not report["tool_ready"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
