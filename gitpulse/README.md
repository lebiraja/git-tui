# ⚡ GitPulse — Git Repo Dashboard TUI

A developer-focused terminal dashboard that scans a root directory for all local Git repositories and displays live status, recent commits, diffs, and branch management — all from the terminal.

Built with **Python**, **Textual**, **Rich**, and **GitPython**.

## Features

- **Repo Discovery** — Recursively scans a configurable root directory for `.git` repos
- **Status Badges** — Color-coded: 🟢 CLEAN / 🟡 MODIFIED / 🔴 UNTRACKED
- **Tabbed Main Panel** — Status, Commits, Diff (syntax-highlighted), and Branches
- **Branch Switching** — Press `Enter` on any branch to check it out
- **Keyboard-driven** — Full keyboard navigation

## Installation

```bash
cd gitpulse
pip install -r requirements.txt
```

## Usage

```bash
# Scan ~/projects (default)
python main.py

# Scan a custom directory
python main.py --root /path/to/your/repos
```

## Keybindings

| Key              | Action                         |
| ---------------- | ------------------------------ |
| `↑` / `↓`       | Navigate repo list             |
| `Tab`            | Next focus area                |
| `Shift+Tab`      | Previous focus area            |
| `Enter`          | Switch branch (Branches tab)   |
| `r`              | Refresh / rescan all repos     |
| `q`              | Quit                           |

## Project Structure

```
gitpulse/
├── main.py          # Entry point, launches Textual app
├── scanner.py       # Recursive repo discovery logic
├── git_ops.py       # All git operations (status, commits, diff, branches)
├── ui/
│   ├── sidebar.py   # Repo list widget
│   ├── tabs.py      # Main panel tabs
│   └── styles.tcss  # Textual CSS styles
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.10+
- `textual >= 0.50.0`
- `rich >= 13.0.0`
- `gitpython >= 3.1.0`
