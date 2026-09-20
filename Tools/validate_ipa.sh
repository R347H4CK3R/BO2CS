#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 Tools/validate_ipa.py "${1:-Build/GameName-unsigned.ipa}"
