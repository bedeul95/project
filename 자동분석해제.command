#!/bin/bash
set -eu
atlas_root="$(cd -- "$(dirname -- "$0")" && pwd)"
python3 "$atlas_root/install_scheduler.py" --remove
