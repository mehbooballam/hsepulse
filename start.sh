#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/streamlit ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
fi
exec .venv/bin/streamlit run app.py "$@"
