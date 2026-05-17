#!/usr/bin/env bash
set -euo pipefail

missing=0

if ! command -v pandoc >/dev/null 2>&1; then
  echo "missing: pandoc"
  missing=1
else
  echo "ok: pandoc $(pandoc --version | head -n 1)"
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "missing: docker"
  missing=1
else
  echo "ok: docker $(docker --version)"
  for image in codebug-runner-cpp codebug-runner-python; do
    if docker image inspect "$image" >/dev/null 2>&1; then
      echo "ok: image $image"
    else
      echo "missing: image $image"
      missing=1
    fi
  done
fi

exit "$missing"
