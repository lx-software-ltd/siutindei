#!/usr/bin/env bash
set -euo pipefail
if [ -z "${CURSOR_API_KEY:-}" ]; then
  echo "CURSOR_API_KEY is not set" >&2
  exit 1
fi
{
  echo "Follow AGENTS.md. Treat the brief as acceptance criteria."
  echo "Do not modify red-zone paths listed in docs/architecture/zones.md."
  echo "Content-kind briefs may only change content/**."
  echo "Do not commit, push, or open pull requests. Only edit files."
  echo "Kind: ${BOARD_KIND}"
  echo
  cat "${RUNNER_TEMP}/brief.txt"
} > "${RUNNER_TEMP}/prompt.txt"
cursor-agent -p "$(cat "${RUNNER_TEMP}/prompt.txt")" \
  --model composer-2.5 --yolo --output-format stream-json \
  | tee "${RUNNER_TEMP}/agent-transcript.jsonl"
