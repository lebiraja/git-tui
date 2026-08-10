#!/usr/bin/env bash
# =============================================================================
# GitPulse Uninstaller
# Usage: ./uninstall.sh
# =============================================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$REPO_DIR/.venv"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo -e "${BOLD}${CYAN}⚡ GitPulse Uninstaller${NC}"
echo -e "   Git Repo Dashboard TUI"
echo "──────────────────────────────────────"

# ── Confirm ────────────────────────────────────────────────────────────────
read -r -p "$(echo -e "${YELLOW}▸ Are you sure you want to uninstall GitPulse? [y/N]: ${NC}")" CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo -e "${CYAN}  Aborted.${NC}"
    echo ""
    exit 0
fi

# ── 1. Remove virtual environment ──────────────────────────────────────────
echo -e "${YELLOW}▸ Removing virtual environment...${NC}"
if [[ -d "$VENV" ]]; then
    rm -rf "$VENV"
    echo -e "   ${GREEN}✓ Removed .venv${NC}"
else
    echo -e "   ${CYAN}  .venv not found, skipping${NC}"
fi

# ── 2. Remove egg-info build artifacts ─────────────────────────────────────
echo -e "${YELLOW}▸ Removing build artifacts...${NC}"
find "$REPO_DIR" -maxdepth 3 -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true
find "$REPO_DIR" -maxdepth 3 -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
echo -e "   ${GREEN}✓ Cleaned build artifacts${NC}"

# ── 3. Remove the console-script symlink ───────────────────────────────────
echo -e "${YELLOW}▸ Removing the 'gitpulse' command...${NC}"

LINK="$HOME/.local/bin/gitpulse"
if [[ -L "$LINK" ]]; then
    # Only remove a symlink that points into this checkout, so a pip/pipx
    # install of gitpulse living at the same path is left alone.
    #
    # Read the link literally rather than with `readlink -f`: step 1 has
    # already deleted .venv, so the link is dangling and -f would resolve to
    # an empty string, causing this check to skip the very link it created.
    TARGET="$(readlink "$LINK" 2>/dev/null || true)"
    case "$TARGET" in
        "$REPO_DIR"/*)
            rm -f "$LINK"
            echo -e "   ${GREEN}✓ Removed $LINK${NC}"
            ;;
        *)
            echo -e "   ${YELLOW}! $LINK points outside this checkout — left in place${NC}"
            ;;
    esac
fi

# ── 4. Remove alias/PATH from shell rc files ───────────────────────────────
echo -e "${YELLOW}▸ Removing shell configuration...${NC}"

# GNU sed takes `-i` with no argument; BSD/macOS sed requires an explicit
# backup suffix, so `sed -i <script>` fails there with "invalid command code".
# Edit via a temp file instead — portable everywhere. Writing back with `cat`
# rather than `mv` keeps the original file's permissions and ownership.
sed_delete() {
    local script="$1" file="$2" tmp
    tmp="$(mktemp)" || return 1
    sed "$script" "$file" > "$tmp" && cat "$tmp" > "$file"
    rm -f "$tmp"
}

RC_FILES=("$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.bash_profile" "$HOME/.zprofile")

for RC in "${RC_FILES[@]}"; do
    [[ -f "$RC" ]] || continue
    if grep -q "gitpulse\|GitPulse TUI" "$RC" 2>/dev/null; then
        # Remove the GitPulse TUI comment line, the alias line, and the PATH line
        sed_delete '/# GitPulse TUI/d; /alias gitpulse=/d; /gitpulse.*PATH/d' "$RC"
        # Collapse the blank line the old installer left behind
        sed_delete '/^$/N;/^\n$/D' "$RC"
        echo -e "   ${GREEN}✓ Removed from $(basename "$RC")${NC}"
    fi
done

# ── 5. Report anything that still answers to `gitpulse` ────────────────────
# A leftover pip/pipx/npm install is not this script's to remove, but leaving
# the user to discover it themselves is how #43 happened.
REMAINING="$(command -v gitpulse 2>/dev/null || true)"
if [[ -n "$REMAINING" ]]; then
    echo ""
    echo -e "${RED}▸ Note: 'gitpulse' still resolves to:${NC}"
    echo -e "   ${CYAN}$REMAINING${NC}"
    echo -e "   That is a separate installation. Remove it with one of:"
    case "$REMAINING" in
        *"/.local/pipx/"*|*"/pipx/venvs/"*)
            echo -e "     ${CYAN}pipx uninstall gitpulse-tui${NC}" ;;
        *"/node_modules/"*|*"/npm/"*)
            echo -e "     ${CYAN}npm uninstall -g gitpulse-tui${NC}" ;;
        *)
            echo -e "     ${CYAN}pip uninstall gitpulse-tui${NC}"
            echo -e "     ${CYAN}npm uninstall -g gitpulse-tui${NC}"
            echo -e "     ${CYAN}pipx uninstall gitpulse-tui${NC}" ;;
    esac
fi

# ── 6. Done ────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}✅ GitPulse uninstalled successfully!${NC}"
echo ""
echo -e "  Open a new terminal to clear any 'gitpulse' alias still loaded"
echo -e "  in this session."
echo ""
echo -e "  The repo folder ${CYAN}$REPO_DIR${NC} was kept."
echo -e "  To fully remove it:  ${CYAN}rm -rf $REPO_DIR${NC}"
echo ""
