#!/usr/bin/env bash
# =============================================================================
# GitPulse Installer
# Usage: ./install.sh
# =============================================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$REPO_DIR/gitpulse/.venv"
BIN="$VENV/bin/gitpulse"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo -e "${BOLD}${CYAN}⚡ GitPulse Installer${NC}"
echo -e "   Git Repo Dashboard TUI"
echo "──────────────────────────────────────"

# ── 1. Check Python ────────────────────────────────────────────────────────
echo -e "${YELLOW}▸ Checking Python version...${NC}"
if ! command -v python3 &>/dev/null; then
    echo "❌ python3 not found. Install Python 3.10+ and try again."
    exit 1
fi
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo $PY_VER | cut -d. -f1)
PY_MINOR=$(echo $PY_VER | cut -d. -f2)
if [[ $PY_MAJOR -lt 3 ]] || [[ $PY_MAJOR -eq 3 && $PY_MINOR -lt 10 ]]; then
    echo "❌ Python 3.10+ required (found $PY_VER)."
    exit 1
fi
echo -e "   ${GREEN}✓ Python $PY_VER${NC}"

# ── 2. Create virtual environment ──────────────────────────────────────────
echo -e "${YELLOW}▸ Setting up virtual environment...${NC}"
python3 -m venv "$VENV"
echo -e "   ${GREEN}✓ Created .venv${NC}"

# ── 3. Install dependencies ────────────────────────────────────────────────
echo -e "${YELLOW}▸ Installing dependencies...${NC}"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -e "$REPO_DIR"
echo -e "   ${GREEN}✓ Installed textual, rich, gitpython${NC}"

# ── 4. Detect shell and add alias ──────────────────────────────────────────
echo -e "${YELLOW}▸ Adding 'gitpulse' command to your shell...${NC}"

ALIAS_LINE="alias gitpulse=\"$BIN\""

# Detect which rc files to update
RC_FILES=()
if [[ -n "$ZSH_VERSION" ]] || [[ "$SHELL" == */zsh ]]; then
    RC_FILES+=("$HOME/.zshrc")
fi
if [[ -n "$BASH_VERSION" ]] || [[ "$SHELL" == */bash ]]; then
    RC_FILES+=("$HOME/.bashrc")
fi
# Fallback — write to both if neither matched
if [[ ${#RC_FILES[@]} -eq 0 ]]; then
    RC_FILES+=("$HOME/.bashrc" "$HOME/.zshrc")
fi

for RC in "${RC_FILES[@]}"; do
    if [[ -f "$RC" ]] || [[ "$RC" == *.zshrc ]]; then
        if grep -q "alias gitpulse=" "$RC" 2>/dev/null; then
            # Update existing alias
            sed -i "s|alias gitpulse=.*|$ALIAS_LINE|" "$RC"
            echo -e "   ${GREEN}✓ Updated existing alias in $RC${NC}"
        else
            echo "" >> "$RC"
            echo "# GitPulse TUI" >> "$RC"
            echo "$ALIAS_LINE" >> "$RC"
            echo -e "   ${GREEN}✓ Added alias to $RC${NC}"
        fi
    fi
done

# ── 5. Done ────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}✅ GitPulse installed successfully!${NC}"
echo ""
echo -e "  ${BOLD}Reload your shell, then run:${NC}"
echo ""
echo -e "   ${CYAN}gitpulse${NC}                         # scans ~/projects"
echo -e "   ${CYAN}gitpulse --root /path/to/repos${NC}   # scans a custom dir"
echo -e "   ${CYAN}gitpulse --root .${NC}                 # scans current directory"
echo ""
echo -e "  ${BOLD}Or reload now with:${NC}"
if [[ "$SHELL" == */zsh ]]; then
    echo -e "   ${CYAN}source ~/.zshrc${NC}"
else
    echo -e "   ${CYAN}source ~/.bashrc${NC}"
fi
echo ""
echo -e "  ${BOLD}Keybindings:${NC}  ↑↓ navigate  /  search  r  refresh  q  quit"
echo ""
