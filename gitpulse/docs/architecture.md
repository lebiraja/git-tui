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
│   │  │ (repos)    │  │      │ │ 🏷️  Tags           │ │   │
│   │  └────────────┘  │      │ │ 🌲 Tree           │ │   │
│   └──────────────────┘      │ └───────────────────┘ │   │
│                             └──────────────────────┘   │
│              Modals (ModalScreen stack):              │
│         CommitModal / NewBranchModal / CommitDiffModal │
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
- The **scan lifecycle** (`_start_scan`, `_scan_worker`, worker state handling)
- The **search/filter logic** (`_apply_filter`)
- **Message routing** — listens for:
  - `RepoSidebar.RepoSelected`
  - `RepoSidebar.SearchChanged`
  - `MainPanel.BranchSwitchRequested`
  - `MainPanel.ReloadRequested` _(new)_ — triggers sidebar rescan after commit/branch ops
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

   | Category | Functions |
   |---|---|
   | Read — repo summary | `get_repo_info()` |
   | Read — file status | `get_status()`, `get_changed_files()` |
   | Read — history | `get_commits()`, `get_stashes()`, `get_tags()` |
   | Read — diff | `get_diff()`, `get_file_diff()`, `get_commit_diff()` |
   | Read — refs | `get_branches()`, `get_remotes()` |
   | Read — tree | `get_file_tree()` |
   | **Write** — staging | `stage_files()`, `unstage_files()`, `stage_all()`, `unstage_all()` |
   | **Write** — committing | `commit_changes()` |
   | **Write** — branches | `switch_branch()`, `create_branch()`, `delete_branch()` |

---

### `ui/sidebar.py` — Left Panel

Composes:
- A title `Static`
- A search `Input` widget
- A `ListView` of `RepoListItem` entries

Each `RepoListItem` uses a **single `Static` with Rich markup** for the two-line display (name + badge on line 1, branch + relative time on line 2).

Emits two messages:
- `RepoSidebar.RepoSelected` — on arrow-key navigation
- `RepoSidebar.SearchChanged` — on each keystroke in the search box

---

### `ui/tabs.py` — Right Panel + Modal Screens

Composes a `TabbedContent` with **seven** `TabPane` children. Each pane is populated independently by a `_load_*` method (lazy: first visit per repo only). Emits:
- `MainPanel.BranchSwitchRequested` — Enter on a branch
- `MainPanel.ReloadRequested` — after a successful commit or branch create/delete

Also defines three **modal screens** pushed via `app.push_screen()`:
- `CommitModal` — stage summary + commit message input
- `NewBranchModal` — new branch name input
- `CommitDiffModal` — read-only scrollable diff viewer for a single commit

---

### `ui/styles.tcss` — Theme

All visual styling. Uses a Tokyo Night-inspired dark palette. See [theming.md](./theming.md) for full colour reference.

---

## Data Flow

### Startup

```
on_mount()
  └── _start_scan()
        └── run_worker(_scan_worker, thread=True)
              ├── scanner.scan_repos(root)          → list[Path]
              └── git_ops.get_repo_info(path) × N   → list[RepoInfo]

on_worker_state_changed(SUCCESS)
  ├── sidebar.populate(repos)
  └── _select_repo(repos[0])
        └── main_panel.load_repo(path, info)
              ├── _load_status()    (active tab only; others lazy)
              ├── _load_commits()
              ├── _load_diff()
              ├── _load_branches()
              ├── _load_remotes()
              ├── _load_tags()
              └── _load_tree()
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
                          └── _start_scan()
```

### Commit Flow

```
User presses 'c'
  └── MainPanel.action_open_commit()
        └── app.push_screen(CommitModal(staged_files), callback)
              └── User types message, presses Enter
                    └── CommitModal.dismiss(message)
                          └── callback(message)
                                ├── git_ops.commit_changes(path, message)
                                ├── app.notify(result)
                                ├── _reload_tab(tab-status/commits/diff)
                                └── post MainPanel.ReloadRequested()
                                      └── GitPulseApp.on_main_panel_reload_requested()
                                            └── _start_scan()  (updates sidebar)
```

### Create / Delete Branch

```
User presses 'n'
  └── MainPanel.action_new_branch()
        └── app.push_screen(NewBranchModal(), callback)
              └── User types name, presses Enter
                    └── git_ops.create_branch(path, name)
                          └── _reload_tab(tab-branches) + ReloadRequested

User presses 'd' in Branches tab
  └── MainPanel.on_key() → _delete_selected_branch()
        ├── git_ops.delete_branch(path, name)
        └── _reload_tab(tab-branches) + ReloadRequested
```

### View Commit Diff

```
User presses Enter or 'd' in Commits tab
  └── MainPanel._open_commit_diff()
        ├── git_ops.get_commit_diff(path, short_hash)
        └── app.push_screen(CommitDiffModal(hash, msg, diff_text))
```

---

## Error Handling Strategy

All `git_ops` functions use try/except broadly and return safe defaults (empty lists, empty strings, human-readable error messages) rather than raising. This means:
- A corrupt or inaccessible repo won’t crash the app
- Mutations (commit, branch ops) return a descriptive error string displayed via `app.notify()`
- Exceptions are silently swallowed in read paths — add `from textual import log; log(exc)` if debugging is needed
