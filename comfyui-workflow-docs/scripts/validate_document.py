from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


REQUIRED_HEADINGS = [
    "## 1. 工作流简介与适用范围",
    "## 2. 数据流概览",
    "## 3. 模型、插件与环境依赖",
    "## 4. 从加载到运行的操作步骤",
    "## 5. 全部节点与参数详解",
    "## 6. 视频讲解与作者说明",
    "## 7. 原始连接与语义连接",
    "## 8. 性能、显存与优化建议",
    "## 9. 常见问题与排错",
    "## 10. 来源、证据和核验状态",
]
HEADING_RE = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")
SAME_NOTE_LINK_RE = re.compile(r"\[\[#([^\]]+?)(?:\\?\|[^\]]+)?\]\]")
PLACEHOLDER_RE = re.compile(r"\{\{[A-Z0-9_]+\}\}")
UNSAFE_HEADING_RE = re.compile(r"[`#|^:]")
SECRET_PATTERNS = (
    re.compile(r"(?i)tvly-(?!YOUR|REDACTED)[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)sk-(?!YOUR|REDACTED)[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)(?:SESSDATA|bili_jct|DedeUserID__ckMd5)\s*[=:]\s*\S{8,}"),
)
OBSIDIAN_CLASS_RE = re.compile(
    r"\A---\s*\n(?:(?!---\s*$).)*?\bcomfyui-workflow-doc\b.*?\n---\s*$",
    re.MULTILINE | re.DOTALL,
)
MERMAID_BLOCK_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)
PARAMETER_TABLE_HEADER_RE = re.compile(
    r"(?m)^\|\s*参数/状态\s*\|\s*当前值；源码通用默认；专项官方基线\s*\|"
    r"\s*参数作用\s*\|\s*↑/↓ 或切换分别会怎样\s*\|"
    r"\s*本工作流建议、风险与回退\s*\|\s*$"
)
ALLOWED_SOURCE_STATUSES = {
    "obtained",
    "not_provided",
    "unavailable",
    "login_required",
    "insufficient_evidence",
    "not_verified",
}
TARGETED_RESEARCH_CLASSES = {
    "custom",
    "unknown",
    "missing",
    "conflict",
    "behavior_sensitive",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(name: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def canonical_type_literal(node_type: str) -> str:
    escaped = node_type.replace("|", "\\|")
    return f"`{escaped}`"


def node_inventory_missing(document: str, nodes: list[dict[str, Any]]) -> list[str]:
    missing: list[str] = []
    root_like = [node for node in nodes if node.get("scope") in {"root", "api"}]
    for node in root_like:
        node_id = str(node.get("id"))
        node_type = str(node.get("type"))
        row_prefix = re.compile(rf"(?m)^\|\s*{re.escape(node_id)}\s*\|")
        if not row_prefix.search(document) or canonical_type_literal(node_type) not in document:
            missing.append(str(node.get("node_key")))
    return missing


def mapped_parameter_missing(document: str, parameters: list[dict[str, Any]]) -> list[str]:
    missing: list[str] = []
    for parameter in parameters:
        name = str(parameter.get("parameter"))
        if f"`{name}`" not in document:
            missing.append(str(parameter.get("parameter_key")))
    return missing


def node_research_contract(
    analysis: dict[str, Any], research: dict[str, Any]
) -> tuple[bool, dict[str, Any]]:
    entries = research.get("entries")
    if not isinstance(entries, list):
        return False, {"status": "invalid_schema", "required": "entries[]"}

    required_types = sorted(
        {
            str(node.get("type"))
            for node in (analysis.get("nodes") or [])
            if node.get("type")
        }
    )
    seen: dict[str, int] = {}
    invalid_statuses: list[dict[str, str]] = []
    missing_targeted_statuses: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        node_type = str(entry.get("node_type") or "")
        if not node_type:
            continue
        seen[node_type] = seen.get(node_type, 0) + 1
        implementation_status = str(entry.get("implementation_status") or "")
        if implementation_status not in ALLOWED_SOURCE_STATUSES:
            invalid_statuses.append(
                {"node_type": node_type, "field": "implementation_status"}
            )
        research_class = str(entry.get("research_class") or "")
        if research_class in TARGETED_RESEARCH_CLASSES:
            for field in ("official_discovery_status", "community_research_status"):
                value = str(entry.get(field) or "")
                if value not in ALLOWED_SOURCE_STATUSES:
                    missing_targeted_statuses.append(f"{node_type}:{field}")

    missing_types = [node_type for node_type in required_types if node_type not in seen]
    duplicate_types = sorted(node_type for node_type, count in seen.items() if count > 1)
    source_sha256 = research.get("source_sha256")
    analysis_sha256 = analysis.get("source_sha256")
    source_matches = not source_sha256 or source_sha256 == analysis_sha256
    passed = not (
        missing_types
        or duplicate_types
        or invalid_statuses
        or missing_targeted_statuses
        or not source_matches
    )
    return passed, {
        "status": "verified" if passed else "failed",
        "required_node_types": len(required_types),
        "matrix_node_types": len(seen),
        "missing_node_types": missing_types,
        "duplicate_node_types": duplicate_types,
        "invalid_statuses": invalid_statuses,
        "missing_targeted_statuses": missing_targeted_statuses,
        "source_sha256_matches": source_matches,
    }


def control_surface_contract(
    analysis: dict[str, Any], inventory: dict[str, Any], document: str
) -> tuple[bool, dict[str, Any]]:
    entries = inventory.get("entries")
    if not isinstance(entries, list):
        return False, {"status": "invalid_schema", "required": "entries[]"}
    source_matches = inventory.get("source_sha256") in (None, analysis.get("source_sha256"))
    invalid: list[str] = []
    missing_options: list[str] = []
    option_count = 0
    for entry in entries:
        if not isinstance(entry, dict):
            invalid.append("non_object_entry")
            continue
        parameter = str(entry.get("parameter") or "")
        evidence_status = str(entry.get("evidence_status") or "")
        options = entry.get("options")
        if not parameter or evidence_status not in ALLOWED_SOURCE_STATUSES:
            invalid.append(f"{entry.get('node_key')}:{parameter or '<missing>'}")
            continue
        if options is not None and not isinstance(options, list):
            invalid.append(f"{entry.get('node_key')}:{parameter}:options")
            continue
        if evidence_status == "obtained" and isinstance(options, list):
            option_count += len(options)
            for option in options:
                text = str(option)
                if text and text not in document:
                    missing_options.append(f"{entry.get('node_key')}:{parameter}:{text}")
    passed = source_matches and not invalid and not missing_options
    return passed, {
        "status": "verified" if passed else "failed",
        "control_count": len(entries),
        "documented_option_count": option_count,
        "invalid_entries": invalid,
        "missing_options": missing_options,
        "source_sha256_matches": source_matches,
    }


def media_runtime_contract(
    analysis: dict[str, Any], inventory: dict[str, Any]
) -> tuple[bool, dict[str, Any]]:
    source_matches = inventory.get("source_sha256") in (None, analysis.get("source_sha256"))
    required = {
        "asset_enablement",
        "path_binding",
        "prompt_references",
        "scene_instruction_slots",
        "audio_instruction_slots",
        "downstream_media_connections",
        "planned_runtime",
        "verified_runtime",
    }
    states = inventory.get("states")
    if not isinstance(states, dict):
        return False, {"status": "invalid_schema", "required": sorted(required)}
    missing = sorted(required - set(states))
    passed = source_matches and not missing
    return passed, {
        "status": "verified" if passed else "failed",
        "missing_states": missing,
        "source_sha256_matches": source_matches,
    }


def active_markdown_state(workspace: dict[str, Any]) -> dict[str, Any] | None:
    active_id = workspace.get("active")

    def visit(value: Any) -> dict[str, Any] | None:
        if isinstance(value, dict):
            if value.get("id") == active_id and value.get("type") == "leaf":
                leaf_state = value.get("state") or {}
                if leaf_state.get("type") == "markdown":
                    return leaf_state.get("state") or {}
            for child in value.values():
                found = visit(child)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = visit(child)
                if found is not None:
                    return found
        return None

    return visit(workspace)


def obsidian_contract(
    document_path: Path,
    vault_path: Path | None,
    css_path: Path | None,
    skip_check: bool,
) -> tuple[bool, dict[str, Any]]:
    if skip_check:
        return True, {"status": "explicitly_skipped", "reason": "non-Obsidian destination"}
    if vault_path is None and css_path is None:
        return False, {"status": "not_checked", "required": ["--obsidian-vault", "--obsidian-css"]}
    if vault_path is None or css_path is None:
        return False, {"status": "incomplete_arguments", "required": ["--obsidian-vault", "--obsidian-css"]}

    try:
        css = css_path.read_text(encoding="utf-8-sig")
        workspace = json.loads(
            (vault_path / ".obsidian" / "workspace.json").read_text(encoding="utf-8-sig")
        )
        relative_document = document_path.resolve().relative_to(vault_path.resolve()).as_posix()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return False, {"status": "read_failed", "error": str(exc)}

    css_requirements = {
        "wide_body": "--file-line-width: min(96%, 1680px);",
        "mermaid_svg": ".markdown-reading-view .mermaid svg",
        "mermaid_width": "width: min(100%, 1200px);",
        "parameter_card_selector": "table:has(> thead > tr > th:nth-child(5))",
        "parameter_card_grid": "display: grid;",
        "parameter_card_no_horizontal_drag": "overflow-x: visible;",
        "ordinary_table_fixed_layout": "table-layout: fixed;",
        "ordinary_table_long_value_wrap": "word-break: break-word;",
    }
    missing_css = [name for name, token in css_requirements.items() if token not in css]
    ordinary_wrapper_match = re.search(
        r"\.markdown-reading-view\s+\.table-wrapper\s*\{[^}]*overflow-x:\s*visible\s*;",
        css,
        re.DOTALL,
    )
    ordinary_code_match = re.search(
        r"\.markdown-reading-view\s+th\s+code,\s*"
        r"\.markdown-reading-view\s+td\s+code\s*\{[^}]*white-space:\s*normal\s*;",
        css,
        re.DOTALL,
    )
    if ordinary_wrapper_match is None:
        missing_css.append("ordinary_table_no_horizontal_drag")
    if ordinary_code_match is None:
        missing_css.append("ordinary_table_code_wrap")
    active_state = active_markdown_state(workspace)
    active_file = None if active_state is None else active_state.get("file")
    active_mode = None if active_state is None else active_state.get("mode")
    passed = not missing_css and active_file == relative_document and active_mode == "preview"
    return passed, {
        "status": "verified" if passed else "failed",
        "document_relative_path": relative_document,
        "active_file": active_file,
        "active_mode": active_mode,
        "missing_css_requirements": missing_css,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a ComfyUI workflow document")
    parser.add_argument("analysis", type=Path)
    parser.add_argument("coverage", type=Path)
    parser.add_argument("document", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--node-research", type=Path, required=True)
    parser.add_argument("--control-surface", type=Path, required=True)
    parser.add_argument("--media-runtime", type=Path, required=True)
    parser.add_argument("--allow-formal", action="store_true")
    parser.add_argument("--obsidian-vault", type=Path)
    parser.add_argument("--obsidian-css", type=Path)
    parser.add_argument("--skip-obsidian-render-check", action="store_true")
    args = parser.parse_args()

    try:
        analysis = json.loads(args.analysis.read_text(encoding="utf-8-sig"))
        coverage = json.loads(args.coverage.read_text(encoding="utf-8-sig"))
        node_research = json.loads(args.node_research.read_text(encoding="utf-8-sig"))
        control_surface = json.loads(args.control_surface.read_text(encoding="utf-8-sig"))
        media_runtime = json.loads(args.media_runtime.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Invalid analysis input: {exc}") from exc
    document = args.document.read_text(encoding="utf-8-sig")
    headings = [match.group(2) for match in HEADING_RE.finditer(document)]
    heading_set = set(headings)
    link_targets = [match.group(1) for match in SAME_NOTE_LINK_RE.finditer(document)]
    missing_targets = sorted({target for target in link_targets if target not in heading_set})
    node_headings = [heading for heading in headings if heading.startswith("节点 ID ")]
    legacy_node_headings = [
        heading
        for heading in headings
        if re.match(r"^(?:节点 )?ID\s+", heading) and not heading.startswith("节点 ID ")
    ]
    unsafe_node_headings = [
        heading for heading in node_headings if UNSAFE_HEADING_RE.search(heading)
    ] + legacy_node_headings
    node_targets = {target for target in link_targets if target.startswith("节点 ID ")}
    unlinked_node_headings = sorted(set(node_headings) - node_targets)
    placeholders = sorted(set(PLACEHOLDER_RE.findall(document)))
    missing_chapters = [heading for heading in REQUIRED_HEADINGS if heading not in document]
    secret_hits = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(document)]
    missing_nodes = node_inventory_missing(document, analysis.get("nodes") or [])
    missing_parameters = mapped_parameter_missing(
        document, coverage.get("parameters") or []
    )
    unresolved_count = int(coverage.get("unresolved_widget_count") or 0)
    mapped_parameter_count = len(coverage.get("parameters") or [])
    mermaid_blocks = MERMAID_BLOCK_RE.findall(document)
    bilingual_flowcharts = [
        block
        for block in mermaid_blocks
        if re.search(r"(?m)^\s*flowchart\s+TB\b", block)
        and re.search(r"[\u4e00-\u9fff]", block)
    ]
    parameter_table_count = len(PARAMETER_TABLE_HEADER_RE.findall(document))
    obsidian_passed, obsidian_detail = obsidian_contract(
        args.document,
        args.obsidian_vault,
        args.obsidian_css,
        args.skip_obsidian_render_check,
    )
    node_research_passed, node_research_detail = node_research_contract(
        analysis, node_research
    )
    control_surface_passed, control_surface_detail = control_surface_contract(
        analysis, control_surface, document
    )
    media_runtime_passed, media_runtime_detail = media_runtime_contract(
        analysis, media_runtime
    )

    checks = [
        check("ten_chapter_structure", not missing_chapters, missing_chapters),
        check("template_placeholders_resolved", not placeholders, placeholders),
        check("same_note_links_present", bool(link_targets), len(link_targets)),
        check("same_note_link_targets_exact", not missing_targets, missing_targets),
        check("safe_plain_node_headings", not unsafe_node_headings, unsafe_node_headings),
        check("node_detail_headings_linked", not unlinked_node_headings, unlinked_node_headings),
        check("root_node_inventory_coverage", not missing_nodes, missing_nodes),
        check("mapped_parameter_names_present", not missing_parameters, missing_parameters),
        check(
            "node_research_matrix_coverage",
            node_research_passed,
            node_research_detail,
        ),
        check(
            "node_research_coverage_declared",
            "节点资料查证" in document,
            "document must declare node research coverage",
        ),
        check("control_surface_inventory", control_surface_passed, control_surface_detail),
        check("media_runtime_inventory", media_runtime_passed, media_runtime_detail),
        check(
            "obsidian_document_class_declared",
            bool(OBSIDIAN_CLASS_RE.search(document)),
            "comfyui-workflow-doc",
        ),
        check(
            "bilingual_top_down_mermaid_source",
            bool(bilingual_flowcharts),
            {"mermaid_blocks": len(mermaid_blocks), "matching_blocks": len(bilingual_flowcharts)},
        ),
        check(
            "five_field_parameter_card_source",
            mapped_parameter_count == 0 or parameter_table_count > 0,
            {"mapped_parameters": mapped_parameter_count, "parameter_tables": parameter_table_count},
        ),
        check("obsidian_render_configuration", obsidian_passed, obsidian_detail),
        check("no_secret_or_session_pattern", not secret_hits, secret_hits),
        check(
            "candidate_or_explicit_formal_mode",
            args.allow_formal or "候选版" in document,
            "formal mode allowed" if args.allow_formal else "candidate marker required",
        ),
    ]
    passed = all(item["passed"] for item in checks)
    if not passed:
        status = "FAIL_VALIDATION"
    elif unresolved_count:
        status = "PASS_WITH_UNRESOLVED_NODES"
    else:
        status = "PASS"
    report = {
        "status": status,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "document_path": str(args.document.resolve()),
        "document_sha256": sha256_file(args.document),
        "source_sha256": analysis.get("source_sha256"),
        "format": analysis.get("format"),
        "checks_passed": sum(item["passed"] for item in checks),
        "checks_total": len(checks),
        "checks": checks,
        "unique_heading_link_targets": len(set(link_targets)),
        "unresolved_widget_count": unresolved_count,
        "node_research_coverage": node_research_detail,
        "control_surface_coverage": control_surface_detail,
        "media_runtime_coverage": media_runtime_detail,
        "obsidian_render_configuration": obsidian_detail,
        "formal_document_overwritten": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": status,
                "passed": report["checks_passed"],
                "total": report["checks_total"],
            },
            ensure_ascii=False,
        )
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
