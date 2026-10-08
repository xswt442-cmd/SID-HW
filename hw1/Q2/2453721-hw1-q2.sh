#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SID="${SID:-2453721}"
K="${K:-2}"
: "${WORKERS:?Set WORKERS to K comma-separated SSH targets; Docker workers use user@host::container}"
python3 "$ROOT/2453721-hw1-q2-distributed.py" --sid "$SID" --k "$K" --workers "$WORKERS" "$@"
