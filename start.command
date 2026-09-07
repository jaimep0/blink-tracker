#!/bin/bash
cd "$(dirname "$0")"
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

PYTHON_BIN=""
if [ -x .venv/bin/python ]; then
  PYTHON_BIN=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  echo "python3 not found. Install Python 3, then run again."
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  "$PYTHON_BIN" -m venv .venv
  .venv/bin/pip install -U pip
  .venv/bin/pip install -r requirements.txt
fi

exec .venv/bin/python blink_tracker.py
