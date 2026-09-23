#!/usr/bin/env bash
# ==============================================================================
# Script: asset-generator.sh
# Description: Shell wrapper for asset_generator.py
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
PYTHON_EXEC="python3"

if [[ -x "${HOME}/.local/share/frame-and-fable/venvs/asset-generator/bin/python" ]]; then
    PYTHON_EXEC="${HOME}/.local/share/frame-and-fable/venvs/asset-generator/bin/python"
elif [[ -x "${SCRIPT_DIR}/.venv/bin/python" ]]; then
    PYTHON_EXEC="${SCRIPT_DIR}/.venv/bin/python"
elif [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
    PYTHON_EXEC="${VIRTUAL_ENV}/bin/python"
fi

exec "${PYTHON_EXEC}" "${SCRIPT_DIR}/asset_generator.py" "$@"
