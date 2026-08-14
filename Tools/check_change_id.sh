#!/usr/bin/env bash
#
# check_change_id.sh - Fail if any commit message contains a Gerrit "Change-Id:"
# trailer.
#
# The repo ships a Gerrit-style commit-msg hook (repo/hooks/commit-msg) that
# auto-inserts Change-Id lines. Those are meaningful only when pushing to the
# internal Gerrit; on the public GitHub mirror they are noise. This guard
# catches such lines before they land on a protected branch.
#
# Usage:
#   Tools/check_change_id.sh [<range>]
#
#   <range>  Git revision range to inspect (e.g. origin/main..HEAD).
#            If omitted, the range is derived from environment variables set by
#            CI (GitHub Actions), falling back to just the tip commit (HEAD).
#
# Exit codes:
#   0  no Change-Id found
#   1  one or more commits contain a Change-Id trailer

set -euo pipefail

PATTERN='^Change-Id:'

resolve_range() {
    # 1) explicit arg wins
    if [ "$#" -ge 1 ] && [ -n "${1:-}" ]; then
        echo "$1"
        return
    fi

    # 2) GitHub Actions pull_request: compare base..head
    if [ -n "${GITHUB_BASE_REF:-}" ]; then
        # base ref is the target branch of the PR
        if git rev-parse --verify --quiet "origin/${GITHUB_BASE_REF}" >/dev/null; then
            echo "origin/${GITHUB_BASE_REF}..HEAD"
            return
        fi
    fi

    # 3) GitHub Actions push: event range before..after
    if [ -n "${GITHUB_EVENT_BEFORE:-}" ] \
        && [ "${GITHUB_EVENT_BEFORE}" != "0000000000000000000000000000000000000000" ] \
        && git rev-parse --verify --quiet "${GITHUB_EVENT_BEFORE}" >/dev/null; then
        echo "${GITHUB_EVENT_BEFORE}..HEAD"
        return
    fi

    # 4) fallback: inspect only the tip commit
    echo "HEAD~1..HEAD"
}

RANGE="$(resolve_range "$@")"

# Guard: if the range endpoints are missing (shallow clone), degrade to HEAD.
if ! git rev-list "$RANGE" >/dev/null 2>&1; then
    echo "⚠️  Range '$RANGE' not resolvable (shallow clone?); checking HEAD only."
    RANGE="HEAD~1..HEAD"
    if ! git rev-list "$RANGE" >/dev/null 2>&1; then
        RANGE="HEAD"
    fi
fi

echo "🔍 Checking commit messages for Change-Id in range: $RANGE"

offenders=""
for sha in $(git rev-list "$RANGE"); do
    if git log -1 --format='%B' "$sha" | grep -Eq "$PATTERN"; then
        offenders="$offenders $sha"
    fi
done

if [ -n "$offenders" ]; then
    echo "❌ Found Gerrit Change-Id trailer in the following commit(s):"
    for sha in $offenders; do
        subject=$(git log -1 --format='%h %s' "$sha")
        echo "   - $subject"
    done
    echo ""
    echo "These Change-Id lines come from the Gerrit commit-msg hook and must"
    echo "not be pushed to this branch. Remove them, e.g.:"
    echo ""
    echo "   git rebase -i <base> --exec \\"
    echo "     'git commit --amend -m \"\$(git log -1 --format=%B | sed \"/^Change-Id: /d\")\"'"
    echo ""
    echo "or for the tip commit only:"
    echo ""
    echo "   git commit --amend -m \"\$(git log -1 --format=%B | sed '/^Change-Id: /d')\""
    exit 1
fi

echo "✅ No Change-Id trailers found."
