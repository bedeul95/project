#!/bin/bash
set -eu
atlas_root="$(cd -- "$(dirname -- "$0")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
 echo 'Python 3.9+를 먼저 설치하세요. README.md를 확인하세요.'
 exit 1
fi
python3 "$atlas_root/install_mcp.py"
