# ⚡ GitPulse — Git Repo Dashboard TUI

A developer-focused terminal dashboard that scans a root directory for all local Git repositories and displays live status, recent commits, diffs, and branch management — all from the terminal.

Built with **Python**, **Textual**, **Rich**, and **GitPython**.

## Install (one command)

```bash
git clone https://github.com/yourname/git-tui.git
cd git-tui
./install.sh
```

That's it. The installer:
- Checks your Python version (3.10+ required)
- Creates a virtual environment automatically
- Installs all dependencies
- Adds the `gitpulse` command to your shell (`~/.zshrc` / `~/.bashrc`)

Then reload your shell:
```bash
source ~/.zshrc   # or source ~/.bashrc
```

## Usage

```bash
gitpulse                          # scans ~/projects (default)
gitpulse --root /path/to/repos   # scans a custom directory
gitpulse --root .                 # scans current directory
```

## Features

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
  - **🌲 Tree** — Visual file hierarchy of all tracked files

## Keybindings

| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate repo list |
| `/` | Focus search/filter |
| `Escape` | Clear search |
| `Tab` / `Shift+Tab` | Next/previous focus area |
| `Enter` | Switch branch (Branches tab) |
| `r` | Refresh / rescan all repos |
| `q` | Quit |

## Requirements

- Python 3.10+
- Linux / macOS

## Documentation

See [docs/](./gitpulse/docs/) for full developer documentation:
- [Architecture](./gitpulse/docs/architecture.md)
- [API Reference](./gitpulse/docs/api_reference.md)
- [UI Components](./gitpulse/docs/ui_components.md)
- [Theming](./gitpulse/docs/theming.md)
- [Contributing](./gitpulse/docs/contributing.md)
