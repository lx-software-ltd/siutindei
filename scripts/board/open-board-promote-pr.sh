#!/usr/bin/env bash
set -euo pipefail
repo="${GITHUB_REPOSITORY}"
compare="$(gh api "repos/${repo}/compare/main...staging")"
behind="$(printf '%s' "${compare}" | jq -r '.behind_by')"
ahead="$(printf '%s' "${compare}" | jq -r '.ahead_by')"
echo "staging vs main: behind=${behind} ahead=${ahead} kind=${KIND}"

if [ "${behind}" != "0" ]; then
  echo "staging is behind main; rebase first" >&2
  exit 1
fi

title="Promote staging $(date -u +%F)"
body="$(cat <<EOF
Promote \`staging\` to \`main\` (${KIND}).

The board never merges to \`main\`. An owner must merge this PR
in GitHub after reviewing the staging diff.

- Ahead of main: ${ahead} commit(s)
EOF
)"

if [ "${ahead}" = "0" ]; then
  echo "staging matches main; nothing to promote"
  exit 0
fi

existing="$(gh pr list --base main --head staging --state open \
  --json number --jq '.[0].number // empty')"
if [ -n "${existing}" ]; then
  gh pr edit "${existing}" --title "${title}" --body "${body}"
  echo "Updated existing promote PR #${existing}"
else
  gh pr create --base main --head staging \
    --title "${title}" \
    --body "${body}"
fi
