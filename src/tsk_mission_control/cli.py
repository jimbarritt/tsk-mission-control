import argparse
import sys

from . import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tsk-mission-control")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "name",
        nargs="?",
        help="name for the first Claude session (default: the current git repo name)",
    )
    parser.parse_args(argv)

    print("tsk-mission-control: layout command not built yet (see T-03)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
