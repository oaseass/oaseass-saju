#!/usr/bin/env bash
set -e
pip install --no-cache-dir -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
