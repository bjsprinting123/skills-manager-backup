from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any


REPORT_NAME = "07-模型资料交接.json"
INDEX_RELATIVE_PATH = Path("索引数据") / "model-index.json"
INDEX_SCHEMA_VERSION = 1
INDEX_MODEL_STATUS = {"candidate", "partial", "verified", "conflict", "deprecated"}
MODEL_ROLES = {
    "checkpoint", "diffusion_model", "lora", "vae", "text_encoder", "clip_vision",
    "controlnet", "ipadapter", "upscaler", "motion_model", "other", "unknown",
}
ARTIFACT_FORMS = {"single_file", "sharded", "directory", "remote_only", "unknown"}

NAMED_MAPPING_STATUSES = {
    "mapped_by_widgets_values_named",
    "mapped_by_named_widgets_object",
    "mapped_by_authoritative_widget_schema",
    "mapped_from_api_input",
}
MODEL_PREFIXES = {
    "checkpoint",
    "ckpt",
    "unet",
    "diffusion_model",
    "vae",
    "lora",
    "controlnet",
    "control_net",
    "ipadapter",
    "ip_adapter",
    "clip",
    "clip_vision",
    "text_encoder",
    "motion_model",
    "upscale_model",
}
GENERIC_MODEL_PARAMETERS = {"model_name", "model_file", "model_path", "filename"}
MODEL_NODE_MARKERS = {
    "loader",
    "checkpoint",
    "lora",
    "vae",
    "unet",
    "controlnet",
    "control_net",
    "ipadapter",
    "ip_adapter",
    "clipvision",
    "clip_vision",
    "textencoder",
    "text_encoder",
    "upscalemodel",
    "upscale_model",
    "motionmodel",
    "motion_model",
}
NON_MODEL_SUFFIXES = {
    ".apng", ".avif", ".bmp", ".gif", ".heic", ".jpeg", ".jpg", ".png",
    ".svg", ".tif", ".tiff", ".webp", ".wav", ".mp3", ".m4a", ".flac",
    ".aac", ".ogg", ".mp4", ".mkv", ".mov", ".avi", ".webm", ".json",
    ".txt", ".md", ".csv", ".srt",
}
MODEL_WEIGHT_SUFFIXES = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".onnx"}
PLACEHOLDERS = {"", "none", "null", "default", "auto", "disabled", "undefined"}
SHA256_RE = re.compile(r"^(?:sha256\s*[:=]\s*)?([0-9a-fA-F]{64})$")
URL_RE = re.compile(r"^(?:https?|ftp|data)://", re.IGNORECASE)
MODEL_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


