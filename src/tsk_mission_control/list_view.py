"""The Mission Control list view. Placeholder until T-04.

Keeps its pane alive rather than exiting, so the three-pane layout T-03
builds does not collapse before T-04 fills this in.
"""

import sys
import time


def main() -> int:
    print("tsk-mission-control: list view not built yet (see T-04)", file=sys.stderr)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
