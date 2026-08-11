#!/usr/bin/env bash
# =============================================================================
# GitPulse Installer
# Usage: ./install.sh
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
echo -e "${BOLD}${CYAN}⚡ GitPulse Installer${NC}"
echo -e "   Git Repo Dashboard TUI"
echo "──────────────────────────────────────"

# ── 1. Check Python ────────────────────────────────────────────────────────
# Probe several names: `python3` is absent on some Windows/Git Bash setups and
# on minimal images where only `python` exists. Ask the interpreter for its own
# version rather than parsing a version string.
echo -e "${YELLOW}▸ Checking Python version...${NC}"

PYTHON=""
for candidate in python3 python py; do
    command -v "$candidate" >/dev/null 2>&1 || continue
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo -e "${RED}❌ Python 3.10+ is required but was not found.${NC}"
    echo ""
    echo "   macOS:   brew install python@3.12"
    echo "   Debian:  sudo apt install python3 python3-venv"
    echo "   Fedora:  sudo dnf install python3"
    echo "   Windows: https://www.python.org/downloads/"
    exit 1
fi

PY_VER="$("$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
echo -e "   ${GREEN}✓ Python $PY_VER ($PYTHON)${NC}"

# ── 2. Create virtual environment ──────────────────────────────────────────
echo -e "${YELLOW}▸ Setting up virtual environment...${NC}"
if ! "$PYTHON" -m venv "$VENV" 2>/tmp/gitpulse-venv-err; then
    echo -e "${RED}❌ Could not create a virtual environment.${NC}"
    sed 's/^/   /' /tmp/gitpulse-venv-err 2>/dev/null | tail -5
    echo ""
    echo "   Debian/Ubuntu users usually need:  sudo apt install python3-venv"
    rm -f /tmp/gitpulse-venv-err
    exit 1
fi
rm -f /tmp/gitpulse-venv-err
echo -e "   ${GREEN}✓ Created .venv${NC}"

# ── 3. Install dependencies ────────────────────────────────────────────────
# POSIX venvs put executables in bin/; Windows venvs (Git Bash, MSYS) use
# Scripts/. Detect rather than assume, so the script also works under Git Bash.
if [[ -d "$VENV/Scripts" ]]; then
    VENV_BIN="$VENV/Scripts"
else
    VENV_BIN="$VENV/bin"
fi

echo -e "${YELLOW}▸ Installing dependencies...${NC}"
"$VENV_BIN/python" -m pip install --quiet --upgrade pip 2>/dev/null || true
if ! "$VENV_BIN/python" -m pip install --quiet -e "$REPO_DIR" 2>/tmp/gitpulse-pip-err; then
    echo -e "${RED}❌ Dependency installation failed.${NC}"
    sed 's/^/   /' /tmp/gitpulse-pip-err 2>/dev/null | tail -8
    echo ""
    echo "   If you are offline, connect and re-run ./install.sh"
    rm -f /tmp/gitpulse-pip-err
    exit 1
fi
rm -f /tmp/gitpulse-pip-err
echo -e "   ${GREEN}✓ Installed textual, rich, gitpython${NC}"

# ── 4. Expose the `gitpulse` command ───────────────────────────────────────
# The venv already provides a console script. Symlinking it into a directory
# on PATH is better than writing an alias into rc files: an alias hardcodes an
# absolute path that silently breaks if the checkout is moved or deleted, and
# it shadows any other GitPulse install (pip, pipx, npm) for the whole shell.
echo -e "${YELLOW}▸ Exposing the 'gitpulse' command...${NC}"

CONSOLE_SCRIPT="$VENV_BIN/gitpulse"
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

# ── 5. Verify the command actually resolves to what we just installed ──────
# Reporting success while a stale binary or alias wins the name is the single
# most confusing failure this installer can produce (see issue #43), so check
# rather than assume.
echo -e "${YELLOW}▸ Verifying...${NC}"

PATH_OK=1
SHADOWED=0
if ! printf '%s' ":$PATH:" | grep -q ":$LINK_DIR:"; then
    PATH_OK=0
    echo -e "   ${YELLOW}! $LINK_DIR is not on your PATH${NC}"
    echo -e "     bash:  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
    echo -e "     zsh:   echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc"
    echo -e "     fish:  fish_add_path ~/.local/bin"
fi

# `command -v` reflects the PATH this script sees. A login shell may differ,
# but a conflict here is a conflict there too.
RESOLVED="$(command -v gitpulse 2>/dev/null || true)"

if [[ $PATH_OK -eq 1 && -n "$RESOLVED" && "$RESOLVED" != "$LINK" ]]; then
    SHADOWED=1
    echo -e "   ${RED}✗ Another 'gitpulse' takes precedence:${NC}"
    echo -e "     ${RED}$RESOLVED${NC}"
    echo ""
    echo -e "     That one will run instead of the version just installed."
    echo -e "     Remove it, then re-open your terminal:"
    echo ""
    case "$RESOLVED" in
        *"/.local/pipx/"*|*"/pipx/venvs/"*)
            echo -e "       ${CYAN}pipx uninstall gitpulse-tui${NC}" ;;
        *"/node_modules/"*|*"/npm/"*)
            echo -e "       ${CYAN}npm uninstall -g gitpulse-tui${NC}" ;;
        *)
            echo -e "       ${CYAN}pip uninstall gitpulse-tui${NC}   # if pip installed it"
            echo -e "       ${CYAN}rm '$RESOLVED'${NC}               # otherwise" ;;
    esac
    echo ""
elif [[ $PATH_OK -eq 1 ]]; then
    # Confirm the symlink really launches: a broken venv would surface here
    # rather than the first time the user runs it.
    if INSTALLED_VER="$("$LINK" --version 2>/dev/null)"; then
        echo -e "   ${GREEN}✓ $INSTALLED_VER${NC}"
    else
        echo -e "   ${RED}✗ '$LINK' did not run — the virtualenv may be broken.${NC}"
        echo -e "     Try: ${CYAN}rm -rf '$VENV' && ./install.sh${NC}"
        exit 1
    fi
fi

# An alias defined in the *current* shell outlives this script and beats PATH.
# The rc files were already cleaned above; warn about the live session too.
if [[ -n "${BASH_VERSION:-}" ]] && alias gitpulse >/dev/null 2>&1; then
    echo -e "   ${YELLOW}! This shell still has a 'gitpulse' alias loaded.${NC}"
    echo -e "     Run ${CYAN}unalias gitpulse${NC} or open a new terminal."
fi

# ── 6. Done ────────────────────────────────────────────────────────────────
echo ""
if [[ $SHADOWED -eq 1 ]]; then
    echo -e "${BOLD}${YELLOW}⚠  GitPulse installed, but another copy shadows it.${NC}"
    echo -e "   Resolve the conflict above, or run it directly:"
    echo -e "   ${CYAN}$LINK${NC}"
elif [[ $PATH_OK -eq 0 ]]; then
    echo -e "${BOLD}${YELLOW}⚠  GitPulse installed — add $LINK_DIR to your PATH.${NC}"
    echo -e "   Until then, run it directly: ${CYAN}$LINK${NC}"
else
    echo -e "${BOLD}${GREEN}✅ GitPulse installed successfully!${NC}"
fi
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
