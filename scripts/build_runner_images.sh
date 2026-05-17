#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

docker build \
  -f "$ROOT_DIR/docker/codebug-runner-cpp.Dockerfile" \
  -t codebug-runner-cpp \
  "$ROOT_DIR"

docker build \
  -f "$ROOT_DIR/docker/codebug-runner-python.Dockerfile" \
  -t codebug-runner-python \
  "$ROOT_DIR"
