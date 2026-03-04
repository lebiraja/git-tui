# Architecture

This document explains how GitPulse is structured, how data flows through the application, and how the major components relate to each other.

---

## High-Level Overview

```
┌─────────────────────────────────────────────────────────┐
│                    GitPulseApp (main.py)                 │
│                                                         │
│   ┌──────────────────┐      ┌──────────────────────┐   │
│   │   RepoSidebar    │      │     MainPanel         │   │
│   │  (sidebar.py)    │      │     (tabs.py)         │   │
│   │                  │      │                       │   │
│   │  ┌────────────┐  │      │ ┌───────────────────┐ │   │
│   │  │ Search     │  │      │ │ 📋 Status         │ │   │
│   │  │ Input      │  │      │ │ 📝 Commits        │ │   │
│   │  └────────────┘  │      │ │ 🔀 Diff           │ │   │
│   │  ┌────────────┐  │      │ │ 🌿 Branches       │ │   │
│   │  │ ListView   │  │      │ │ 🌐 Remotes        │ │   │
│   │  │ (repos)    │  │      │ │ 🏷️  Tags          │ │   │
│   │  └────────────┘  │      │ └───────────────────┘ │   │
│   └──────────────────┘      └──────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
          │                            │
          ▼                            ▼
   scanner.py                    git_ops.py
   (discovery)              (all git operations)
          │                            │
          └──────────────┬─────────────┘
                         ▼
                  Local filesystem
                  (git repositories)
```

---

## Module Responsibilities

### `main.py` — Application Orchestrator

The root `GitPulseApp(App)` class owns:
- The **only mutable repo state** (`_all_repos`, `repos`, `_selected_repo`)
- The **scan lifecycle** (`_scan_and_populate`, refresh)
- The **search/filter logic** (`_apply_filter`)
- **Message routing** — listens for `RepoSidebar.RepoSelected`, `RepoSidebar.SearchChanged`, and `MainPanel.BranchSwitchRequested`
- **Keybindings** (`q`, `r`, `/`, `Escape`)

Neither the sidebar nor the tabs know about each other. All cross-widget communication goes through the app.

---

### `scanner.py` — Repo Discovery

Pure filesystem logic. No git library dependency.

```
scan_repos(root)
    └── _walk(dir, repos)
            ├── if .git exists → append dir, stop recursion
            └── else → recurse into non-skipped subdirs
```

Returns a list of `Path` objects. The sort-by-date step happens in `main.py` after `get_repo_info()` is called on each path.

---

### `git_ops.py` — Git Data Layer

This is the **only module that imports GitPython**. Everything else is pure Python or Textual. The module has three layers:

1. **Data classes** — pure immutable objects (dataclasses):
   `RepoInfo`, `FileStatus`, `CommitInfo`, `BranchInfo`, `StashEntry`, `RemoteInfo`, `TagInfo`

2. **Private helpers** — prefixed with `_`, not for external use:
   `_open_repo()`, `_determine_status()`

3. **Public API functions** — called by `main.py` and `tabs.py`:
   `get_repo_info()`, `get_status()`, `get_commits()`, `get_diff()`,
   `get_branches()`, `switch_branch()`, `get_stashes()`, `get_remotes()`, `get_tags()`

---

### `ui/sidebar.py` — Left Panel

Composes:
- A title `Static`
- A search `Input` widget
- A `ListView` of `RepoListItem` entries

Each `RepoListItem` uses a **single `Static` with Rich markup** for the two-line display (name + badge on line 1, branch + relative time on line 2). This is intentional — Textual's layout engine does not handle nested containers inside `ListItem` reliably.

Emits two messages:
- `RepoSidebar.RepoSelected` — on arrow-key navigation
- `RepoSidebar.SearchChanged` — on each keystroke in the search box

---

### `ui/tabs.py` — Right Panel

Composes a `TabbedContent` with six `TabPane` children. Each pane is populated independently by a `_load_*` method called from `load_repo()`. Emits:
- `MainPanel.BranchSwitchRequested` — when Enter is pressed on a `BranchListItem`

---

### `ui/styles.tcss` — Theme

All visual styling. Uses a Tokyo Night-inspired dark palette. See [theming.md](./theming.md) for full color reference.

---

## Data Flow

### Startup

```
on_mount()
  └── call_later(_scan_and_populate)
        ├── scanner.scan_repos(root)          → list[Path]
        ├── git_ops.get_repo_info(path) × N   → list[RepoInfo]
        ├── sort by last_commit_ts desc
        ├── sidebar.populate(repos)
        └── _select_repo(repos[0])
              └── main_panel.load_repo(path, info)
                    ├── _load_status()
                    ├── _load_commits()
                    ├── _load_diff()
                    ├── _load_branches()
                    ├── _load_remotes()
                    └── _load_tags()
```

### Repo Selection (arrow keys)

```
User presses ↑/↓
  └── ListView.Highlighted
        └── RepoSidebar.on_list_view_highlighted()
              └── post RepoSidebar.RepoSelected(info)
                    └── GitPulseApp.on_repo_sidebar_repo_selected()
                          └── _select_repo(info)
                                └── main_panel.load_repo(path, info)
```

### Search Filter

```
User types in search box
  └── Input.Changed
        └── RepoSidebar.on_input_changed()
              └── post RepoSidebar.SearchChanged(query)
                    └── GitPulseApp.on_repo_sidebar_search_changed()
                          └── _apply_filter(query)
                                └── sidebar.populate(filtered_repos)
```

### Branch Switch

```
User presses Enter on branch
  └── ListView.Selected
        └── MainPanel.on_list_view_selected()
              └── post MainPanel.BranchSwitchRequested(branch_name)
                    └── GitPulseApp.on_main_panel_branch_switch_requested()
                          ├── git_ops.switch_branch(path, branch)
                          ├── notify(result_message)
                          └── _scan_and_populate()
```

---

## Error Handling Strategy

All `git_ops` functions use try/except broadly and return safe defaults (empty lists, empty strings) rather than raising. This means:
- A corrupt or inaccessible repo won't crash the app
- The sidebar will still show the repo with `CLEAN` status and partial data
- Exceptions are silently swallowed — add logging if debugging is needed
