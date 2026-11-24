#!/usr/bin/env bash
set -euo pipefail
git config user.name "github-actions[bot]"
git config user.email \
  "41898282+github-actions[bot]@users.noreply.github.com"
git add -A
title="board: #${ISSUE} $(head -n 1 "${RUNNER_TEMP}/brief.txt")"
git commit -m "${title}" || true
# git smart HTTP on github.com rejects "Authorization: bearer" for
# receive-pack (401, then git asks for a username and dies with
# "could not read Username"). Use the basic header actions/checkout
# itself writes: base64("x-access-token:<token>").
auth_header="AUTHORIZATION: basic $(printf 'x-access-token:%s' "${GH_TOKEN}" | base64 -w0)"
git_auth() {
  git -c "http.extraheader=${auth_header}" "$@"
}
git_auth fetch origin staging
ahead="$(git rev-list --count "origin/staging..HEAD")"
if [ "${ahead}" = "0" ]; then
  echo "No unique commits vs staging; skip draft PR (dry-run / no-op)"
  exit 0
fi
if [ -n "${PR_NUMBER:-}" ]; then
  git_auth push -u origin HEAD
  echo "Updated existing PR #${PR_NUMBER}"
  exit 0
fi
git_auth push -u origin "HEAD:board/${TASK_ID}" --force-with-lease
zone="$(python3 scripts/ci/board_policy.py --zone origin/staging \
  --kind "${BOARD_KIND}")"
body="$(
  BOARD_ZONE="${zone}" \
  BOARD_BRIEF_FILE="${RUNNER_TEMP}/brief.txt" \
  BOARD_EVIDENCE_FILE="${RUNNER_TEMP}/board-test.log" \
  BOARD_TASK_ID="${TASK_ID}" \
  python3 scripts/ci/board_pr_body.py
)"
existing="$(gh pr list --head "board/${TASK_ID}" --base staging \
  --json number --jq '.[0].number // empty')"
if [ -n "${existing}" ]; then
  gh pr edit "${existing}" --title "${title}" --body "${body}"
  echo "Updated existing PR #${existing}"
else
  gh pr create --draft --base staging \
    --title "${title}" \
    --body "${body}"
fi
