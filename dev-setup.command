#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

set +e
/usr/bin/env bash "$ROOT/dev-setup.sh"
status=$?

echo
echo "Press any key to close..."
read -n 1 -s -r
exit "$status"
