#!/usr/bin/env bash
# Usage: recruit.sh <name> <role> <tier> <floor> <brief-file> [--note "<Floor> Handoffs"] [--dry-run]
exec python3 "$(dirname "$0")/recruit.py" "$@"
