#!/usr/bin/env bash
# Write the public website promotion summary. Values come from the step env.
set -euo pipefail
if [ "${SKIPPED:-}" = "true" ]; then
  {
    echo '## Public Website refresh skipped'
    echo ''
    echo "- Promotion mode: \`${PROMOTION_MODE}\`"
    echo '- Reason: no production build recorded yet, or no activity changed since the live build'
  } >> "$GITHUB_STEP_SUMMARY"
elif [ "${PROMOTION_MODE:-}" = "maintenance_on" ]; then
  {
    echo '## Public Website maintenance mode enabled'
    echo ''
    echo '- Operation mode: `maintenance_on`'
    echo '- Target environment: `production`'
    echo '- Stack: `lxsoftware-siutindei-public-www`'
    echo "- Production URL: \`${PRODUCTION_SITE_ORIGIN}\`"
  } >> "$GITHUB_STEP_SUMMARY"
else
  {
    echo '## Public Website promotion'
    echo ''
    echo "- Promotion mode: \`${PROMOTION_MODE}\`"
    echo "- Release ID: \`${RELEASE_ID}\`"
    echo '- Source environment: `staging`'
    echo '- Target environment: `production`'
    echo '- Build: fresh static export with **production** GitHub Environment variables'
    echo '- Stack: `lxsoftware-siutindei-public-www`'
    echo "- Production URL: \`${PRODUCTION_SITE_ORIGIN}\`"
  } >> "$GITHUB_STEP_SUMMARY"
fi
