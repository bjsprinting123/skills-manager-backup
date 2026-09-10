"""Validate declared knowledge destinations, not factual quality or permission."""
import json
from pathlib import Path
import sys

AREAS = {"workflow", "model_library", "video_index", "author_index", "node_guide",
         "application_guide", "general_guide", "performance"}
PENDING = {"pending_research", "pending_approval", "blocked"}


def initial_checklist(scope):
    return {"scope": scope, "destinations": [
        {"area": area, "status": "pending_research",
         "reason": "尚未评估本次证据对该知识目标的影响；不是发布授权。",
         "owner": "comfyui-model-library" if area == "model_library" else "comfyui-workflow-docs",
         "next_action": "核对范围、证据和已有授权，填写更新/无需更新/待办及依据；有待办必须在交付时提醒。"}
        for area in sorted(AREAS)]}


def validate(data):
    errors, pending = [], []
    if not isinstance(data, dict) or not isinstance(data.get("destinations"), list):
        return {"status": "FAIL", "errors": ["destinations must be a list"], "pending": []}
    if not data.get("scope"):
        errors.append("scope missing")
    seen = set()
    for entry in data["destinations"]:
        if not isinstance(entry, dict):
            errors.append("invalid destination")
            continue
        area, status = entry.get("area"), entry.get("status")
        if area not in AREAS or area in seen:
            errors.append("unknown or duplicate area: " + str(area))
        seen.add(area)
        if status not in PENDING | {"updated", "no_change", "out_of_scope"}:
            errors.append("invalid status: " + str(area))
        if not entry.get("reason"):
            errors.append("reason missing: " + str(area))
        if status in PENDING:
            pending.append(area)
            if not entry.get("next_action") or not entry.get("owner"):
                errors.append("pending needs next_action and owner: " + str(area))
        if status == "updated":
            fields = ["evidence_paths"] + (["receipt_paths"] if area == "model_library" else [])
            for field in fields:
                paths = entry.get(field)
                if not isinstance(paths, list) or not paths:
                    errors.append(field + " missing: " + str(area))
                    continue
                for path in paths:
                    if not isinstance(path, str) or not Path(path).is_absolute() or not Path(path).is_file():
                        errors.append("missing absolute evidence file: " + str(path))
    if seen != AREAS:
        errors.append("destinations do not cover all areas")
    return {"status": "FAIL" if errors else "PARTIAL" if pending else "PASS_CLOSED",
            "errors": errors, "pending": pending}


if __name__ == "__main__":
    try:
        result = validate(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig")))
    except (OSError, ValueError, IndexError) as exc:
        result = {"status": "FAIL", "errors": [type(exc).__name__], "pending": []}
    print(json.dumps(result, ensure_ascii=False))
    sys.exit({"PASS_CLOSED": 0, "PARTIAL": 2, "FAIL": 1}[result["status"]])
