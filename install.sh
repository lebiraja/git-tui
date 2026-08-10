#!/usr/bin/env bash
# =============================================================================
# GitPulse Installer
# Usage: ./install.sh
# =============================================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$REPO_DIR/.venv"

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
"$VENV/bin/pip" install --quiet --upgrade pip 2>/dev/null || true
"$VENV/bin/pip" install --quiet -e "$REPO_DIR"
echo -e "   ${GREEN}✓ Installed textual, rich, gitpython${NC}"

# ── 4. Expose the `gitpulse` command ───────────────────────────────────────
# The venv already provides a console script. Symlinking it into a directory
# on PATH is better than writing an alias into rc files: an alias hardcodes an
# absolute path that silently breaks if the checkout is moved or deleted, and
# it shadows any other GitPulse install (pip, pipx, npm) for the whole shell.
echo -e "${YELLOW}▸ Exposing the 'gitpulse' command...${NC}"

CONSOLE_SCRIPT="$VENV/bin/gitpulse"
LINK_DIR="$HOME/.local/bin"
LINK="$LINK_DIR/gitpulse"

mkdir -p "$LINK_DIR"
ln -sf "$CONSOLE_SCRIPT" "$LINK"
echo -e "   ${GREEN}✓ Linked $LINK → .venv/bin/gitpulse${NC}"

# Remove aliases written by older versions of this installer; they point at an
# absolute path and would take precedence over the symlink.
#
# GNU sed takes `-i` with no argument; BSD/macOS sed requires an explicit
# (possibly empty) backup suffix, so `sed -i <script>` fails there with
# "invalid command code". Edit to a temp file instead — portable everywhere.
sed_delete() {
    local script="$1" file="$2" tmp
    tmp="$(mktemp)" || return 1
    sed "$script" "$file" > "$tmp" && cat "$tmp" > "$file"
    rm -f "$tmp"
}

for RC in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.bash_profile" "$HOME/.zprofile"; do
    [[ -f "$RC" ]] || continue
    if grep -q "alias gitpulse=" "$RC" 2>/dev/null; then
        sed_delete '/^# GitPulse TUI$/d; /alias gitpulse=/d' "$RC"
        echo -e "   ${GREEN}✓ Removed the old alias from $(basename "$RC")${NC}"
    fi
done

if ! echo ":$PATH:" | grep -q ":$LINK_DIR:"; then
    echo -e "   ${YELLOW}! $LINK_DIR is not on your PATH${NC}"
    echo -e "     bash/zsh:  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
    echo -e "     fish:      fish_add_path ~/.local/bin"
fi

# ── 5. Done ────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}✅ GitPulse installed successfully!${NC}"
echo ""
echo -e "  ${BOLD}Run it with:${NC}"
echo ""
echo -e "   ${CYAN}gitpulse${NC}                         # scans current directory"
echo -e "   ${CYAN}gitpulse --root /path/to/repos${NC}   # scans a custom dir"
echo -e "   ${CYAN}gitpulse --commits 20${NC}            # show more commits"
echo ""
echo -e "  ${BOLD}Keybindings (press ? in the app for the full sheet):${NC}"
echo ""
echo -e "  ${BOLD}Global:${NC}       ↑↓ navigate  /  search  r  refresh  q  quit"
echo -e "  ${BOLD}Status tab:${NC}   s  stage    u  unstage    a  stage-all    c  commit"
echo -e "               z  stash    Z  pop-stash"
echo -e "  ${BOLD}Commits tab:${NC}  Enter / d  view commit diff"
echo -e "  ${BOLD}Branches:${NC}     Enter  switch    n  new branch    d  delete"
echo -e "  ${BOLD}Remotes:${NC}      f  fetch    p  pull    P  push"
echo -e "  ${BOLD}Tree tab:${NC}     Enter  preview file contents"
echo ""
