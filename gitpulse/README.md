# ⚡ GitPulse — Git Repo Dashboard TUI

A developer-focused terminal dashboard that scans a root directory for all local Git repositories and displays live status, recent commits, diffs, and branch management — all from the terminal.

Built with **Python**, **Textual**, **Rich**, and **GitPython**.

## Features

- **Repo Discovery** — Recursively scans a configurable root directory for `.git` repos
- **Sorted by Activity** — Repos ordered by most recent commit date
- **Status Badges** — Color-coded with file counts: 🟢 CLEAN / 🟡 MODIFIED (3) / 🔴 UNTRACKED (2)
- **Relative Time** — "2h ago", "3d ago" shown next to each repo
- **Search/Filter** — Press `/` to filter repos by name
- **Tabbed Main Panel**:
  - **📋 Status** — Repo summary header, staged/unstaged/untracked files with icons, stash list
  - **📝 Commits** — Last 10 commits with diff stats (files changed, insertions, deletions)
  - **🔀 Diff** — Syntax-highlighted uncommitted changes
  - **🌿 Branches** — All local branches, press Enter to switch
  - **🌐 Remotes** — Remote URLs with ahead/behind sync status
  - **🏷️ Tags** — Recent tags with date and tagger info

## Installation

```bash
cd gitpulse
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Usage

```bash
# Scan ~/projects (default)
.venv/bin/python main.py

# Scan a custom directory
.venv/bin/python main.py --root /path/to/your/repos
```

## Keybindings

| Key              | Action                         |
| ---------------- | ------------------------------ |
| `↑` / `↓`       | Navigate repo list             |
| `/`              | Focus search/filter            |
| `Escape`         | Clear search                   |
| `Tab`            | Next focus area                |
| `Shift+Tab`      | Previous focus area            |
| `Enter`          | Switch branch (Branches tab)   |
| `r`              | Refresh / rescan all repos     |
| `q`              | Quit                           |

## Project Structure

```
gitpulse/
├── main.py          # Entry point, app assembly, keybindings
├── scanner.py       # Recursive repo discovery logic
├── git_ops.py       # Git operations (status, commits, diff, branches, stash, remotes, tags)
├── ui/
│   ├── sidebar.py   # Repo list widget with search
│   ├── tabs.py      # Main panel tabs (Status, Commits, Diff, Branches, Remotes, Tags)
│   └── styles.tcss  # Textual CSS styles (Tokyo Night theme)
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.10+
- `textual >= 0.50.0`
- `rich >= 13.0.0`
- `gitpython >= 3.1.0`