class ModelIndexError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def path_is_within(path: Path, directory: Path) -> bool:
    """Detect both lexical containment and containment through an existing link target."""
    absolute_path = Path(os.path.abspath(path))
    absolute_directory = Path(os.path.abspath(directory))
    try:
        absolute_path.relative_to(absolute_directory)
        return True
    except ValueError:
        pass
    try:
        resolved_path = absolute_path.resolve()
        resolved_directory = absolute_directory.resolve()
        resolved_path.relative_to(resolved_directory)
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _normalized(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().strip("\"'").replace("\\", "/").casefold()


def _basename(value: str) -> str:
    return _normalized(value).rstrip("/").rsplit("/", 1)[-1]


def _safe_model_id(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(MODEL_ID_RE.fullmatch(value))
        and not value.endswith(".")
        and value.split(".", 1)[0].upper() not in WINDOWS_RESERVED_NAMES
    )


def _parameter_is_model_reference(parameter: str, node_type: str) -> bool:
    name = parameter.casefold().strip()
    for prefix in MODEL_PREFIXES:
        if name == prefix or re.fullmatch(
            rf"{re.escape(prefix)}_(?:name|file|path|model)(?:_?\d+)?", name
        ):
            return True
    if name in GENERIC_MODEL_PARAMETERS:
        node = node_type.casefold().replace(" ", "")
        return any(marker in node for marker in MODEL_NODE_MARKERS)
    return False


def _safe_reference(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().strip("\"'")
    lowered = candidate.casefold()
    if lowered in PLACEHOLDERS or len(candidate) > 512 or "\n" in candidate or "\r" in candidate:
        return None
    if URL_RE.match(candidate) or lowered.startswith("www."):
        return None
    suffix = Path(candidate.replace("\\", "/")).suffix.casefold()
    if suffix in NON_MODEL_SUFFIXES:
        return None
    return candidate


def _reference_role(parameter: str) -> str:
    name = parameter.casefold()
    roles = (
        ("checkpoint", ("checkpoint", "ckpt")),
        ("diffusion_model", ("diffusion_model", "unet")),
        ("lora", ("lora",)),
        ("vae", ("vae",)),
        ("controlnet", ("controlnet", "control_net")),
        ("ipadapter", ("ipadapter", "ip_adapter")),
        ("clip_vision", ("clip_vision",)),
        ("text_encoder", ("text_encoder", "clip")),
        ("motion_model", ("motion_model",)),
        ("upscaler", ("upscale_model",)),
    )
    for role, prefixes in roles:
        if any(name == prefix or name.startswith(prefix + "_") for prefix in prefixes):
            return role
    return "unknown"


def _artifact_form(reference: str) -> str:
    if _reference_sha(reference):
        return "unknown"
    suffix = Path(reference.replace("\\", "/")).suffix.casefold()
    if suffix in MODEL_WEIGHT_SUFFIXES:
        return "single_file"
    return "unknown"


def _linked(path: Path) -> bool:
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def _declared_version(parameters: list[dict[str, Any]], row: dict[str, Any]) -> str | None:
    name = str(row.get("parameter", "")).casefold()
    prefix = next((item for item in sorted(MODEL_PREFIXES, key=len, reverse=True) if name.startswith(item)), "model")
    allowed = {"model_version", f"{prefix}_version"}
    for other in parameters:
        if other.get("node_key") != row.get("node_key"):
            continue
        if (
            other.get("mapping_status") not in NAMED_MAPPING_STATUSES
            or other.get("category") != "execution_parameter"
            or other.get("redacted")
        ):
            continue
        if str(other.get("parameter", "")).casefold() not in allowed:
            continue
        value = other.get("current_value")
        if isinstance(value, str) and 0 < len(value.strip()) <= 128:
            return value.strip()
    return None


def extract_candidates(parsed: dict[str, Any], coverage: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract named model strings and source-verified leaves; ignore unresolved widgets."""
    nodes = {str(row.get("node_key")): row for row in parsed.get("nodes", []) if isinstance(row, dict)}
    parameters = [row for row in coverage.get("parameters", []) if isinstance(row, dict)]
    candidates: list[dict[str, Any]] = []
    for row in parameters:
        if row.get("mapping_status") not in NAMED_MAPPING_STATUSES:
            continue
        if row.get("category") != "execution_parameter" or row.get("redacted"):
            continue
        parameter = str(row.get("parameter", ""))
        node_type = str(row.get("node_type", ""))
        value = row.get("current_value")
        extra_hints: dict[str, Any] = {}
        role = _reference_role(parameter)
        if node_type == "Power Lora Loader (rgthree)" and re.fullmatch(r"lora_\d+", parameter, re.I):
            # rgthree py/power_lora_loader.py: only this known object schema is a LoRA slot.
            if not isinstance(value, dict) or not {"on", "lora", "strength"} <= value.keys():
                continue
            extra_hints["saved_lora_controls"] = {
                "on": value["on"] if type(value["on"]) is bool else None,
                "strength": value["strength"] if type(value["strength"]) in (int, float) else None,
                "strengthTwo": value.get("strengthTwo") if type(value.get("strengthTwo")) in (int, float) else None,
            }
            extra_hints["source_parameter"] = parameter
            parameter += ".lora"
            value = value["lora"]
            role = "lora"
        elif node_type == "QwenTE_ModelLoader" and parameter in {"主模型", "视觉投影mmproj"}:
            # Author's comfyUI-llama-TE/nodes.py: LLM and optional vision projection, not CLIP/VAE.
            if isinstance(value, str) and (value.strip() == "无" or value.strip().startswith("（请把模型放到")):
                continue
            role = "other"
            extra_hints["component_kind"] = "llm" if parameter == "主模型" else "vision_projection"
        elif not _parameter_is_model_reference(parameter, node_type):
            continue
        reference = _safe_reference(value)
        if reference is None:
            continue
        node = nodes.get(str(row.get("node_key")), {})
        declared_version = _declared_version(parameters, row)
        artifact_form = _artifact_form(reference)
        digest = hashlib.sha256(
            f"{row.get('node_key')}\0{parameter}\0{reference}".encode("utf-8")
        ).hexdigest()[:20]
        hints = {
            "reference_basename": _basename(reference),
            "reference_suffix": Path(reference.replace("\\", "/")).suffix or None,
            "declared_model_version": declared_version,
            "node_package": node.get("package"),
            "node_version": node.get("version"),
            "reference_role_hint": role,
            "parsed_node_mode": node.get("mode"),
            "node_mode_state": (
                {0: "normal_or_parser_default", 2: "never", 4: "bypassed"}.get(node["mode"], "unknown")
                if type(node.get("mode")) is int else "not_recorded"
            ),
            "runtime_usage": "not_verified",
            "local_file_presence": "not_checked",
            **extra_hints,
        }
        candidates.append(
            {
                "candidate_id": f"model-ref-{digest}",
                "node_key": row.get("node_key"),
                "node_type": node_type,
                "parameter": parameter,
                "raw_reference": reference,
                "model_role": role,
                "artifact_form": artifact_form,
                "mapping_status": row.get("mapping_status"),
                "known_hints": hints,
            }
        )
    return candidates


def _optional_string(value: Any, field: str, index: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ModelIndexError("invalid_index_schema", f"models[{index}].{field} must be non-empty string or null")
    return value


def _safe_library_relative_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    return (
        bool(normalized)
        and not normalized.startswith("/")
        and ":" not in normalized
        and not re.match(r"^[A-Za-z]:/", normalized)
        and not URL_RE.match(normalized)
        and ".." not in path.parts
    )


def load_model_index(library_root: Path) -> tuple[list[dict[str, Any]], Path, str]:
    root = Path(os.path.abspath(library_root))
    index_parent = root / INDEX_RELATIVE_PATH.parent
    index_path = root / INDEX_RELATIVE_PATH
    if not root.is_dir():
        raise ModelIndexError("model_library_root_missing", f"Model library root does not exist: {root}")
    if _linked(root) or _linked(index_parent) or _linked(index_path):
        raise ModelIndexError(
            "unsafe_model_library_link",
            "Model library root, index directory, and model-index.json must not be a symlink or junction",
        )
    if not index_path.is_file():
        raise ModelIndexError("model_index_missing", f"Model index does not exist: {index_path}")
    try:
        index_bytes = index_path.read_bytes()
        value = json.loads(index_bytes.decode("utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ModelIndexError("invalid_index_json", f"Cannot read model index: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != INDEX_SCHEMA_VERSION:
        raise ModelIndexError("unsupported_index_schema", "model-index.json must use schema_version=1")
    if set(value) - {"schema_version", "models", "publish_requests"}:
        raise ModelIndexError("invalid_index_schema", "model-index.json contains unsupported top-level fields")
    models = value.get("models")
    if not isinstance(models, list):
        raise ModelIndexError("invalid_index_schema", "model-index.json models must be an array")
    required = {
        "model_id", "aliases", "publisher", "version", "remote_file", "sha256", "status",
        "model_role", "artifact_form", "current_revision", "paths",
    }
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(models):
        if not isinstance(item, dict) or set(item) != required:
            raise ModelIndexError("invalid_index_schema", f"models[{index}] must contain exactly the schema fields")
        model_id = item.get("model_id")
        aliases = item.get("aliases")
        paths = item.get("paths")
        status = item.get("status")
        revision = item.get("current_revision")
        folded_id = model_id.casefold() if isinstance(model_id, str) else None
        if not _safe_model_id(model_id) or folded_id in seen_ids:
            raise ModelIndexError("invalid_index_schema", f"models[{index}].model_id must be a unique safe identifier")
        if not isinstance(aliases, list) or not all(isinstance(v, str) and v.strip() for v in aliases):
            raise ModelIndexError("invalid_index_schema", f"models[{index}].aliases must be a string array")
        if not isinstance(paths, list) or not all(isinstance(v, str) and v.strip() for v in paths):
            raise ModelIndexError("invalid_index_schema", f"models[{index}].paths must be a string array")
        if not all(_safe_library_relative_path(value) for value in paths):
            raise ModelIndexError("invalid_index_schema", f"models[{index}].paths must stay inside the model library")
        if status not in INDEX_MODEL_STATUS:
            raise ModelIndexError("invalid_index_schema", f"models[{index}].status is invalid")
        if item.get("model_role") not in MODEL_ROLES:
            raise ModelIndexError("invalid_index_schema", f"models[{index}].model_role is invalid")
        if item.get("artifact_form") not in ARTIFACT_FORMS:
            raise ModelIndexError("invalid_index_schema", f"models[{index}].artifact_form is invalid")
        if revision is not None and (not isinstance(revision, str) or not revision.strip()):
            raise ModelIndexError("invalid_index_schema", f"models[{index}].current_revision must be non-empty string or null")
        item_copy = dict(item)
        for field in ("publisher", "version", "remote_file", "sha256"):
            item_copy[field] = _optional_string(item.get(field), field, index)
        sha = item_copy["sha256"]
        if sha and not re.fullmatch(r"[0-9a-fA-F]{64}", sha):
            raise ModelIndexError("invalid_index_schema", f"models[{index}].sha256 is not a full SHA-256")
        seen_ids.add(folded_id)
        normalized.append(item_copy)
    return normalized, index_path, hashlib.sha256(index_bytes).hexdigest()


def _reference_sha(reference: str) -> str | None:
    matched = SHA256_RE.fullmatch(reference.strip())
    return matched.group(1).casefold() if matched else None


def _alias_keys(model: dict[str, Any]) -> set[str]:
    values = list(model.get("aliases") or [])
    if model.get("remote_file"):
        values.append(model["remote_file"])
    keys: set[str] = set()
    for value in values:
        keys.add(_normalized(value))
        keys.add(_basename(value))
    return keys


def _library_entry_view(model: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "model_id", "status", "model_role", "artifact_form", "publisher", "version",
        "remote_file", "sha256", "current_revision", "paths",
    )
    return {field: model.get(field) for field in fields}


def match_candidate(candidate: dict[str, Any], models: list[dict[str, Any]]) -> dict[str, Any]:
    reference = candidate["raw_reference"]
    sha = _reference_sha(reference)
    role_conflicts: list[dict[str, Any]] = []
    version_conflicts: list[dict[str, Any]] = []
    version_unresolved = False
    if sha:
        matches = [model for model in models if (model.get("sha256") or "").casefold() == sha]
        method = "full_sha256"
    else:
        keys = {_normalized(reference), _basename(reference)}
        matches = [model for model in models if keys & _alias_keys(model)]
        method = "exact_alias_or_remote_file"
        candidate_role = candidate.get("model_role")
        if candidate_role in MODEL_ROLES - {"unknown"}:
            role_compatible = [model for model in matches
                               if model.get("model_role") in {candidate_role, "unknown"}]
            role_conflicts = [model for model in matches if model not in role_compatible]
            matches = role_compatible
            if matches and all(model.get("model_role") == candidate_role for model in matches):
                method = "exact_alias_and_model_role"
        declared_version = candidate.get("known_hints", {}).get("declared_model_version")
        if declared_version:
            version_matches = [model for model in matches if _normalized(model.get("version") or "") == _normalized(declared_version)]
            if version_matches:
                matches = version_matches
                method = "exact_alias_and_declared_version"
            elif matches:
                unknown_version = [model for model in matches if model.get("version") is None]
                version_conflicts = [model for model in matches if model.get("version") is not None]
                matches = unknown_version
                if matches:
                    version_unresolved = True
                    method = "exact_alias_but_library_version_unknown"
    result = dict(candidate)
    result["match_method"] = method if matches else None
    result["matched_model_ids"] = [model["model_id"] for model in matches]
    result["matched_library_entries"] = [_library_entry_view(model) for model in matches]
    result["role_conflict_model_ids"] = [model["model_id"] for model in role_conflicts]
    result["version_conflict_model_ids"] = [model["model_id"] for model in version_conflicts]
    selected = matches[0] if len(matches) == 1 else None
    artifact_conflict = bool(
        selected
        and candidate.get("artifact_form") == "single_file"
        and selected.get("artifact_form") in {"sharded", "directory"}
    )
    review_reasons = []
    if selected and selected.get("status") in {"candidate", "partial", "conflict", "deprecated"}:
        review_reasons.append(f"library_status:{selected['status']}")
    if artifact_conflict:
        review_reasons.append("artifact_form_conflict")
    result["library_review_required"] = bool(review_reasons)
    result["library_review_reasons"] = review_reasons
    library_requires_resolution = bool(
        selected and (selected.get("status") in {"conflict", "deprecated"} or artifact_conflict)
    )
    if version_unresolved or library_requires_resolution:
        result["status"] = "ambiguous"
        result["matched_revision"] = None
        result["matched_paths"] = []
    elif len(matches) == 1:
        result["status"] = "matched"
        result["matched_revision"] = matches[0].get("current_revision")
        result["matched_paths"] = matches[0].get("paths", [])
    elif len(matches) > 1:
        result["status"] = "ambiguous"
        result["matched_revision"] = None
        result["matched_paths"] = []
    else:
        result["status"] = "missing"
        result["matched_revision"] = None
        result["matched_paths"] = []
    return result


def _missing_request(candidate: dict[str, Any], workflow: dict[str, Any]) -> dict[str, Any]:
    raw = f"{workflow.get('sha256')}\0{workflow.get('run_id')}\0{candidate['candidate_id']}"
    request_id = "model-research-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return {
        "request_id": request_id,
        "request_type": "model_library_research_candidate",
        "status": "pending_research",
        "workflow_sha256": workflow.get("sha256"),
        "run_id": workflow.get("run_id"),
        "node_key": candidate.get("node_key"),
        "node_type": candidate.get("node_type"),
        "parameter": candidate.get("parameter"),
        "raw_reference": candidate.get("raw_reference"),
        "model_role": candidate.get("model_role"),
        "artifact_form": candidate.get("artifact_form"),
        "known_hints": candidate.get("known_hints", {}),
        "candidate_model_ids": [
            *candidate.get("role_conflict_model_ids", []),
            *candidate.get("version_conflict_model_ids", []),
        ],
        "needed_fields": [
            "canonical_identity",
            "publisher",
            "version",
            "remote_file",
            "sha256_if_locally_available",
            "author_sources_and_guidance",
            "community_feedback_with_source_status",
            "compatibility_and_usage_limits",
        ],
        "publication_owner": "comfyui-model-library",
    }


def _resolution_request(candidate: dict[str, Any], workflow: dict[str, Any]) -> dict[str, Any]:
    raw = f"resolve\0{workflow.get('sha256')}\0{workflow.get('run_id')}\0{candidate['candidate_id']}"
    return {
        "request_id": "model-resolution-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24],
        "request_type": "model_library_identity_resolution_candidate",
        "status": "pending_resolution",
        "workflow_sha256": workflow.get("sha256"),
        "run_id": workflow.get("run_id"),
        "node_key": candidate.get("node_key"),
        "node_type": candidate.get("node_type"),
        "parameter": candidate.get("parameter"),
        "raw_reference": candidate.get("raw_reference"),
        "model_role": candidate.get("model_role"),
        "artifact_form": candidate.get("artifact_form"),
        "known_hints": candidate.get("known_hints", {}),
        "candidate_model_ids": candidate.get("matched_model_ids", []),
        "needed_fields": ["exact_sha256", "publisher", "version", "remote_file"],
        "publication_owner": "comfyui-model-library",
    }


def build_report(
    parsed: dict[str, Any],
    coverage: dict[str, Any],
    library_root: Path,
    *,
    run_id: str | None = None,
    workflow_sha256: str | None = None,
) -> dict[str, Any]:
    candidates = extract_candidates(parsed, coverage)
    workflow = {
        "sha256": workflow_sha256 or parsed.get("source_sha256"),
        "run_id": run_id,
        "format": parsed.get("format"),
        "source_path": parsed.get("original_source_path") or parsed.get("source_path"),
    }
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": _now(),
        "producer": "comfyui-workflow-docs/model_handoff.py",
        "mode": "read_only_lookup_and_request_generation",
        "workflow": workflow,
        "model_library_root": str(library_root.resolve()),
        "model_index_path": str((library_root.resolve() / INDEX_RELATIVE_PATH)),
        "phase_statuses": {
            "analysis": "completed",
            "index": "not_checked",
            "research": "not_performed",
            "publish": "not_performed",
        },
        "results": [],
        "missing_requests": [],
        "resolution_requests": [],
        "constraints": {
            "shared_library_mutated": False,
            "unresolved_widgets_used": False,
            "web_or_readme_content_treated_as_instructions": False,
            "workflow_runtime_executed": False,
        },
    }
    try:
        models, index_path, index_sha256 = load_model_index(library_root)
    except ModelIndexError as exc:
        report["phase_statuses"]["index"] = "not_checked"
        report["index_error"] = {"code": exc.code, "message": str(exc)}
        report["results"] = [{**candidate, "status": "not_checked", "match_method": None,
                              "matched_model_ids": [], "matched_revision": None, "matched_paths": []}
                             for candidate in candidates]
    else:
        report["phase_statuses"]["index"] = "read_only_checked"
        report["model_index_path"] = str(index_path)
        report["model_index_sha256"] = index_sha256
        report["results"] = [match_candidate(candidate, models) for candidate in candidates]
        inventory_spec = importlib.util.spec_from_file_location('workflow_inventory_state', Path(__file__).with_name('inventory_state.py'))
        inventory_module = importlib.util.module_from_spec(inventory_spec)
        inventory_spec.loader.exec_module(inventory_module)
        inventory = inventory_module.read_state(library_root, index={'models': models})
        report['phase_statuses']['inventory'] = inventory['status']
        report['inventory_checked_at'] = inventory.get('checked_at')
        report['inventory_review_required'] = not inventory['fresh'] or bool(inventory.get('unregistered_paths'))
        report['inventory_unregistered_count'] = len(inventory.get('unregistered_paths', []))
        for result in report['results']:
            result['inventory_by_model'] = {
                mid: inventory['records'].get(mid, inventory_module.unknown(inventory.get('reason') or '库存记录缺失'))
                for mid in result.get('matched_model_ids', [])
            }
            if any(not state['is_local'] for state in result['inventory_by_model'].values()):
                report['inventory_review_required'] = True
        report["missing_requests"] = [
            _missing_request(result, workflow)
            for result in report["results"]
            if result["status"] == "missing"
        ]
        report["resolution_requests"] = [
            _resolution_request(result, workflow)
            for result in report["results"]
            if result["status"] == "ambiguous"
        ]
    counts = {status: 0 for status in ("matched", "missing", "ambiguous", "not_checked")}
    for result in report["results"]:
        counts[result["status"]] += 1
    report["summary"] = {
        "candidate_count": len(candidates),
        **{f"{name}_count": count for name, count in counts.items()},
        "missing_request_count": len(report["missing_requests"]),
        "resolution_request_count": len(report["resolution_requests"]),
        "library_review_count": sum(
            1 for result in report["results"] if result.get("library_review_required")
        ),
        "handoff_status": (
            "not_checked" if report["phase_statuses"]["index"] == "not_checked"
            else "needs_research" if counts["missing"]
            else "needs_resolution" if counts["ambiguous"]
            else "needs_library_review" if any(
                result.get("library_review_required") for result in report["results"]
            )
            else "complete_for_detected_references"
        ),
    }
    return report


def create_report(
    parsed: dict[str, Any],
    coverage: dict[str, Any],
    library_root: Path,
    output_path: Path,
    *,
    run_id: str | None = None,
    workflow_sha256: str | None = None,
) -> dict[str, Any]:
    if path_is_within(output_path, library_root):
        raise ValueError("Handoff output must be outside the read-only shared model library")
    if output_path.exists() or output_path.is_symlink():
        raise FileExistsError("Handoff output must be a new file; existing files and hardlinks are not overwritten")
    report = build_report(
        parsed, coverage, library_root, run_id=run_id, workflow_sha256=workflow_sha256
    )
    _write_json(output_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Read a shared model index and create a workflow-to-model handoff report")
    parser.add_argument("parsed", type=Path)
    parser.add_argument("coverage", type=Path)
    parser.add_argument("model_library_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--workflow-sha256")
    args = parser.parse_args()
    parsed = json.loads(args.parsed.read_text(encoding="utf-8"))
    coverage = json.loads(args.coverage.read_text(encoding="utf-8"))
    report = create_report(
        parsed,
        coverage,
        args.model_library_root,
        args.output,
        run_id=args.run_id,
        workflow_sha256=args.workflow_sha256,
    )
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
