# Installation & Packaging

This document explains how GitPulse is packaged, how the installer works, and how to distribute it to other developers.

---

## What Was Added

| File | Purpose |
|------|---------|
| [`install.sh`](../../install.sh) | One-command installer for end users |
| [`pyproject.toml`](../../pyproject.toml) | Package definition, entry point registration |
| [`gitpulse/__init__.py`](../__init__.py) | Makes `gitpulse/` a proper Python package |
| [`gitpulse/__main__.py`](../__main__.py) | Enables `python -m gitpulse` |

---

## How the Installer Works (`install.sh`)

The script lives at the **repo root** and handles the full setup automatically:

```
install.sh
├── 1. Check Python 3.10+ is available
├── 2. Create .venv inside gitpulse/
├── 3. pip install -e . (editable install from pyproject.toml)
├── 4. Detect shell (zsh → ~/.zshrc, bash → ~/.bashrc)
└── 5. Append/update:  alias gitpulse="/path/to/.venv/bin/gitpulse"
```

After running `install.sh`, users reload their shell once (`source ~/.zshrc`) and the `gitpulse` command is available globally, forever.

**For a developer cloning the repo:**
```bash
git clone https://github.com/yourname/git-tui.git
cd git-tui
./install.sh
source ~/.zshrc   # or source ~/.bashrc
gitpulse          # ✅ works
```

---

## How the Package Is Defined (`pyproject.toml`)

`pyproject.toml` lives at the **repo root** (not inside `gitpulse/`), so setuptools sees the `gitpulse/` directory as the top-level package.

```toml
[project.scripts]
gitpulse = "gitpulse.cli:main"
```

This registers the `gitpulse` command in the venv's `bin/` directory when installed. It points directly to the `main()` function in `gitpulse/main.py`.

```toml
[tool.setuptools.packages.find]
where = ["."]
include = ["gitpulse*"]
```

This tells setuptools to include the `gitpulse` package and its `gitpulse.ui` sub-package.

---

## How Imports Work

Modules use **relative imports** throughout:

```python
from .scanner import scan_repos
from .git_ops import get_repo_info
from .ui.sidebar import RepoSidebar
```

Earlier versions carried a `try`/`except ImportError` block in every module so
that `python main.py` would work from inside the package directory. That
fallback mutated `sys.path` at import time, which made `import gitpulse` unsafe
inside another process, so it was removed. Run the package with `python -m
gitpulse` (or the `gitpulse` console script) instead.

The CSS path is made absolute so it works from any working directory:
```python
CSS_PATH = str(Path(__file__).parent / "ui" / "styles.tcss")
```

---

## Running Without Installation

You can always run directly without installing:
```bash
cd /path/to/git-tui
source .venv/bin/activate
python -m gitpulse --root ~/projects
```

Or:
```bash
cd /path/to/git-tui
.venv/bin/python -m gitpulse --root ~/projects
```

---

## Re-installing After Code Changes

Since it's installed in **editable mode** (`pip install -e .`), any changes to the source files are reflected immediately — no reinstall needed. The only time you need to re-run `install.sh` is if you add new dependencies to `pyproject.toml`.

---

## Uninstalling

```bash
# Remove the gitpulse package from the venv
/path/to/git-tui/gitpulse/.venv/bin/pip uninstall gitpulse

# Remove the alias from your shell config
# Edit ~/.zshrc or ~/.bashrc and delete the line:
# alias gitpulse="..."
```
