# GitPulse Documentation

Welcome to the **GitPulse** developer documentation. GitPulse is a terminal-based Git repository dashboard built with Python and the Textual TUI framework. This folder contains everything you need to understand, extend, or contribute to the codebase.

---

## Table of Contents

| Document | Description |
|---|---|
| [installation.md](./installation.md) | One-command installer, pyproject.toml setup, how dual-mode imports work |
| [architecture.md](./architecture.md) | System architecture, data flow, and module relationships |
| [api_reference.md](./api_reference.md) | Full reference for every data class and public function in `git_ops.py` and `scanner.py` |
| [ui_components.md](./ui_components.md) | Textual widget guide — sidebar, tabs, modal screens, messages, and events |
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
├── main.py          ← App entry point, keybindings, startup scan, message routing
├── scanner.py       ← Recursive .git discovery
├── git_ops.py       ← All git data models and operations (read + write)
├── ui/
│   ├── __init__.py  ← Package marker
│   ├── sidebar.py   ← Left panel: repo list + search
│   ├── tabs.py      ← Right panel: 7 tabs + 3 modal screens
│   └── styles.tcss  ← Textual CSS (Tokyo Night theme)
├── docs/            ← You are here
├── requirements.txt
└── README.md
```

---

## Keyboard Shortcuts

### Global (always active)

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Rescan all repos |
| `/` | Focus search filter |
| `Esc` | Clear search / close modal |
| `Tab` / `Shift+Tab` | Cycle focus between sidebar and panel |

### Main Panel (when panel has focus)

| Key | Action | Active Tab |
|-----|--------|------------|
| `s` | Stage highlighted file | Status |
| `u` | Unstage highlighted file | Status |
| `a` | Stage all changes | Any |
| `Shift+U` | Unstage all | Any |
| `c` | Open commit dialog | Any |
| `n` | Create new branch | Any |
| `Enter` | Switch branch / View commit diff | Branches / Commits |
| `d` | Delete branch / View commit diff | Branches / Commits |

### Modal Screens

| Key | Action |
|-----|--------|
| `Enter` | Submit (commit, create branch) |
| `Esc` / `q` | Close / cancel |

---

## Key Concepts

- **Read + write git operations** — `git_ops.py` handles both querying (status, log, diff) and mutating operations (stage, commit, branch). All mutations return a human-readable result string.
- **Lazy tab loading** — tabs are only populated the first time they become visible for each selected repo (`_loaded_tabs` set tracks this). Switching repos clears the set, triggering fresh loads.
- **Modal screens** — commit dialog, new branch dialog, and commit diff viewer are Textual `ModalScreen` subclasses pushed onto the screen stack with `app.push_screen()`.
- **Message-based communication** — widgets talk to each other by posting `Message` subclasses up the DOM, never by importing each other directly.
- **No global state** — `GitPulseApp` is the single source of truth for the repo list, search state, and selected repo.
- **TCSS for styling** — All visual styling lives in `ui/styles.tcss`, not in Python code.
