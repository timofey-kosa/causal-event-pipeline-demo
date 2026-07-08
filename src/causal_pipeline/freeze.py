from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_commit(cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return None


def collect_outputs(run_dir: Path, include_logs: bool = True) -> list[Path]:
    suffixes = {".parquet", ".csv", ".json", ".md", ".png", ".txt", ".yaml", ".log", ".jsonl"}
    outputs: list[Path] = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.parts[-2:-1] == ("frozen",) and path.name in {"manifest.json", "checksums.json"}:
            continue
        if not include_logs and "logs" in path.relative_to(run_dir).parts:
            continue
        if path.suffix.lower() in suffixes:
            outputs.append(path)
    return outputs


def collect_key_outputs(run_dir: Path) -> list[Path]:
    return collect_outputs(run_dir, include_logs=False)


def freeze_run(
    run_dir: Path,
    project_root: Path,
    run_id: str,
    config: dict[str, Any],
    stages: list[str],
    row_counts: dict[str, int],
    validations: list[dict[str, object]],
) -> dict[str, Any]:
    frozen_dir = run_dir / "frozen"
    frozen_dir.mkdir(parents=True, exist_ok=True)
    config_text = yaml.safe_dump(config, sort_keys=True)
    config_snapshot = frozen_dir / "config_snapshot.yaml"
    config_snapshot.write_text(config_text, encoding="utf-8")

    outputs = collect_key_outputs(run_dir)
    produced_outputs = collect_outputs(run_dir, include_logs=True)
    checksums = {path.relative_to(run_dir).as_posix(): sha256_file(path) for path in outputs}
    checksums_path = frozen_dir / "checksums.json"
    checksums_path.write_text(json.dumps(checksums, indent=2, sort_keys=True), encoding="utf-8")

    validation_status = "passed" if all(item.get("passed") for item in validations) else "failed"
    manifest = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(project_root),
        "python_version": sys.version,
        "platform": platform.platform(),
        "config_hash": hash_text(config_text),
        "random_seed": config["synthetic"]["random_seed"],
        "pipeline_stages": stages,
        "produced_artefacts": sorted(path.relative_to(run_dir).as_posix() for path in produced_outputs),
        "row_counts": row_counts,
        "validation_status": validation_status,
        "validations": validations,
        "checksums": checksums,
    }
    manifest_path = frozen_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return manifest


def verify_checksums(run_dir: Path, checksums_path: Path | None = None) -> bool:
    checksums_path = checksums_path or (run_dir / "frozen" / "checksums.json")
    checksums = json.loads(checksums_path.read_text(encoding="utf-8"))
    for relative, expected in checksums.items():
        path = run_dir / relative
        if not path.exists() or sha256_file(path) != expected:
            return False
    return True
