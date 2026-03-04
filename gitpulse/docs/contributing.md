# Contributing to GitPulse

Thank you for your interest in contributing! This document covers environment setup, project conventions, and step-by-step guides for common contribution types.

---

## Prerequisites

- **Python 3.10+** (the codebase uses `match`, `|` union types, and `from __future__ import annotations`)
- **git** installed and on your PATH
- A terminal that supports 256 colours (or true colour for the best experience)

---

## Development Setup

```bash
# 1. Clone the repository
git clone https://github.com/yourname/git-tui.git
cd git-tui/gitpulse

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app (scan your ~/projects)
python main.py

# 5. Run against a specific folder (great for testing with a small set of repos)
python main.py --root /tmp/test-repos
```

### Creating test repos

```bash
# Make a handful of dummy repos for local testing
mkdir -p /tmp/test-repos
for name in alpha beta gamma; do
  mkdir /tmp/test-repos/$name
  cd /tmp/test-repos/$name
  git init
  git commit --allow-empty -m "Initial commit"
  cd -
done
python main.py --root /tmp/test-repos
```

---

## Project Conventions

### Code style

- **Black** formatting preferred (`pip install black && black .`)
- Type hints on all public functions and methods
- Docstrings on all public classes and functions (Google style)
- Private helpers prefixed with `_`
- No global mutable state outside of `GitPulseApp`

### Import order

1. Standard library
2. Third-party (`textual`, `rich`, `git`)
3. Local (`scanner`, `git_ops`, `ui.*`)

Separate each group with a blank line.

### Error handling

All git operations must be **non-fatal**. Wrap git calls in try/except and return a safe default (empty list, empty string, or a default dataclass). Never let a bad repo crash the TUI.

```python
# Good
try:
    result = repo.git.some_command()
except Exception:
    result = ""

# Bad — will crash the app if the repo is broken
result = repo.git.some_command()
```

---

## Making Changes

### Changing the git data layer (`git_ops.py`)

1. Add your new data class (if needed) in the **Data models** section.
2. Add your public function after the existing ones in the **Public API** section.
3. Update `docs/api_reference.md` with the new class/function.
4. Call your function from `ui/tabs.py` or `main.py` as appropriate.

**Example — adding `get_ignored(path)`:**

```python
# git_ops.py
@dataclass
class IgnoredFiles:
    paths: list[str] = field(default_factory=list)

def get_ignored(path: Path) -> IgnoredFiles:
    """Return a list of git-ignored files."""
    repo = _open_repo(path)
    try:
        output = repo.git.ls_files("--others", "--ignored", "--exclude-standard")
        return IgnoredFiles(paths=output.splitlines())
    except Exception:
        return IgnoredFiles()
```

---

### Adding a new tab to the main panel (`ui/tabs.py`)

See [ui_components.md → Adding a New Tab](./ui_components.md#adding-a-new-tab) for the step-by-step guide.

Quick checklist:
- [ ] Add `TabPane` in `MainPanel.compose()`
- [ ] Set up `DataTable` columns in `on_mount()` if needed
- [ ] Write `_load_mytab(repo_path)` method
- [ ] Call `_load_mytab()` from `load_repo()`
- [ ] Update `ui/styles.tcss` if custom styling needed
- [ ] Update `docs/ui_components.md`

---

### Adding a new keybinding (`main.py`)

1. Add a `Binding` to `GitPulseApp.BINDINGS`:
   ```python
   Binding("x", "my_action", "My Action", show=True)
   ```
   Set `show=True` to display it in the footer, `show=False` to hide it.

2. Add an `action_my_action()` method to `GitPulseApp`:
   ```python
   def action_my_action(self) -> None:
       """Description of what this does."""
       # your code here
   ```

3. Update `README.md` keybindings table and `docs/index.md`.

---

### Changing the sort order of repos

Repos are sorted in `GitPulseApp._scan_and_populate()`:

```python
# Current: sort by most recent commit (descending)
self._all_repos.sort(key=lambda r: r.last_commit_ts, reverse=True)
```

To sort alphabetically:
```python
self._all_repos.sort(key=lambda r: r.name.lower())
```

To sort by status (MODIFIED first):
```python
_status_order = {RepoStatus.MODIFIED: 0, RepoStatus.UNTRACKED: 1, RepoStatus.CLEAN: 2}
self._all_repos.sort(key=lambda r: _status_order[r.status])
```

---

### Changing the scanner behaviour (`scanner.py`)

To skip additional directories, add names to `SKIP_DIRS`:
```python
SKIP_DIRS = {
    "node_modules",
    "my_custom_build_dir",  # ← Add here
    ...
}
```

To also scan hidden directories (starting with `.`), remove the `.startswith(".")` check in `_walk()`:
```python
# Before
if child.is_dir() and child.name not in SKIP_DIRS and not child.name.startswith("."):

# After (scans hidden dirs too)
if child.is_dir() and child.name not in SKIP_DIRS:
```

---

## File Checklist for Common Tasks

| Task | Files to edit |
|------|--------------|
| New git data operation | `git_ops.py`, `ui/tabs.py`, `docs/api_reference.md` |
| New sidebar feature | `ui/sidebar.py`, `main.py`, `ui/styles.tcss` |
| New main panel tab | `ui/tabs.py`, `ui/styles.tcss`, `docs/ui_components.md` |
| New keybinding | `main.py`, `README.md`, `docs/index.md` |
| Theme change | `ui/styles.tcss`, `ui/sidebar.py`, `ui/tabs.py` |
| Scanner behaviour | `scanner.py` |

---

## Debugging Tips

### Enable Textual's built-in devtools

Run with the `--dev` flag to open the Textual inspector:
```bash
python main.py --dev
```
This opens a separate browser-based panel showing the widget tree, CSS, and events in real time.

### Redirect log output

Textual logs to stderr by default. Capture them:
```bash
python main.py 2>debug.log
tail -f debug.log
```

Or add explicit log lines in your code:
```python
from textual import log
log("my_value =", my_value)
```

### Test git_ops in isolation

All `git_ops` functions are pure Python and can be tested in a REPL:
```python
from pathlib import Path
from git_ops import get_commits, get_stashes

path = Path("/path/to/your/test/repo")
commits = get_commits(path, n=5)
for c in commits:
    print(c.short_hash, c.message)
```

---

## Submitting Changes

1. Fork the repository and create a feature branch: `git checkout -b feature/my-feature`
2. Make your changes following the conventions above
3. Test manually: run the app against a real `--root` directory with at least 3–5 repos
4. Update relevant `docs/` files
5. Open a pull request with a clear description of what changed and why
