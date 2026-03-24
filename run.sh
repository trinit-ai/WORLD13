#!/bin/bash
# 13TMOS CLI Runner
# Usage: ./run.sh [--pack pack_id] [--resume session_id] [--list]

cd "$(dirname "$0")"
python3 engine/console.py "$@"
