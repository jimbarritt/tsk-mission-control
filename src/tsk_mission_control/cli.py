import argparse
import sys

from . import __version__
from . import layout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tsk-mission-control")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "name",
        nargs="?",
        help="name for the first Claude session (default: the current git repo name)",
    )
    args = parser.parse_args(argv)

    return layout.run(args.name)


if __name__ == "__main__":
    sys.exit(main())
