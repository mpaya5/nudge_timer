#!/usr/bin/env python3
"""Install Nudge on this computer (macOS, Windows or Linux).

    python3 install.py                 install, or update, for the current user
    python3 install.py --uninstall     remove it (your reminders are kept)

Most people should double-click "Install on Mac.command", "Install on Windows.bat"
or "Install on Linux.sh" instead.
"""

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from nudge import installer  # noqa: E402


def main(argv):
    parser = argparse.ArgumentParser(description="Install Nudge for the current user.")
    parser.add_argument("--uninstall", action="store_true", help="remove Nudge (reminders are kept)")
    parser.add_argument("--remove-data", action="store_true", help="with --uninstall: also delete the reminders")
    parser.add_argument("--no-launch", action="store_true", help="do not open Nudge when finished")
    args = parser.parse_args(argv)

    if args.uninstall:
        installer.uninstall(remove_data=args.remove_data)
        print("\nNudge was removed.")
        return 0

    problem = installer.python_problem()
    if problem:
        print("\n" + problem, file=sys.stderr)
        return 1
    try:
        plan = installer.install(HERE)
    except installer.InstallError as error:
        print("\n" + str(error), file=sys.stderr)
        return 1
    print("\nNudge is installed. " + installer.where_to_find_it(plan))
    if not args.no_launch:
        installer.open_installed(plan)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
