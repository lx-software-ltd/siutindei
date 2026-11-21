# GitHub Rulesets Configuration

This document describes the recommended GitHub rulesets for repository protection.

## Overview

GitHub rulesets protect critical branches and tags from accidental or malicious
changes. These rules enforce code review, CI checks, and prevent destructive
operations.

`.github/workflows/verify-rulesets.yml` runs `lx-software-ltd/actions/verify-rulesets`
weekly. A 403 from the classic branch-protection API is treated as
unreadable, and the ruleset API is still evaluated. The job fails while no
active ruleset targets `main`. Activating that ruleset is a repository
admin action.

---

## Branch Protection: `main`

The `main` branch requires protection as it triggers production deployments.

### Required Rules

| Rule | Setting | Purpose |
|------|---------|---------|
| Require pull request before merging | ✅ Enabled | Prevents direct pushes |
| Required approvals | 0 | Exactly 0 approving reviews |
| Dismiss stale reviews | ✅ Enabled | Re-review after changes |
| Require status checks to pass | ✅ Enabled | CI must pass |
| Require branches to be up to date | ✅ Enabled | Prevents stale merges |
| Block force pushes | ✅ Enabled | Protects history |
| Block deletions | ✅ Enabled | Prevents accidental deletion |

### Required Status Checks

GitHub matches required checks by job name. The weekly job calls
`lx-software-ltd/actions/verify-rulesets` and fails unless the
approving-review count is exactly 0 and the required checks are exactly
the job names `lint` and `test`. The weekly job fails if the count is
not 0 or the check list is not exactly those two names.

| Workflow | Job name |
|----------|----------|
| `.github/workflows/lint.yml` | `lint` |
| `.github/workflows/test.yml` | `test` |

---

## Branch Protection: `staging`

The `staging` branch is the source of truth for the public website staging
deploy (`.github/workflows/deploy-public-www.yml` triggers on
`push: staging`). Direct pushes and force-pushes are blocked; changes land
through pull requests.

### Required Rules

| Rule | Setting | Purpose |
|------|---------|---------|
| Require pull request before merging | ✅ Enabled | Prevents direct pushes |
| Block force pushes | ✅ Enabled | Protects history |
| Block deletions | ✅ Enabled | Prevents accidental deletion |
| Bypass actors | Repository admin (`lcacchiani`); GitHub Actions app (`github-actions`, id `15368`) | Owner emergencies; `board-merge-staging.yml` squash |

### Setup (GitHub Web UI)

1. Go to repository **Settings** → **Rules** → **Rulesets**
2. Click **New ruleset** → **New branch ruleset**
3. Configure:
   - **Ruleset name:** `staging-protection`
   - **Enforcement status:** Active
   - **Target branches:** Add target → Include by pattern → `staging`
4. Enable rules:
   - ✅ Restrict deletions
   - ✅ Block force pushes
   - ✅ Require a pull request before merging
5. **Bypass list:** add yourself (`lcacchiani`) and **GitHub Actions**
   (app `github-actions`, id `15368`) so `board-merge-staging.yml` can
   squash-merge `board/*` PRs.
6. Click **Create**

---

## Tag Protection: `v*`

Release tags should be protected from modification or deletion.

| Rule | Setting | Purpose |
|------|---------|---------|
| Protect tags matching `v*` | ✅ Enabled | Protects release versions |
| Restrict who can create | Maintainers only | Controlled releases |

---

## Setup Instructions

### Option 1: GitHub Web UI

#### Branch Protection

1. Go to repository **Settings** → **Rules** → **Rulesets**
2. Click **New ruleset** → **New branch ruleset**
3. Configure:
   - **Ruleset name:** `main-protection`
   - **Enforcement status:** Active
   - **Target branches:** Add target → Include by pattern → `main`
