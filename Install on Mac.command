#!/bin/bash
# Double-click this file to install Nudge on your Mac.
cd "$(dirname "$0")" || exit 1

check='import sys, tkinter; sys.exit(0 if tkinter.TkVersion >= 8.6 else 1)'
chosen=""
for candidate in \
  /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
  /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "$check" >/dev/null 2>&1; then
    chosen="$candidate"
    break
  fi
done

if [ -z "$chosen" ]; then
  echo
  echo "Nudge needs the free Python from python.org (it has everything included)."
  echo "Opening the download page. Install it, then double-click this file again."
  open "https://www.python.org/downloads/" >/dev/null 2>&1
  status=1
else
  "$chosen" install.py "$@"
  status=$?
fi

echo
read -n 1 -s -r -p "Press any key to close this window."
echo
exit $status
