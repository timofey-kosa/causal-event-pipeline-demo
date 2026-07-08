from __future__ import annotations

import argparse
from pathlib import Path

from causal_pipeline.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the synthetic methodology case study.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Run the end-to-end demo.")
    run.add_argument("--config", type=Path, required=True, help="Path to a YAML config file.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        run_dir = run_pipeline(args.config, project_root=Path.cwd())
        print(f"Run complete: {run_dir}")
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
