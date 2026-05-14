# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Build HTML documentation using Sphinx.

Usage:
    python build_docs.py [--strict] [--verbose]
"""

import argparse
import sys
from pathlib import Path

DOCS_SOURCE = Path(__file__).resolve().parent / "docs"
DOCS_OUTPUT = DOCS_SOURCE / "_build" / "html"


def build_docs(strict: bool = False, verbose: bool = False) -> int:
    from sphinx.cmd.build import build_main

    args = [
        "-b", "html",
        "-j", "auto",
    ]

    if strict:
        args.append("-W")

    if verbose:
        args.append("-v")

    args += [str(DOCS_SOURCE), str(DOCS_OUTPUT)]

    return build_main(args)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Sphinx documentation")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors (-W)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    ret = build_docs(strict=args.strict, verbose=args.verbose)
    sys.exit(ret)


if __name__ == "__main__":
    main()
