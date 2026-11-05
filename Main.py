"""RefactorCompare: check whether a function behaves the same in two commits.

Usage:
    python Main.py REPO COMMIT1 COMMIT2 FILE FUNCTION [--arg NAME=TYPE ...]

Example (this repo's own history, where add() has no type hints):
    python Main.py . a992c23 8afd8d5 Math.py add --arg num1=int --arg num2=int

Any argument left out is asked for interactively, and so is the type of any
parameter that has no type hint.

Exit code: 0 = same behaviour, 1 = difference found, 2 = error.
"""

import argparse
import sys

import Testing
from checkout import GitError, checkout_versions
from loader import LoadError, load_function


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Compare a function's behaviour between two git commits using Hypothesis."
    )
    parser.add_argument("repo", nargs="?", help="repository URL or local path")
    parser.add_argument("commit1", nargs="?", help="original commit / branch / tag")
    parser.add_argument("commit2", nargs="?", help="refactored commit / branch / tag")
    parser.add_argument("file", nargs="?", help="path to the .py file inside the repo")
    parser.add_argument("function", nargs="?", help="function name (Class.method also works)")
    parser.add_argument(
        "--arg", action="append", default=[], metavar="NAME=TYPE",
        help="type for a parameter, e.g. --arg x=int --arg items='list[str]'",
    )
    parser.add_argument("--examples", type=int, default=500, help="inputs to try (default 500)")
    parser.add_argument("--keep", action="store_true", help="keep the checked-out versions")
    args = parser.parse_args(argv)

    prompts = {
        "repo": "Repo link or path: ",
        "commit1": "First (original) commit: ",
        "commit2": "Second (refactored) commit: ",
        "file": "Path to the file, relative to the repo root (e.g. src/Math.py): ",
        "function": "Function name: ",
    }
    for field, prompt in prompts.items():
        if not getattr(args, field):
            setattr(args, field, input(prompt).strip())
    args.file = args.file.replace("\\", "/")

    arg_types = {}
    for item in args.arg:
        name, sep, type_text = item.partition("=")
        if not sep:
            parser.error(f"--arg must look like NAME=TYPE, got {item!r}")
        arg_types[name.strip()] = Testing.parse_type(type_text.strip())
    args.arg_types = arg_types
    return args


def ask_type(param_name):
    while True:
        text = input(f"Type of parameter '{param_name}' (e.g. int, str, list[int]): ").strip()
        try:
            return Testing.parse_type(text)
        except Testing.StrategyError as exc:
            print(exc)


def compare_commits(args):
    with checkout_versions(args.repo, args.commit1, args.commit2, keep=args.keep) as (v1, v2):
        func1 = load_function(v1, args.file, args.function, "Version1")
        func2 = load_function(v2, args.file, args.function, "Version2")

        ask = ask_type if sys.stdin.isatty() else None
        print(f"\nComparing {args.file}:{args.function}")
        same, message = Testing.compare(
            func1, func2, args.arg_types, ask=ask, max_examples=args.examples
        )

    print("\n===========================")
    if same:
        print(f"PASS: {message}.\nThe refactor looks functionally the same.")
        return 0
    print(f"FAIL: the versions behave differently.\n{message}")
    return 1


def main(argv=None):
    try:
        args = parse_args(argv)
        return compare_commits(args)
    except (GitError, LoadError, Testing.StrategyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
