"""Command line entrypoint for GovMesh benchmarks."""

from __future__ import annotations

import argparse
from pathlib import Path

from packages.govmesh_benchmark.runner import run_benchmark


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m packages.govmesh_benchmark")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run local-only sample benchmarks")
    run.add_argument("--sample", required=True, help="Sample document directory")
    run.add_argument(
        "--out",
        default="reports/benchmarks",
        help="Output directory for JSON and Markdown reports",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "run":
        report = run_benchmark(Path(args.sample), Path(args.out))
        print(f"JSON report: {report.json_report_path}")
        print(f"Markdown report: {report.markdown_report_path}")
        return 0

    return 1
