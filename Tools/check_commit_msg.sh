#!/usr/bin/env bash
#
# check_commit_msg.sh - Validate a commit message against the project's
# Conventional Commits convention.
#
# Convention (see .github/copilot-instructions.md, README):
#
#   type(scope): summary
#   type: summary            # scope is optional
#
#   - type  : feat|fix|test|refactor|chore|docs|style|perf|build|ci|revert
#   - scope : optional, lowercase/dashes/dots/digits, in parentheses
#   - summary: non-empty, should not end with a period
#   - subject line length <= 100 chars
#
# Merge/revert/fixup/squash auto-messages are exempt.
#
# Usage:
#   Tools/check_commit_msg.sh <file>     # validate a message file (hook mode)
#   Tools/check_commit_msg.sh --range <gitrange>   # validate a commit range (CI)
#   Tools/check_commit_msg.sh --text "feat(cli): x" # validate a literal string
#
# Exit codes: 0 = all valid, 1 = one or more invalid.

set -euo pipefail

# type(scope): summary  — scope optional, summary non-empty.
SUBJECT_RE='^(feat|fix|test|refactor|chore|docs|style|perf|build|ci|revert)(\([a-z0-9._-]+\))?!?: .+'
MAX_LEN=100

_is_exempt() {
    # Skip auto-generated messages that don't follow the convention.
    case "$1" in
        "Merge "* | "Revert "* | "fixup! "* | "squash! "* | "Reapply "*)
            return 0
            ;;
    esac
    return 1
}

# Validate a single subject line. Prints a reason on failure.
_validate_subject() {
    local subject="$1"

    if [ -z "$subject" ]; then
        echo "empty subject line"
        return 1
    fi

    if _is_exempt "$subject"; then
        return 0
    fi

    if ! printf '%s' "$subject" | grep -Eq "$SUBJECT_RE"; then
        echo "does not match 'type(scope): summary'"
        return 1
    fi

    if [ "${#subject}" -gt "$MAX_LEN" ]; then
        echo "subject exceeds ${MAX_LEN} chars (${#subject})"
        return 1
    fi

    # Discourage a trailing period on the subject.
    case "$subject" in
        *.)
            echo "subject should not end with a period"
            return 1
            ;;
    esac

    return 0
}

_print_help() {
    cat <<'USAGE'
Valid commit subject format:

    type(scope): summary        (scope optional)

  type   : feat | fix | test | refactor | chore | docs | style | perf | build | ci | revert
  scope  : optional, e.g. (transfer), (cli), (WebServer), (serial)
  summary: short, imperative, no trailing period, <= 100 chars

Examples:
    feat(transfer): add file transaction guard
    fix(serial): reject corrupted fcrc offset echo
    docs: document git hooks in README
USAGE
}

# ---- mode: literal text ----------------------------------------------------
if [ "${1:-}" = "--text" ]; then
    subject="$(printf '%s' "${2:-}" | head -n1)"
    if reason="$(_validate_subject "$subject")"; then
        echo "✅ commit subject OK"
        exit 0
    fi
    echo "❌ invalid commit subject: $reason"
    echo "   > $subject"
    echo ""
    _print_help
    exit 1
fi

# ---- mode: git range (CI) --------------------------------------------------
if [ "${1:-}" = "--range" ]; then
    range="${2:?--range requires a git revision range}"
    bad=0
    while IFS= read -r sha; do
        [ -z "$sha" ] && continue
        subject="$(git log -1 --format='%s' "$sha")"
        if ! reason="$(_validate_subject "$subject")"; then
            bad=1
            echo "❌ $(git log -1 --format='%h' "$sha"): $reason"
            echo "   > $subject"
        fi
    done < <(git rev-list "$range")

    if [ "$bad" -ne 0 ]; then
        echo ""
        _print_help
        exit 1
    fi
    echo "✅ all commit subjects in range '$range' OK"
    exit 0
fi

# ---- mode: message file (commit-msg hook) ----------------------------------
MSG_FILE="${1:-}"
if [ -z "$MSG_FILE" ] || [ ! -f "$MSG_FILE" ]; then
    echo "usage: $0 <commit-msg-file> | --range <range> | --text <subject>" >&2
    exit 2
fi

# First non-comment, non-empty line is the subject.
subject="$(grep -vE '^\s*#' "$MSG_FILE" | grep -vE '^\s*$' | head -n1 || true)"

if reason="$(_validate_subject "$subject")"; then
    exit 0
fi

echo "❌ commit message rejected: $reason"
echo "   > ${subject:-<empty>}"
echo ""
_print_help
exit 1
