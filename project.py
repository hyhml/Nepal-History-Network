#!/usr/bin/env python3
"""File-based request and material catalog for this repository."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil


ROOT = Path(__file__).resolve().parent
REQUESTS = ROOT / "docs/requests.jsonl"
CATALOG = ROOT / "materials/catalog.json"
LOCAL = ROOT / "materials/local"
KINDS = ("books", "datasets", "notes", "other")


def within_project(path: Path) -> Path:
    resolved = (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    if not resolved.is_relative_to(ROOT):
        raise ValueError(f"路径超出项目边界：{resolved}")
    return resolved


def read_requests() -> list[dict]:
    if not REQUESTS.exists():
        return []
    return [json.loads(line) for line in REQUESTS.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_catalog() -> list[dict]:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def save_catalog(entries: list[dict]) -> None:
    CATALOG.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def request_add(args: argparse.Namespace) -> None:
    wording = args.text.strip()
    if not wording:
        raise ValueError("要求不能为空")
    existing = read_requests()
    numbers = [int(item["id"].split("-")[-1]) for item in existing]
    entry = {
        "id": f"REQ-{max(numbers, default=0) + 1:04d}",
        "date": datetime.now(timezone.utc).date().isoformat(),
        "source": "cli",
        "text": wording,
    }
    with REQUESTS.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"已记录 {entry['id']}；请同步更新 docs/design-spec.md")


def request_list(_args: argparse.Namespace) -> None:
    for item in read_requests():
        print(f"{item['id']}  {item['date']}  {item['text']}")


def material_path(entry: dict) -> Path:
    return within_project(Path(entry["path"]))


def material_list(args: argparse.Namespace) -> None:
    directory = within_project(Path(args.directory)) if args.directory else None
    for entry in read_catalog():
        path = material_path(entry)
        if directory and not path.is_relative_to(directory):
            continue
        state = "可用" if path.exists() else "缺失"
        print(f"{entry['id']}  [{state}]  {entry['path']}  {entry['title']}")


def material_show(args: argparse.Namespace) -> None:
    entry = next((entry for entry in read_catalog() if entry["id"] == args.id), None)
    if entry is None:
        raise ValueError(f"未知资料 ID：{args.id}")
    path = material_path(entry)
    print(json.dumps({**entry, "absolute_path": str(path), "exists": path.exists()}, ensure_ascii=False, indent=2))


def material_add(args: argparse.Namespace) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", args.id):
        raise ValueError("ID 只能包含小写字母、数字、连字符和下划线")
    entries = read_catalog()
    if any(entry["id"] == args.id for entry in entries):
        raise ValueError(f"资料 ID 已存在：{args.id}")
    source = Path(args.source).expanduser().resolve(strict=True)
    if not source.is_file() and not source.is_dir():
        raise ValueError("只接受普通文件或目录")
    target = within_project(LOCAL / args.kind / source.name)
    if target.exists():
        raise FileExistsError(f"目标已存在：{target}")
    if source.is_dir() and target.is_relative_to(source):
        raise ValueError("不能把目录复制到它自身内部")
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target)
    else:
        shutil.copy2(source, target)
    entry = {
        "id": args.id,
        "title": args.title,
        "kind": args.kind,
        "scope": "local",
        "path": target.relative_to(ROOT).as_posix(),
        "note": args.note or "",
    }
    if target.is_file():
        entry["sha256"] = file_sha256(target)
    entries.append(entry)
    save_catalog(entries)
    print(f"已保存：{entry['path']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    groups = parser.add_subparsers(dest="group", required=True)

    request = groups.add_parser("request", help="记录与查看用户要求")
    request_actions = request.add_subparsers(dest="action", required=True)
    add_request = request_actions.add_parser("add")
    add_request.add_argument("text")
    add_request.set_defaults(handler=request_add)
    list_requests = request_actions.add_parser("list")
    list_requests.set_defaults(handler=request_list)

    material = groups.add_parser("material", help="登记与查找项目资料")
    material_actions = material.add_subparsers(dest="action", required=True)
    list_materials = material_actions.add_parser("list")
    list_materials.add_argument("--directory", help="以项目根目录为起点的目录路径")
    list_materials.set_defaults(handler=material_list)
    show_material = material_actions.add_parser("show")
    show_material.add_argument("id")
    show_material.set_defaults(handler=material_show)
    add_material = material_actions.add_parser("add")
    add_material.add_argument("source", help="要复制到项目本地目录的文件或目录")
    add_material.add_argument("--id", required=True)
    add_material.add_argument("--title", required=True)
    add_material.add_argument("--kind", choices=KINDS, default="other")
    add_material.add_argument("--note")
    add_material.set_defaults(handler=material_add)

    args = parser.parse_args()
    try:
        args.handler(args)
    except (ValueError, FileExistsError, FileNotFoundError) as error:
        parser.exit(2, f"错误：{error}\n")


if __name__ == "__main__":
    main()
