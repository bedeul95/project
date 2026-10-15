#!/bin/bash
# Optional: Python 3 must already be installed. The HTML file needs no Python.
set -eu
atlas_root="$(cd -- "$(dirname -- "$0")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  echo "조회·자동분석에는 Python 3와 Node.js 18+가 필요합니다. 시작.html은 오프라인 분석만 제공합니다."
  if [ "$(uname -s)" = "Darwin" ]; then /usr/bin/open "$atlas_root/시작.html"; fi
  exit 0
fi
exec python3 "$atlas_root/server.py"
