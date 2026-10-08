"""Command-line interface: ``cdisc-safety generate | run | demo``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from cdisc_safety import __version__
from cdisc_safety.pipeline import run_from_dir
from cdisc_safety.synthetic import generate, write_raw


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cdisc-safety", description="Raw clinical trial data to SDTM, ADaM and safety tables.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="write a synthetic raw dataset")
    gen.add_argument("--out", type=Path, default=Path("data/raw"))
    gen.add_argument("--subjects", type=int, default=300)
    gen.add_argument("--seed", type=int, default=42)
    gen.add_argument("--inject-errors", action="store_true", help="add realistic data-entry faults")

    run = sub.add_parser("run", help="run the pipeline on a directory of raw files")
    run.add_argument("--raw", type=Path, default=Path("data/raw"))
    run.add_argument("--out", type=Path, default=Path("outputs"))
    run.add_argument("--strict", action="store_true", help="exit with code 2 if any ERROR finding is raised")

    demo = sub.add_parser("demo", help="generate synthetic data and run the pipeline")
    demo.add_argument("--out", type=Path, default=Path("outputs"))
    demo.add_argument("--subjects", type=int, default=300)
    demo.add_argument("--seed", type=int, default=42)
    return parser


def _report(result) -> int:
    print(f"Run {result.run_id}: {result.status}")
    if result.message:
        print(result.message)
    if not result.ok:
        return 1
    m = result.manifest
    print("Records:", ", ".join(f"{k}={v}" for k, v in m["records"].items()))
    print("Findings:", ", ".join(f"{k}={v}" for k, v in m["findings"].items()))
    if m["quarantined"]:
        print("Quarantined:", ", ".join(f"{k}={v}" for k, v in m["quarantined"].items()))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point; returns a process exit code."""
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    try:
        if args.command == "generate":
            paths = write_raw(generate(args.subjects, args.seed, args.inject_errors), args.out)
            for name, path in paths.items():
                print(f"wrote {name}: {path}")
            return 0
        if args.command == "demo":
            raw_dir = args.out / "raw"
            write_raw(generate(args.subjects, args.seed), raw_dir)
            return _report(run_from_dir(raw_dir, args.out))
        result = run_from_dir(args.raw, args.out)
        code = _report(result)
        if code == 0 and args.strict and result.manifest["findings"]["ERROR"]:
            return 2
        return code
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
