# GitPulse Documentation

Welcome to the **GitPulse** developer documentation. GitPulse is a terminal-based Git repository dashboard built with Python and the Textual TUI framework. This folder contains everything you need to understand, extend, or contribute to the codebase.

---

## Table of Contents

| Document | Description |
|---|---|
| [architecture.md](./architecture.md) | System architecture, data flow, and module relationships |
| [api_reference.md](./api_reference.md) | Full reference for every data class and public function in `git_ops.py` and `scanner.py` |
| [ui_components.md](./ui_components.md) | Textual widget guide — sidebar, tabs, messages, and events |
| [theming.md](./theming.md) | How the Textual CSS theme works and how to customise it |
| [contributing.md](./contributing.md) | Setup instructions, coding standards, and how to add new features |

---

## Quick Start

```bash
# Clone the repo
git clone https://github.com/yourname/git-tui.git
cd git-tui/gitpulse

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate       # Windows

# Install dependencies
pip install -r requirements.txt

# Run against your ~/projects directory
python main.py

# Run against a custom directory
python main.py --root /path/to/your/repos
```

---

## Project Structure

```
gitpulse/
├── main.py          ← App entry point, keybindings, startup scan
├── scanner.py       ← Recursive .git discovery
├── git_ops.py       ← All git data models and operations
├── ui/
│   ├── __init__.py  ← Package marker
│   ├── sidebar.py   ← Left panel: repo list + search
│   ├── tabs.py      ← Right panel: Status/Commits/Diff/Branches/Remotes/Tags
│   └── styles.tcss  ← Textual CSS (Tokyo Night theme)
├── docs/            ← You are here
├── requirements.txt
└── README.md
```

---

## Key Concepts

- **All git operations are synchronous** — called from the main Textual thread. For repos with a very deep history, `get_repo_info()` caps commit traversal at 500 commits for performance.
- **Message-based communication** — Textual widgets talk to each other by posting `Message` subclasses up the DOM, never by importing each other directly.
- **No global state** — `GitPulseApp` is the single source of truth for the repo list, search state, and selected repo.
- **TCSS for styling** — All visual styling lives in `ui/styles.tcss`, not in Python code.
