#!/usr/bin/env python3
"""Start Nudge."""

import os
import shutil
import subprocess
import sys

os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

MODERN_TK = 8.6
CANDIDATES = (
    "/Library/Frameworks/Python.framework/Versions/Current/bin/python3",  # python.org installer
    "/opt/homebrew/bin/python3.13",
    "/opt/homebrew/bin/python3",
    "/usr/local/bin/python3",
)

# macOS asks "reopen windows?" after a program crashes, and Tk waits for an
# answer nobody sees. Nudge has no windows worth restoring, so skip that.
MAC_FLAG = "-ApplePersistenceIgnoreState"
MAC_FLAGS = [MAC_FLAG, "YES"]


def extra_flags():
    return list(MAC_FLAGS) if sys.platform == "darwin" else []


def tk_version(python):
    """Tk version of another interpreter, or 0.0 when it has none."""
    try:
        result = subprocess.run(
            [python, "-c", "import tkinter; print(tkinter.TkVersion)"] + extra_flags(),
            capture_output=True,
            text=True,
            timeout=15,
        )
        return float(result.stdout.strip()) if result.returncode == 0 else 0.0
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def restart(python, argv):
    """Replace this process with `python main.py ...`, once."""
    os.environ["NUDGE_NO_REEXEC"] = "1"
    args = [python, os.path.abspath(__file__)] + list(argv)
    if MAC_FLAG not in argv:
        args += extra_flags()
    os.execv(python, args)


def switch_to_modern_tk(argv):
    """The Tk 8.5 bundled with macOS draws empty windows. Use a newer one."""
    if os.environ.get("NUDGE_NO_REEXEC"):
        return
    for name in CANDIDATES:
        python = name if os.path.isabs(name) else shutil.which(name)
        if not python or not os.path.exists(python):
            continue
        if os.path.realpath(python) == os.path.realpath(sys.executable):
            continue
        if tk_version(python) >= MODERN_TK:
            restart(python, argv)


def ensure_quiet_start(argv):
    """On macOS, make sure this process was started with the flag above."""
    if sys.platform == "darwin" and MAC_FLAG not in sys.argv:
        restart(sys.executable, argv)


def main(argv):
    if "--help" in argv or "-h" in argv:
        print("Usage: python3 main.py [--demo] [--preview]")
        print("  --demo      Try it out: alarms fire after 8, 28, 48 and 68 seconds.")
        print("              Uses throwaway settings, so your real reminders are untouched.")
        print("  --preview   Play the first reminder's animation right away.")
        return 0
    try:
        import tkinter
    except ImportError:
        tkinter = None
    if tkinter is None or tkinter.TkVersion < MODERN_TK:
        switch_to_modern_tk(argv)
    if tkinter is None:
        sys.stderr.write(
            "Nudge needs Tkinter, which is not installed on this Python.\n"
            "Fix: install Python from https://www.python.org/downloads/ (Linux: sudo apt install python3-tk)\n"
            "or, with Homebrew: brew install python-tk@3.13\n"
        )
        return 1
    ensure_quiet_start(argv)
    if tkinter.TkVersion < MODERN_TK:
        sys.stderr.write(
            "Warning: this Python has Tk %s, which may show an empty window.\n"
            "Fix: install Python from https://www.python.org/downloads/\n"
            "or, with Homebrew: brew install python-tk@3.13\n" % tkinter.TkVersion
        )
    from nudge.app import run

    run(preview_on_start="--preview" in argv, demo="--demo" in argv)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
