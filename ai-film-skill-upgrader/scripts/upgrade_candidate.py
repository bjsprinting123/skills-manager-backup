from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


def find_repo_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / "system" / "registry" / "capabilities.json").is_file() and (parent / "skills").is_dir():
            return parent
    canonical = Path(r"E:\AI短剧\技能仓库")
    if (canonical / "system" / "registry" / "capabilities.json").is_file() and (canonical / "skills").is_dir():
        return canonical
    raise RuntimeError("AI film skill repository root not found")


ROOT = find_repo_root(Path(__file__).resolve().parent)
SYSTEM = ROOT / "system"
CANDIDATES = SYSTEM / "upgrade" / "candidates"
TEMPLATE = SYSTEM / "upgrade" / "candidate-template.json"
REGISTRY = SYSTEM / "registry" / "capabilities.json"

CLASSIFICATIONS = {
    "knowledge",
    "recipe",
    "capability_implementation",
    "provider_model",
    "architecture_change",
}
STATUSES = {
    "inbox",
    "research",
    "sandbox",
    "ready_for_review",
    "approved_pending_release",
    "promoted",
    "suspended",
    "rejected",
}
EVIDENCE = {f"E{i}" for i in range(6)}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def known_capabilities() -> set[str]:
    return {item["id"] for item in load(REGISTRY)["capabilities"]}


def candidate_path(candidate_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", candidate_id).strip("-")
    if not safe:
        raise SystemExit("candidate_id becomes empty after sanitization")
    return CANDIDATES / f"{safe}.json"


def validate(candidate: dict) -> list[str]:
    errors: list[str] = []
    required = {
        "candidate_id",
        "title",
        "source_type",
        "source",
        "version_or_date",
        "license",
        "capability_ids",
        "classification",
        "evidence_level",
        "diff",
        "benchmark",
        "impact",
        "rollback",
        "status",
    }
    missing = sorted(required - set(candidate))
    if missing:
        errors.append(f"missing fields: {missing}")
    if candidate.get("classification") not in CLASSIFICATIONS:
        errors.append(f"invalid classification: {candidate.get('classification')!r}")
    if candidate.get("status") not in STATUSES:
        errors.append(f"invalid status: {candidate.get('status')!r}")
    if candidate.get("evidence_level") not in EVIDENCE:
        errors.append(f"invalid evidence_level: {candidate.get('evidence_level')!r}")
    known = known_capabilities()
    for cap in candidate.get("capability_ids", []):
        if cap not in known:
            errors.append(f"unknown capability: {cap}")
    if candidate.get("classification") == "capability_implementation" and not candidate.get("implementation"):
        errors.append("capability_implementation requires implementation")
    if not isinstance(candidate.get("diff"), dict):
        errors.append("diff must be an object")
    if not isinstance(candidate.get("benchmark"), dict):
        errors.append("benchmark must be an object")
    if not isinstance(candidate.get("impact"), dict):
        errors.append("impact must be an object")
    return errors


def cmd_init(args) -> int:
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    path = candidate_path(args.candidate_id)
    if path.exists():
        raise SystemExit(f"candidate already exists: {path}")

    candidate = load(TEMPLATE)
    candidate.update(
        {
            "candidate_id": args.candidate_id,
            "title": args.title,
            "source_type": args.source_type,
            "source": args.source,
            "version_or_date": args.version,
            "license": args.license,
            "capability_ids": args.capability or [],
            "classification": args.classification,
            "evidence_level": args.evidence,
            "implementation": args.implementation or "",
            "status": "inbox",
        }
    )
    errors = validate(candidate)
    if errors:
        print(json.dumps({"status": "BLOCKED", "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "CREATED",
                "candidate_id": args.candidate_id,
                "path": str(path),
                "note": "CURRENT was not modified.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_validate(args) -> int:
    path = Path(args.file).resolve()
    candidate = load(path)
    errors = validate(candidate)
    print(
        json.dumps(
            {"status": "FAIL" if errors else "PASS", "candidate_id": candidate.get("candidate_id"), "errors": errors},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if errors else 0


def cmd_list(args) -> int:
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in sorted(CANDIDATES.glob("*.json")):
        candidate = load(path)
        rows.append(
            {
                "candidate_id": candidate.get("candidate_id"),
                "classification": candidate.get("classification"),
                "status": candidate.get("status"),
                "evidence_level": candidate.get("evidence_level"),
                "path": str(path),
            }
        )
    print(json.dumps({"count": len(rows), "candidates": rows}, ensure_ascii=False, indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Create and validate AI Film upgrade candidates without touching CURRENT")
    sub = p.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init")
    init.add_argument("candidate_id")
    init.add_argument("--title", required=True)
    init.add_argument("--source-type", required=True)
    init.add_argument("--source", required=True)
    init.add_argument("--version", required=True)
    init.add_argument("--license", required=True)
    init.add_argument("--classification", required=True, choices=sorted(CLASSIFICATIONS))
    init.add_argument("--evidence", default="E0", choices=sorted(EVIDENCE))
    init.add_argument("--capability", action="append", default=[])
    init.add_argument("--implementation")
    init.set_defaults(func=cmd_init)

    val = sub.add_parser("validate")
    val.add_argument("file")
    val.set_defaults(func=cmd_validate)

    listing = sub.add_parser("list")
    listing.set_defaults(func=cmd_list)
    return p


def main() -> int:
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
