#!/usr/bin/env python3
"""Run every test and print a summary.

    python3 tests/run_all.py          # dots
    python3 tests/run_all.py -v       # one line per test

Equivalent to `python3 -m unittest discover -s tests`, but on macOS it also
starts Python without window restoration, so a crashed earlier run cannot
leave a hidden "reopen windows?" prompt that stalls the window tests.
"""

import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAC_FLAG = "-ApplePersistenceIgnoreState"


def main(argv):
    if sys.platform == "darwin" and MAC_FLAG not in argv:
        os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve())] + argv + [MAC_FLAG, "YES"])
    argv = [arg for arg in argv if arg not in (MAC_FLAG, "YES")]
    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(HERE.parent))
    verbosity = 2 if "-v" in argv else 1
    suite = unittest.defaultTestLoader.discover(str(HERE), top_level_dir=str(HERE))
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
