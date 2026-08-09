# ⚡ GitPulse — Git Repo Dashboard TUI

A developer-focused terminal dashboard that scans a root directory for all local Git repositories and displays live status, recent commits, diffs, and branch management — all from the terminal.

Built with **Python**, **Textual**, **Rich**, and **GitPython**.

## Why GitPulse?

A lot of development happens late at night, and not everyone commits or pushes
their changes right away. With "vibe coding" becoming so popular, many people
now juggle several projects at once — and that makes it genuinely hard to keep
track of every local repository.

GitPulse exists to solve exactly that. It gives you a single dashboard for all
your local repos, so at a glance you can see what's committed but not yet
pushed, what's changed but not yet committed, the number of modified files, the
current branch, the last commit, and everything else about the state of each
local Git repository.

## Screenshots

**Demo** — GitPulse in action

![GitPulse demo](https://raw.githubusercontent.com/lebiraja/gitpulse/main/ss/gitpulse.gif)

**Status tab** — repo summary cards, staged/unstaged/untracked/stash workspace, and the file tree / recent commits / remote summary side panels

![Status tab](https://raw.githubusercontent.com/lebiraja/gitpulse/main/ss/status.png)

**Commits tab** — last N commits with color-coded insertions/deletions

![Commits tab](https://raw.githubusercontent.com/lebiraja/gitpulse/main/ss/commits.png)

## Installation

The easiest way to install GitPulse is via PyPI using `pip` or `pipx`:

```bash
pip install gitpulse-tui
```
*(We recommend using `pipx install gitpulse-tui` to install it in an isolated environment)*

### Install via npm

GitPulse is also available as an npm package. The npm package is a thin
launcher — it bootstraps an isolated Python environment and runs the same
Python application (no logic is duplicated):

```bash
npm install -g gitpulse-tui
```

The CLI command is still `gitpulse` once installed.
This requires Python 3.10+ on your system; the wrapper handles the rest.
See [npm/README.md](./npm/README.md) for details and troubleshooting.

### Install from source

If you prefer to install from source or want to contribute to the project:

```bash
git clone https://github.com/lebiraja/gitpulse.git
cd gitpulse
./install.sh
```

The installer:
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
gitpulse                           # scan the current directory (or scan.roots from config)
gitpulse --root /path/to/repos     # scan a custom directory
gitpulse --commits 20              # show 20 commits per repo (default: 10)
gitpulse --no-watch                # disable live watch mode
gitpulse --config path/to.toml     # use a custom config file
gitpulse --version                 # print version

gitpulse --update                  # upgrade to the latest release
gitpulse --check-update            # report if one exists, install nothing

# Activity digest (prints markdown, no TUI):
gitpulse digest --since 7d                 # last 7 days
gitpulse digest --since 2024-01-01         # since a date
gitpulse digest --author you@example.com   # filter by author
```

### For scripts and coding agents

Non-interactive subcommands emit machine-readable fleet state on stdout, so an
agent can answer "which of my repos have unpushed work?" in a single call:

```bash
gitpulse scan --json                     # full fleet state as one JSON document
gitpulse scan --json --dirty             # only repos with uncommitted changes
gitpulse scan --json --ahead             # only repos with unpushed commits
gitpulse scan --ndjson                   # one JSON object per line
gitpulse context                         # Markdown context pack for an LLM prompt
```

The JSON envelope carries a `schema_version`, ISO-8601 UTC timestamps
alongside raw epochs, and an `errors` array. Repos that could not be read are
marked `"status": "unreadable"` with `"readable": false` — never silently
reported as clean.

GitPulse is also importable as a library. `gitpulse.api` never imports Textual:

```python
from gitpulse.api import scan_fleet

unpushed = [r for r in scan_fleet("~/Projects") if r.ahead > 0]
```

### Teaching your agent to use it

**Claude Code** — install the bundled skill, and Claude will reach for GitPulse
on its own whenever you ask about "my repos", "what haven't I pushed", or want
a standup summary:

```bash
git clone https://github.com/lebiraja/gitpulse.git
mkdir -p ~/.claude/skills
cp -r gitpulse/skills/gitpulse ~/.claude/skills/gitpulse
```

Then just ask: *"which of my projects have uncommitted work?"*

**Any other agent** (Cursor, Codex, Aider, …) — [`AGENTS.md`](./AGENTS.md) is a
vendor-neutral description of the same CLI contract. Drop it in your project
root, or paste it into your agent's rules/system prompt.

Both documents cover the same ground: the JSON schema, how to narrow with
`--dirty` / `--ahead`, and the failure modes worth knowing — chiefly that
`"readable": false` means *unknown*, not clean, and that `ahead: 0` does not
prove a branch is pushed when it has no upstream.

### Staying up to date

```bash
gitpulse --update          # check PyPI, then upgrade in place
gitpulse --check-update    # report only — installs nothing
```

`--update` detects how GitPulse was installed and runs the right command for
that channel. It will **not** upgrade in place when doing so would break the
install — it prints the correct command instead:

| Install method | Behaviour |
|---|---|
| virtualenv | upgrades in place with `pip` |
| pipx | runs `pipx upgrade gitpulse-tui` |
| npm | prints `npm install -g gitpulse-tui@latest` |
| OS-managed Python ([PEP 668](https://peps.python.org/pep-0668/)) | prints a `pipx` command |

npm installs are deliberately excluded from self-upgrade: the wrapper pins an
exact Python package version and would silently revert a `pip` upgrade on the
next launch.

GitPulse never checks for updates on its own — no background network calls, no
telemetry. The check happens only when you ask for it.

## Features

- **Multi-repo dashboard** — Scans a directory tree and lists every local Git repo, sorted by most recent activity
- **Compact fleet sidebar** — Each repo as a single row: name, branch, change count, and status (`✓ Clean` / `● Modified` / `● Untracked`)
- **Fleet status strip** — Cross-repo counters (dirty, behind, ahead, stashes, stale branches); click one to filter the list
- **Live watch mode** — Polls the filesystem and auto-refreshes repos as they change, without blocking the UI
- **Search & filter** — Press `/` to filter repos by name instantly
- **Multi-select & bulk actions** — Select repos with `Space`, then run `fetch` / `pull` / `push` / `gc` / `prune` / `clean` across all of them from the command palette (`:`)
- **Activity digest** — A markdown standup summary of your commits across all repos for a time window (`d`, or `--digest` on the CLI)
- **Stale-branch cleanup** — Find and bulk-delete merged / WIP / old branches across every repo (`b`)
- **Seven content tabs**:
  - **Status** — Summary cards (branch, commits, status, stashes, ahead/behind), a staged/unstaged/untracked/stash workspace, and file-tree / recent-commits / remote-summary side panels. Stage, unstage, commit and stash inline.
  - **Commits** — ASCII commit graph + last N commits with color-coded `+green` / `-red` diff stats
  - **Diff** — Per-file picker with syntax-highlighted staged & unstaged changes
  - **Branches** — All local branches; switch, create, or delete
  - **Remotes** — Remote URLs with ahead/behind sync status; fetch / pull / push
  - **Tags** — Recent tags with date and tagger info
  - **Tree** — File hierarchy of all tracked files, with file preview

## Keybindings

Press `?` inside the app for the full cheat sheet.

| Key | Action |
|-----|--------|
| `↑` / `↓` or `j` / `k` | Navigate the repo list |
| `[` / `]` | Previous / next tab |
| `/` | Search / filter repos |
| `Space` / `*` | Toggle multi-select / select all |
| `r` | Refresh — rescan all repos |
| `w` | Toggle watch mode |
| `d` | Activity digest |
| `:` | Bulk action palette |
| `b` | Stale-branch cleanup |
| `e` | Error log |
| `?` | Help |
| `q` | Quit |
| `s` / `u` / `a` | Stage / unstage / stage-all (Status tab) |
| `c` | Commit staged changes |
| `n` | New branch |
| `z` / `Z` | Create / pop stash |
| `Enter` | Switch branch · view commit diff · preview file |
| `f` / `p` / `P` | Fetch / pull / push (Remotes tab) |

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
