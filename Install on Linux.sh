#!/bin/sh
# Install Nudge on Linux. Double-click it (choose "Run") or run:  sh "Install on Linux.sh"
cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
  echo
  echo "Python 3 is needed. Install it with your package manager, for example:"
  echo "    sudo apt install python3 python3-tk"
  status=1
else
  python3 install.py "$@"
  status=$?
fi

echo
printf "Press Enter to close this window."
read -r _
exit $status
