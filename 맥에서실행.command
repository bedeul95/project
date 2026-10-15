#!/bin/bash
# Open the standalone application. No installation or network request.
set -eu
atlas_root="$(cd -- "$(dirname -- "$0")" && pwd)"
if [ "$(uname -s)" != "Darwin" ]; then
  echo "맥에서는 시작.html을 더블클릭하거나 이 파일을 bash로 실행하세요."
  exit 0
fi
/usr/bin/open "$atlas_root/시작.html"
