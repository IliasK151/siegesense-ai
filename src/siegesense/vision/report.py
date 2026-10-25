"""Command-line entry point for local annotation evaluation reports.

Example:
  python -m siegesense.vision.report --dataset heldout=heldout.json --output report.json
  python -m siegesense.vision.report --dataset heldout=heldout.json \
      --agreement double_review=reviewer_a.json,reviewer_b.json --output report.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from siegesense.vision.evaluation import write_evaluation_report


def _named_path(value: str) -> tuple[str, Path]:
    name, separator, raw_path = value.partition("=")
    if not separator or not name.strip() or not raw_path.strip():
        raise argparse.ArgumentTypeError("Expected NAME=PATH")
    return name.strip(), Path(raw_path.strip()).expanduser()


def _named_pair(value: str) -> tuple[str, Path, Path]:
    name, separator, raw_paths = value.partition("=")
    paths = raw_paths.split(",")
    if (
        not separator
        or not name.strip()
        or len(paths) != 2
        or not all(path.strip() for path in paths)
    ):
        raise argparse.ArgumentTypeError("Expected NAME=FIRST_DATASET,SECOND_DATASET")
    return name.strip(), Path(paths[0].strip()).expanduser(), Path(paths[1].strip()).expanduser()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create a local JSON report of human annotation coverage and optional "
            "inter-annotator agreement. This does not evaluate a vision model."
        )
    )
    parser.add_argument(
        "--dataset",
        action="append",
        type=_named_path,
        default=[],
        metavar="NAME=PATH",
        help="Annotation dataset to include; repeat for distinct recording splits.",
    )
    parser.add_argument(
        "--agreement",
        action="append",
        type=_named_pair,
        default=[],
        metavar="NAME=FIRST,SECOND",
        help="Two independently labelled datasets for the same source recording.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output JSON report path (must not overwrite an input dataset).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.dataset:
        parser.error("provide at least one --dataset NAME=PATH")
    try:
        output = write_evaluation_report(
            args.output,
            args.dataset,
            annotator_pairs=args.agreement,
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Evaluation report failed: {error}", file=sys.stderr)
        return 2
    print(f"Evaluation report written: {output}")
    print("Note: this report does not measure model performance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
