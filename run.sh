#!/bin/zsh
# Launch Nudge with a Python that has a modern Tk (8.6 or newer).
#
# The Tk 8.5 that ships with macOS draws empty windows on recent versions of
# macOS, so it is only used as a last resort.
#   brew install python-tk@3.13

set -uo pipefail
cd "$(dirname "$0")"

check='import sys, tkinter; sys.exit(0 if tkinter.TkVersion >= 8.6 else 1)'

for cmd in /Library/Frameworks/Python.framework/Versions/Current/bin/python3 /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
  if command -v "$cmd" >/dev/null 2>&1 && "$cmd" -c "$check" >/dev/null 2>&1; then
    exec "$cmd" main.py "$@"
  fi
done

echo "No Python with a modern Tk was found; the window may appear empty." >&2
echo "Fix: install Python from https://www.python.org/downloads/ (or: brew install python-tk@3.13)" >&2
exec /usr/bin/python3 main.py "$@"
