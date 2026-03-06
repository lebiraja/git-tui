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

# ── 3. Remove alias/PATH from shell rc files ───────────────────────────────
echo -e "${YELLOW}▸ Removing shell configuration...${NC}"

RC_FILES=("$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.bash_profile")

for RC in "${RC_FILES[@]}"; do
    [[ -f "$RC" ]] || continue
    if grep -q "gitpulse\|GitPulse TUI" "$RC" 2>/dev/null; then
        # Remove the GitPulse TUI comment line, the alias line, and the PATH line
        sed -i '/# GitPulse TUI/d' "$RC"
        sed -i '/alias gitpulse=/d' "$RC"
        sed -i '/gitpulse.*PATH/d' "$RC"
        # Also remove any blank line that was added before the alias block
        # (safe: collapses multiple consecutive blank lines to one)
        sed -i '/^$/N;/^\n$/d' "$RC"
        echo -e "   ${GREEN}✓ Removed from $(basename $RC)${NC}"
    fi
done

# ── 4. Done ────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}✅ GitPulse uninstalled successfully!${NC}"
echo ""
echo -e "  Reload your shell to apply changes:"
echo -e "   ${CYAN}source ~/.bashrc${NC}   # bash users"
echo -e "   ${CYAN}source ~/.zshrc${NC}    # zsh users"
echo ""
echo -e "  The repo folder ${CYAN}$REPO_DIR${NC} was kept."
echo -e "  To fully remove it:  ${CYAN}rm -rf $REPO_DIR${NC}"
echo ""
