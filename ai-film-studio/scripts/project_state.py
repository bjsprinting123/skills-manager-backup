from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone


STATE_DIR = ".ai-film"
STATE_FILE = "project-state.json"
VALID_STATUS = {"draft", "accepted", "stale", "retired"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def state_path(project: Path) -> Path:
    return project / STATE_DIR / STATE_FILE


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(project: Path) -> dict:
    path = state_path(project)
    if not path.exists():
        raise SystemExit(f"project state missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def relpath(project: Path, value: str) -> str:
    p = Path(value)
    if p.is_absolute():
        try:
            return p.resolve().relative_to(project.resolve()).as_posix()
        except ValueError:
            raise SystemExit("artifact path must live inside project root")
    return p.as_posix()


def dependents(state: dict, slot: str) -> list[str]:
    return [
        name
        for name, item in state["artifacts"].items()
        if slot in item.get("depends_on", [])
    ]


def downstream_closure(state: dict, slot: str) -> list[str]:
    out: list[str] = []
    seen = {slot}
    queue = [slot]
    while queue:
        current = queue.pop(0)
        for child in dependents(state, current):
            if child in seen:
                continue
            seen.add(child)
            out.append(child)
            queue.append(child)
    return out


def mark_downstream_stale(state: dict, slot: str, reason: str) -> list[str]:
    changed = []
    for child in downstream_closure(state, slot):
        current = state["artifacts"][child].get("current")
        if not current or current.get("status") in {"retired", "stale"}:
            continue
        current["status"] = "stale"
        current["stale_reason"] = reason
        current["updated_at"] = now()
        changed.append(child)
    return changed


def validate_state(project: Path, state: dict) -> list[str]:
    errors: list[str] = []
    artifacts = state.get("artifacts", {})

    for slot, item in artifacts.items():
        current = item.get("current")
        if not current:
            errors.append(f"{slot}: missing current")
            continue
        status = current.get("status")
        if status not in VALID_STATUS:
            errors.append(f"{slot}: invalid status {status!r}")
        for dep in item.get("depends_on", []):
            if dep not in artifacts:
                errors.append(f"{slot}: missing dependency {dep}")
        if status == "accepted":
            p = project / current.get("path", "")
            if not current.get("path") or not p.is_file():
                errors.append(f"{slot}: accepted artifact file missing: {p}")
            else:
                recorded = current.get("sha256")
                actual = file_sha256(p)
                if not recorded:
                    errors.append(f"{slot}: accepted artifact missing sha256")
                elif recorded != actual:
                    errors.append(f"{slot}: accepted artifact bytes changed without a new version")
            for dep in item.get("depends_on", []):
                if dep in artifacts:
                    dep_status = artifacts[dep].get("current", {}).get("status")
                    if dep_status != "accepted":
                        errors.append(f"{slot}: accepted artifact depends on {dep} with status {dep_status}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def walk(slot: str) -> None:
        if slot in visiting:
            errors.append(f"dependency cycle at {slot}")
            return
        if slot in visited or slot not in artifacts:
            return
        visiting.add(slot)
        for dep in artifacts[slot].get("depends_on", []):
            walk(dep)
        visiting.remove(slot)
        visited.add(slot)

    for slot in artifacts:
        walk(slot)
    return errors


def cmd_init(args) -> int:
    project = Path(args.project).resolve()
    project.mkdir(parents=True, exist_ok=True)
    path = state_path(project)
    if path.exists() and not args.force:
        raise SystemExit(f"state already exists: {path}")
    state = {
        "schema_version": 1,
        "project_id": args.project_id or project.name,
        "created_at": now(),
        "updated_at": now(),
        "artifacts": {},
        "events": [],
    }
    atomic_write(path, state)
    print(json.dumps({"status": "INITIALIZED", "state": str(path)}, ensure_ascii=False))
    return 0


def cmd_set(args) -> int:
    project = Path(args.project).resolve()
    state = load(project)
    if args.status not in VALID_STATUS:
        raise SystemExit(f"invalid status: {args.status}")

    slot = args.slot
    path = relpath(project, args.path)
    deps = list(dict.fromkeys(args.depends_on or []))
    for dep in deps:
        if dep not in state["artifacts"]:
            raise SystemExit(f"dependency not registered: {dep}")
        if args.status == "accepted" and state["artifacts"][dep]["current"]["status"] != "accepted":
            raise SystemExit(
                f"accepted artifact cannot depend on non-accepted {dep}: "
                f"{state['artifacts'][dep]['current']['status']}"
            )
    if args.status == "accepted" and not (project / path).is_file():
        raise SystemExit(f"accepted artifact file missing: {project / path}")

    artifact_path = project / path
    new_sha = file_sha256(artifact_path) if artifact_path.is_file() else None

    previous = state["artifacts"].get(slot, {}).get("current")
    history = state["artifacts"].get(slot, {}).get("history", [])
    changed_version = bool(previous and previous.get("version") != args.version)
    if (
        previous
        and previous.get("version") == args.version
        and previous.get("sha256")
        and new_sha
        and previous["sha256"] != new_sha
    ):
        raise SystemExit(
            f"{slot}: content changed but version stayed {args.version}; use a new version"
        )
    if previous:
        history.append(previous)

    state["artifacts"][slot] = {
        "depends_on": deps,
        "current": {
            "version": args.version,
            "path": path,
            "status": args.status,
            "sha256": new_sha,
            "updated_at": now(),
        },
        "history": history,
    }

    stale = []
    if changed_version:
        stale = mark_downstream_stale(
            state,
            slot,
            f"{slot} changed to version {args.version}",
        )
    state["events"].append(
        {
            "at": now(),
            "action": "set-artifact",
            "slot": slot,
            "version": args.version,
            "status": args.status,
            "stale_downstream": stale,
        }
    )
    state["updated_at"] = now()
    errors = validate_state(project, state)
    if errors:
        print(json.dumps({"status": "BLOCKED", "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    atomic_write(state_path(project), state)
    print(
        json.dumps(
            {"status": "UPDATED", "slot": slot, "stale_downstream": stale},
            ensure_ascii=False,
        )
    )
    return 0


def cmd_status(args) -> int:
    project = Path(args.project).resolve()
    state = load(project)
    rows = {}
    for slot, item in state["artifacts"].items():
        current = item["current"]
        rows[slot] = {
            "version": current["version"],
            "status": current["status"],
            "path": current["path"],
            "depends_on": item.get("depends_on", []),
        }
    print(json.dumps({"project_id": state["project_id"], "artifacts": rows}, ensure_ascii=False, indent=2))
    return 0


def cmd_impact(args) -> int:
    project = Path(args.project).resolve()
    state = load(project)
    if args.slot not in state["artifacts"]:
        raise SystemExit(f"unknown artifact slot: {args.slot}")
    print(
        json.dumps(
            {"slot": args.slot, "downstream": downstream_closure(state, args.slot)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_validate(args) -> int:
    project = Path(args.project).resolve()
    state = load(project)
    errors = validate_state(project, state)
    print(json.dumps({"status": "FAIL" if errors else "PASS", "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Persistent AI film project state")
    sub = p.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init")
    init.add_argument("project")
    init.add_argument("--project-id")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    setp = sub.add_parser("set")
    setp.add_argument("project")
    setp.add_argument("slot")
    setp.add_argument("--version", required=True)
    setp.add_argument("--path", required=True)
    setp.add_argument("--status", default="accepted", choices=sorted(VALID_STATUS))
    setp.add_argument("--depends-on", nargs="*", default=[])
    setp.set_defaults(func=cmd_set)

    status = sub.add_parser("status")
    status.add_argument("project")
    status.set_defaults(func=cmd_status)

    impact = sub.add_parser("impact")
    impact.add_argument("project")
    impact.add_argument("slot")
    impact.set_defaults(func=cmd_impact)

    val = sub.add_parser("validate")
    val.add_argument("project")
    val.set_defaults(func=cmd_validate)
    return p


def main() -> int:
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
