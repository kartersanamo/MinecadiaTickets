#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then
  PY=.venv/bin/python
elif [ -x venv/bin/python ]; then
  PY=venv/bin/python
else
  PY=python3
fi
while true; do
  "$PY" main.py
  sleep 5
done