4. Enable rules:
   - ✅ Restrict deletions
   - ✅ Require a pull request before merging
     - Required approvals: `0`
     - ✅ Dismiss stale pull request approvals when new commits are pushed
   - ✅ Require status checks to pass
     - ✅ Require branches to be up to date before merging
     - Add checks: `lint`, `test`
   - ✅ Block force pushes
5. Click **Create**

#### Tag Protection

1. Go to repository **Settings** → **Rules** → **Rulesets**
2. Click **New ruleset** → **New tag ruleset**
3. Configure:
   - **Ruleset name:** `release-tags`
   - **Enforcement status:** Active
   - **Target tags:** Add target → Include by pattern → `v*`
4. Enable rules:
   - ✅ Restrict deletions
   - ✅ Restrict updates
   - ✅ Restrict creations (optional, maintainers only)
5. Click **Create**

### Option 2: GitHub CLI

```bash
# Branch protection for main
gh api repos/{owner}/{repo}/rulesets \
  --method POST \
  --field name='main-protection' \
  --field target='branch' \
  --field enforcement='active' \
  --field 'conditions[ref_name][include][]=refs/heads/main' \
  --field 'rules[][type]=deletion' \
  --field 'rules[][type]=non_fast_forward' \
  --field 'rules[][type]=pull_request' \
  --field 'rules[2][parameters][required_approving_review_count]=0' \
  --field 'rules[2][parameters][dismiss_stale_reviews_on_push]=true' \
  --field 'rules[][type]=required_status_checks' \
  --field 'rules[3][parameters][strict_required_status_checks_policy]=true' \
  --field 'rules[3][parameters][required_status_checks][][context]=lint' \
  --field 'rules[3][parameters][required_status_checks][][context]=test'

# Tag protection for releases (already exists here as `release-tags`)
gh api repos/{owner}/{repo}/rulesets \
  --method POST \
  --field name='release-tags' \
  --field target='tag' \
  --field enforcement='active' \
  --field 'conditions[ref_name][include][]=refs/tags/v*' \
  --field 'rules[][type]=deletion' \
  --field 'rules[][type]=update'
```

### Update the existing `main-protection` ruleset

The ruleset already exists, so update it instead of creating a second
one. `rules` replaces the whole list; conditions and bypass actors stay
as they are. An admin token is required.

```bash
gh api repos/lx-software-ltd/siutindei/rulesets/12176289 \
  --method PUT \
  --input - <<'JSON'
{
  "enforcement": "active",
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {"type": "pull_request", "parameters": {
      "required_approving_review_count": 0,
      "dismiss_stale_reviews_on_push": true,
      "require_code_owner_review": false,
      "require_last_push_approval": false,
      "required_review_thread_resolution": false
    }},
    {"type": "required_status_checks", "parameters": {
      "strict_required_status_checks_policy": true,
      "required_status_checks": [
        {"context": "lint"},
        {"context": "test"}
      ]
    }}
  ]
}
JSON
```

Then run **Verify GitHub Rulesets** (`verify-rulesets.yml`) by hand to confirm.

---

## Verification

A CI workflow (`.github/workflows/verify-rulesets.yml`) runs weekly and on
demand to verify that branch protection rules are correctly configured.

The verification checks:
- An **active** ruleset targets `main`. A ruleset whose enforcement is
  `disabled` or `evaluate` fails this check. Classic branch protection
  is not a substitute for that disabled ruleset.
- The approving-review count is exactly 0, and the required status
  checks are exactly `lint` and `test`. The weekly job fails if the
  count is not 0 or the check list is not exactly those two names.
- Force push protection is enabled
- Deletion protection is enabled

---

## Exceptions

### Dependabot

Dependabot PRs are automatically created and can be merged after CI passes.
No special exceptions needed as Dependabot respects branch protection.

### Emergency Fixes

In emergencies, repository admins can bypass branch protection. This should
be documented in the PR and followed by a post-mortem if used.

---

## Related Documentation

- [GitHub Rulesets Documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)
- [Branch Protection Rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
