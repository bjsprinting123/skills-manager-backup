from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


ANNOTATION_TYPES = {"Note", "MarkdownNote", "Label (rgthree)"}
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
SECRET_PATTERNS = (
    re.compile(r"(?i)tvly-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)(?:SESSDATA|bili_jct|DedeUserID__ckMd5)\s*[=:]\s*\S{8,}"),
    re.compile(
        r"(?i)\b(?:password|api[_-]?key|access[_-]?token|refresh[_-]?token|"
        r"cookie|authorization|client[_-]?secret)\s*[:=]\s*"
        r"(?:\"[^\"]*\"|'[^']*'|[^\s;,]+)"
    ),
    re.compile(r"(?i)Bearer\s+[^\s\"']+"),
    re.compile(r"(?i)https?://[^/@\s]+@"),
    re.compile(r"(?i)[?&](?:token|key|signature|password)=[^&#\s]+"),
)
SECRET_NAME_RE = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|"
    r"password|cookie|sessdata|bili_jct|authorization|client[_-]?secret)"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit("Invalid JSON: the root value must be an object")
    return value, raw


def redacted_record(value: str, reason: str) -> dict[str, Any]:
    return {
        "redacted": True,
        "reason": reason,
        "character_count": len(value),
        "sha256": sha256_bytes(value.encode("utf-8")),
    }


def sanitize_value(node_type: str, name: str, value: Any) -> tuple[Any, bool]:
    if SECRET_NAME_RE.search(name) and value not in (None, "", False):
        raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        return redacted_record(str(raw), "sensitive_named_field"), True
    if isinstance(value, str):
        if any(pattern.search(value) for pattern in SECRET_PATTERNS):
            return redacted_record(value, "secret_or_session_pattern"), True
        if "TextEncode" in node_type and (name == "text" or len(value) >= 80):
            return redacted_record(value, "prompt_content"), True
    return value, False


def sorted_node_id(value: Any) -> tuple[int, int | str]:
    text = str(value)
    if text.lstrip("-").isdigit():
        return 0, int(text)
    return 1, text


def subgraph_items(graph: dict[str, Any]) -> list[dict[str, Any]]:
    definitions = graph.get("definitions") or {}
    raw = definitions.get("subgraphs") or []
    if isinstance(raw, dict):
        candidates: Iterable[Any] = raw.values()
    elif isinstance(raw, list):
        candidates = raw
    else:
        candidates = []
    return [item for item in candidates if isinstance(item, dict)]


