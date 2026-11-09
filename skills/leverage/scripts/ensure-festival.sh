#!/usr/bin/env bash
# Self-contained entry point; Python is also the report renderer's runtime.
set -euo pipefail
exec python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/bootstrap.py" "$@"
