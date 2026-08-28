#!/usr/bin/env bash
#
# install.sh - one-shot installer for FPBInject local git hooks.
#
# Points this repo's git at the tracked hooks in Tools/hooks via
# core.hooksPath. This does two things:
#   1. Disables the inherited Gerrit commit-msg hook (which injects
#      "Change-Id:" trailers that this project's CI rejects). core.hooksPath
#      fully overrides .git/hooks, so the Gerrit symlink stops firing.
#   2. Enables our fast pre-commit checks (format/lint on staged files) and a
#      defensive commit-msg hook that strips any stray Change-Id trailer.
#
# Usage:
#   Tools/hooks/install.sh            # install (idempotent)
#   Tools/hooks/install.sh --uninstall
#
# Bypass hooks for a single commit with:  git commit --no-verify

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Path stored in git config: relative to repo root so it works for any clone.
HOOKS_REL="Tools/hooks"

uninstall() {
    if git -C "$REPO_ROOT" config --local --get core.hooksPath >/dev/null 2>&1; then
        git -C "$REPO_ROOT" config --local --unset core.hooksPath
        echo -e "${GREEN}✓${NC} Removed core.hooksPath; git will use .git/hooks again."
    else
        echo -e "${YELLOW}core.hooksPath was not set; nothing to uninstall.${NC}"
    fi
}

if [ "${1:-}" = "--uninstall" ]; then
    uninstall
    exit 0
fi

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  FPBInject git hooks installer${NC}"
echo -e "${BLUE}================================================${NC}"

# Make hook files executable (git needs the exec bit).
chmod +x "$SCRIPT_DIR/pre-commit" "$SCRIPT_DIR/commit-msg"

# Point git at our tracked hooks dir. Overrides the inherited Gerrit hook.
git -C "$REPO_ROOT" config --local core.hooksPath "$HOOKS_REL"

# Belt-and-suspenders: also tell any lingering Gerrit hook not to add
# Change-Id trailers, in case some other tooling reads this setting.
git -C "$REPO_ROOT" config --local gerrit.createChangeId false

echo -e "${GREEN}✓${NC} core.hooksPath -> ${HOOKS_REL}"
echo -e "${GREEN}✓${NC} gerrit.createChangeId -> false"
echo -e "${GREEN}✓${NC} hooks enabled: pre-commit (fast format/lint), commit-msg (Change-Id stripper)"
echo ""
echo -e "Bypass for one commit:  ${YELLOW}git commit --no-verify${NC}"
echo -e "Uninstall:              ${YELLOW}Tools/hooks/install.sh --uninstall${NC}"