def collect_graphs(root: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    graphs: list[tuple[str, dict[str, Any]]] = [("root", root)]
    seen: set[str] = set()

    def visit(parent_scope: str, graph: dict[str, Any]) -> None:
        for index, subgraph in enumerate(subgraph_items(graph)):
            subgraph_id = str(subgraph.get("id") or f"unnamed-{index}")
            identity = f"{parent_scope}/{subgraph_id}"
            if identity in seen:
                continue
            seen.add(identity)
            scope = f"subgraph:{subgraph_id}"
            graphs.append((scope, subgraph))
            visit(scope, subgraph)

    visit("root", root)
    return graphs


def normalize_link(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, list) and len(raw) >= 6:
        return {
            "link_id": raw[0],
            "from_node_id": raw[1],
            "from_slot": raw[2],
            "to_node_id": raw[3],
            "to_slot": raw[4],
            "data_type": raw[5],
        }
    if isinstance(raw, dict):
        if not {"origin_id", "target_id"}.issubset(raw):
            return None
        return {
            "link_id": raw.get("id"),
            "from_node_id": raw.get("origin_id"),
            "from_slot": raw.get("origin_slot", 0),
            "to_node_id": raw.get("target_id"),
            "to_slot": raw.get("target_slot", 0),
            "data_type": raw.get("type"),
        }
    return None


def port_name(node: dict[str, Any] | None, collection: str, slot: Any) -> str | int:
    if node is None:
        return f"boundary_slot_{slot}"
    ports = node.get(collection) or []
    if isinstance(slot, int) and 0 <= slot < len(ports):
        item = ports[slot]
        if isinstance(item, dict):
            return item.get("name", slot)
    return slot


def parse_ui_workflow(
    data: dict[str, Any], widget_schema: dict[str, list[str]] | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    widget_schema = widget_schema or {}
    graphs = collect_graphs(data)
    definition_names = {
        str(graph.get("id")): graph.get("name") or str(graph.get("id"))
        for scope, graph in graphs
        if scope != "root" and graph.get("id") is not None
    }

    node_rows: list[dict[str, Any]] = []
    parameter_rows: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    physical_links: list[dict[str, Any]] = []
    semantic_links: list[dict[str, Any]] = []
    graph_rows: list[dict[str, Any]] = []

    for scope, graph in graphs:
        raw_nodes = [item for item in (graph.get("nodes") or []) if isinstance(item, dict)]
        nodes = {str(node.get("id")): node for node in raw_nodes}
        scoped_physical: list[dict[str, Any]] = []
        adjacency: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for node in sorted(raw_nodes, key=lambda item: sorted_node_id(item.get("id"))):
            node_id = node.get("id")
            node_type = str(node.get("type", "<unknown>"))
            node_key = f"{scope}/{node_id}"
            named = node.get("widgets_values_named")
            raw_widgets = node.get("widgets_values")
            mapped_count = 0
            unresolved_count = 0

            if isinstance(named, dict):
                for name, raw_value in named.items():
                    value, was_redacted = sanitize_value(node_type, str(name), raw_value)
                    category = (
                        "annotation_content"
                        if node_type in ANNOTATION_TYPES
                        else "frontend_state"
                        if name == "control_after_generate"
                        else "execution_parameter"
                    )
                    parameter_rows.append(
                        {
                            "parameter_key": f"{node_key}:{name}",
                            "node_key": node_key,
                            "node_id": node_id,
                            "scope": scope,
                            "node_type": node_type,
                            "parameter": str(name),
                            "category": category,
                            "current_value": value,
                            "redacted": was_redacted,
                            "mapping_status": "mapped_by_widgets_values_named",
                        }
                    )
                    mapped_count += 1
            elif isinstance(raw_widgets, dict):
                for name, raw_value in raw_widgets.items():
                    value, was_redacted = sanitize_value(node_type, str(name), raw_value)
                    parameter_rows.append(
                        {
                            "parameter_key": f"{node_key}:{name}",
                            "node_key": node_key,
                            "node_id": node_id,
                            "scope": scope,
                            "node_type": node_type,
                            "parameter": str(name),
                            "category": "execution_parameter",
                            "current_value": value,
                            "redacted": was_redacted,
                            "mapping_status": "mapped_by_named_widgets_object",
                        }
                    )
                    mapped_count += 1
            elif isinstance(raw_widgets, list) and node_type in widget_schema:
                names = widget_schema[node_type]
                if len(names) == len(raw_widgets):
                    for name, raw_value in zip(names, raw_widgets, strict=True):
                        value, was_redacted = sanitize_value(node_type, name, raw_value)
                        category = (
                            "annotation_content"
                            if node_type in ANNOTATION_TYPES
                            else "frontend_state"
                            if name == "control_after_generate"
                            else "execution_parameter"
                        )
                        parameter_rows.append(
                            {
                                "parameter_key": f"{node_key}:{name}",
                                "node_key": node_key,
                                "node_id": node_id,
                                "scope": scope,
                                "node_type": node_type,
                                "parameter": name,
                                "category": category,
                                "current_value": value,
                                "redacted": was_redacted,
                                "mapping_status": "mapped_by_authoritative_widget_schema",
                            }
                        )
                        mapped_count += 1
                else:
                    for index, raw_value in enumerate(raw_widgets):
                        value, was_redacted = sanitize_value(
                            node_type, f"widget_{index}", raw_value
                        )
                        unresolved.append(
                            {
                                "unresolved_key": f"{node_key}:widget_{index}",
                                "node_key": node_key,
                                "node_id": node_id,
                                "scope": scope,
                                "node_type": node_type,
                                "widget_index": index,
                                "raw_value": value,
                                "redacted": was_redacted,
                                "category_hint": "unknown",
                                "reason": "widget_schema_length_mismatch",
                                "schema_field_count": len(names),
                                "source_widget_count": len(raw_widgets),
                            }
                        )
                        unresolved_count += 1
            elif isinstance(raw_widgets, list):
                for index, raw_value in enumerate(raw_widgets):
                    value, was_redacted = sanitize_value(node_type, f"widget_{index}", raw_value)
                    unresolved.append(
                        {
                            "unresolved_key": f"{node_key}:widget_{index}",
                            "node_key": node_key,
                            "node_id": node_id,
                            "scope": scope,
                            "node_type": node_type,
                            "widget_index": index,
                            "raw_value": value,
                            "redacted": was_redacted,
                            "category_hint": (
                                "annotation_content" if node_type in ANNOTATION_TYPES else "unknown"
                            ),
                            "reason": "widget_name_not_present_in_source",
                        }
                    )
                    unresolved_count += 1

            properties = node.get("properties") or {}
            is_subgraph_instance = node_type in definition_names or bool(UUID_RE.match(node_type))
            node_rows.append(
                {
                    "node_key": node_key,
                    "scope": scope,
                    "id": node_id,
                    "type": node_type,
                    "resolved_display_type": (
                        f"Subgraph {definition_names.get(node_type, '<definition not found>')}"
                        if is_subgraph_instance
                        else node_type
                    ),
                    "is_subgraph_instance": is_subgraph_instance,
                    "subgraph_definition_found": node_type in definition_names,
                    "title": node.get("title"),
                    "mode": node.get("mode", 0),
                    "pinned": bool((node.get("flags") or {}).get("pinned", False)),
                    "package": properties.get("cnr_id"),
                    "version": properties.get("ver"),
                    "proxy_widgets": properties.get("proxyWidgets") or [],
                    "mapped_widget_count": mapped_count,
                    "unresolved_widget_count": unresolved_count,
                    "inputs": [
                        {
                            "name": item.get("name"),
                            "type": item.get("type"),
                            "link_id": item.get("link"),
                        }
                        for item in (node.get("inputs") or [])
                        if isinstance(item, dict)
                    ],
                    "outputs": [
                        {
                            "name": item.get("name"),
                            "type": item.get("type"),
                            "link_ids": item.get("links"),
                        }
                        for item in (node.get("outputs") or [])
                        if isinstance(item, dict)
                    ],
                }
            )

        for raw_link in graph.get("links") or []:
            link = normalize_link(raw_link)
            if link is None:
                continue
            source = nodes.get(str(link["from_node_id"]))
            target = nodes.get(str(link["to_node_id"]))
            row = {
                "scope": scope,
                "link_id": link["link_id"],
                "from_node_key": f"{scope}/{link['from_node_id']}",
                "from_node_id": link["from_node_id"],
                "from_node_type": source.get("type") if source else "<subgraph-input-boundary>",
                "from_port": port_name(source, "outputs", link["from_slot"]),
                "to_node_key": f"{scope}/{link['to_node_id']}",
                "to_node_id": link["to_node_id"],
                "to_node_type": target.get("type") if target else "<subgraph-output-boundary>",
                "to_port": port_name(target, "inputs", link["to_slot"]),
                "data_type": link["data_type"],
            }
            scoped_physical.append(row)
            physical_links.append(row)
            adjacency[str(link["from_node_id"])].append(row)

        def follow(origin: dict[str, Any], edge: dict[str, Any], path: list[Any], seen: set[str]) -> None:
            target_id = str(edge["to_node_id"])
            if target_id in seen:
                return
            target = nodes.get(target_id)
            if target is None or target.get("type") != "Reroute":
                semantic_links.append(
                    {
                        "scope": scope,
                        "from_node_key": origin["from_node_key"],
                        "from_node_id": origin["from_node_id"],
                        "from_node_type": origin["from_node_type"],
                        "from_port": origin["from_port"],
                        "to_node_key": edge["to_node_key"],
                        "to_node_id": edge["to_node_id"],
                        "to_node_type": edge["to_node_type"],
                        "to_port": edge["to_port"],
                        "data_type": edge["data_type"],
                        "physical_link_path": path + [edge["link_id"]],
                        "physical_path_includes_reroute": len(path) > 0,
                    }
                )
                return
            for next_edge in adjacency.get(target_id, []):
                follow(origin, next_edge, path + [edge["link_id"]], seen | {target_id})

        for node_id, node in nodes.items():
            if node.get("type") == "Reroute":
                continue
            for first_edge in adjacency.get(node_id, []):
                follow(first_edge, first_edge, [], {node_id})

        graph_rows.append(
            {
                "scope": scope,
                "id": graph.get("id"),
                "name": graph.get("name"),
                "node_count": len(raw_nodes),
                "link_count": len(scoped_physical),
                "group_count": len(graph.get("groups") or []),
                "inputs": graph.get("inputs") or [],
                "outputs": graph.get("outputs") or [],
                "widgets": graph.get("widgets") or [],
            }
        )

    type_counts = Counter(row["type"] for row in node_rows)
    parameter_categories = Counter(row["category"] for row in parameter_rows)
    root_nodes = [row for row in node_rows if row["scope"] == "root"]
    missing_definitions = sorted(
        {
            row["type"]
            for row in node_rows
            if row["is_subgraph_instance"] and not row["subgraph_definition_found"]
        }
    )
    parsed = {
        "format": "comfyui_ui_workflow",
        "workflow_metadata": {
            "id": data.get("id"),
            "revision": data.get("revision"),
            "version": data.get("version"),
        },
        "statistics": {
            "root_node_count": len(root_nodes),
            "expanded_definition_node_count": len(node_rows) - len(root_nodes),
            "total_indexed_node_count": len(node_rows),
            "node_type_count": len(type_counts),
            "node_type_counts": dict(sorted(type_counts.items())),
            "subgraph_definition_count": len(graphs) - 1,
            "subgraph_instance_count": sum(row["is_subgraph_instance"] for row in node_rows),
            "missing_subgraph_definition_count": len(missing_definitions),
            "group_count": sum(row["group_count"] for row in graph_rows),
            "physical_link_count": len(physical_links),
            "semantic_link_count": len(semantic_links),
        },
        "missing_subgraph_definitions": missing_definitions,
        "graphs": graph_rows,
        "nodes": node_rows,
        "physical_links": physical_links,
        "semantic_links": semantic_links,
    }
    coverage = {
        "format": "comfyui_ui_workflow",
        "named_widget_field_count": len(parameter_rows),
        "category_counts": dict(sorted(parameter_categories.items())),
        "mapped_field_count": len(parameter_rows),
        "unresolved_widget_count": len(unresolved),
        "redacted_field_count": sum(row["redacted"] for row in parameter_rows)
        + sum(row["redacted"] for row in unresolved),
        "parameters": parameter_rows,
        "unresolved_widgets": unresolved,
        "coverage_status": "complete" if not unresolved else "has_unresolved_widgets",
    }
    return parsed, coverage


def api_prompt_payload(data: dict[str, Any]) -> dict[str, Any] | None:
    candidates = [data]
    if isinstance(data.get("prompt"), dict):
        candidates.insert(0, data["prompt"])
    for candidate in candidates:
        if candidate and all(
            isinstance(value, dict) and "class_type" in value for value in candidate.values()
        ):
            return candidate
    return None


def parse_api_prompt(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    prompt = api_prompt_payload(data)
    if prompt is None:
        raise SystemExit("Unsupported JSON: expected ComfyUI UI Workflow or API Prompt")
    node_ids = {str(key) for key in prompt}
    nodes: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    parameters: list[dict[str, Any]] = []
    for node_id in sorted(node_ids, key=sorted_node_id):
        node = prompt[node_id]
        node_type = str(node.get("class_type", "<unknown>"))
        node_key = f"api/{node_id}"
        node_inputs = node.get("inputs") or {}
        for name, raw_value in node_inputs.items():
            if (
                isinstance(raw_value, list)
                and len(raw_value) == 2
                and str(raw_value[0]) in node_ids
                and isinstance(raw_value[1], int)
            ):
                links.append(
                    {
                        "scope": "api",
                        "link_id": f"api:{node_id}:{name}",
                        "from_node_key": f"api/{raw_value[0]}",
                        "from_node_id": str(raw_value[0]),
                        "from_output_slot": raw_value[1],
                        "to_node_key": node_key,
                        "to_node_id": node_id,
                        "to_node_type": node_type,
                        "to_port": name,
                    }
                )
            else:
                value, was_redacted = sanitize_value(node_type, str(name), raw_value)
                parameters.append(
                    {
                        "parameter_key": f"{node_key}:{name}",
                        "node_key": node_key,
                        "node_id": node_id,
                        "scope": "api",
                        "node_type": node_type,
                        "parameter": str(name),
                        "category": "execution_parameter",
                        "current_value": value,
                        "redacted": was_redacted,
                        "mapping_status": "mapped_from_api_input",
                    }
                )
        nodes.append(
            {
                "node_key": node_key,
                "scope": "api",
                "id": node_id,
                "type": node_type,
                "resolved_display_type": node_type,
                "is_subgraph_instance": False,
                "subgraph_definition_found": False,
                "title": (node.get("_meta") or {}).get("title"),
                "mapped_widget_count": sum(
                    row["node_key"] == node_key for row in parameters
                ),
                "unresolved_widget_count": 0,
            }
        )
    parsed = {
        "format": "comfyui_api_prompt",
        "workflow_metadata": {},
        "statistics": {
            "root_node_count": len(nodes),
            "expanded_definition_node_count": 0,
            "total_indexed_node_count": len(nodes),
            "node_type_count": len({node["type"] for node in nodes}),
            "subgraph_definition_count": 0,
            "subgraph_instance_count": 0,
            "missing_subgraph_definition_count": 0,
            "group_count": 0,
            "physical_link_count": len(links),
            "semantic_link_count": len(links),
        },
        "source_limitations": [
            "API Prompt JSON normally omits canvas layout, groups, physical link IDs, and front-end-only state."
        ],
        "missing_subgraph_definitions": [],
        "graphs": [{"scope": "api", "node_count": len(nodes), "link_count": len(links)}],
        "nodes": nodes,
        "physical_links": links,
        "semantic_links": links,
    }
    coverage = {
        "format": "comfyui_api_prompt",
        "named_widget_field_count": len(parameters),
        "mapped_field_count": len(parameters),
        "unresolved_widget_count": 0,
        "redacted_field_count": sum(row["redacted"] for row in parameters),
        "parameters": parameters,
        "unresolved_widgets": [],
        "coverage_status": "complete_with_api_prompt_limitations",
    }
    return parsed, coverage


def load_widget_schema(path: Path | None) -> tuple[dict[str, list[str]], dict[str, Any] | None]:
    if path is None:
        return {}, None
    value, raw = read_json(path)
    raw_nodes = value.get("nodes", value)
    if not isinstance(raw_nodes, dict):
        raise SystemExit("Invalid widget schema: expected an object or a nodes object")
    schema: dict[str, list[str]] = {}
    for node_type, names in raw_nodes.items():
        if not isinstance(node_type, str) or not isinstance(names, list) or not all(
            isinstance(name, str) and name for name in names
        ):
            raise SystemExit(f"Invalid widget schema entry: {node_type!r}")
        schema[node_type] = names
    return schema, {
        "path": str(path.resolve()),
        "sha256": sha256_bytes(raw),
        "node_type_count": len(schema),
    }


def analyze(
    source: Path, widget_schema_path: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    data, raw = read_json(source)
    widget_schema, schema_metadata = load_widget_schema(widget_schema_path)
    if isinstance(data.get("nodes"), list):
        parsed, coverage = parse_ui_workflow(data, widget_schema)
    elif api_prompt_payload(data) is not None:
        parsed, coverage = parse_api_prompt(data)
    else:
        raise SystemExit("Unsupported JSON: expected ComfyUI UI Workflow or API Prompt")
    common = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_path": str(source.resolve()),
        "source_size_bytes": len(raw),
        "source_sha256": sha256_bytes(raw),
        "analyzer": "comfyui-workflow-docs/analyze_workflow.py",
        "widget_schema": schema_metadata,
    }
    return {**common, **parsed}, {**common, **coverage}


def write_outputs(parsed: dict[str, Any], coverage: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "01-工作流解析结果.json").write_text(
        json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "02-参数覆盖对账.json").write_text(
        json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a ComfyUI workflow JSON")
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--widget-schema", type=Path)
    args = parser.parse_args()
    parsed, coverage = analyze(args.source, args.widget_schema)
    write_outputs(parsed, coverage, args.output_dir)
    print(
        json.dumps(
            {
                "format": parsed["format"],
                "statistics": parsed["statistics"],
                "coverage": coverage["coverage_status"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
