# UI Components

This document describes each Textual widget used in GitPulse, their composition, messages they emit, and how to extend them.

---

## Overview

GitPulse uses the following Textual widgets:

| Widget | File | Role |
|--------|------|------|
| `RepoSidebar` | `ui/sidebar.py` | Left panel — title + search + repo list |
| `RepoListItem` | `ui/sidebar.py` | One row in the sidebar per repo |
| `MainPanel` | `ui/tabs.py` | Right panel — TabbedContent host |
| `BranchListItem` | `ui/tabs.py` | One row in the Branches tab |

Standard Textual widgets used directly: `Header`, `Footer`, `Horizontal`, `TabbedContent`, `TabPane`, `ListView`, `ListItem`, `Static`, `DataTable`, `Input`.

---

## `RepoListItem` (`ui/sidebar.py`)

**Inherits:** `textual.widgets.ListItem`

### Purpose
Represents a single repository in the sidebar's scrollable list. Displays:
- **Line 1:** Bold repo name + colour-coded status badge with file count
- **Line 2:** Branch icon + branch name + relative time

### Why a single `Static`?
Textual's layout engine has known issues with nested container widgets (`Horizontal`, `Grid`) inside `ListItem`. Using a **single `Static` with Rich markup** is the reliable, battle-tested approach. All formatting is done via Rich's markup syntax within one string.

### Constructor
```python
RepoListItem(repo_info: RepoInfo)
```

### Badge generation — `_make_badge(info)`

```python
def _make_badge(info: RepoInfo) -> str
```

Returns a Rich markup string based on `info.status` and `info.modified_count`:

| Status | Badge text | Background |
|--------|-----------|------------|
| `CLEAN` | `✓ CLEAN` | `#2d7d46` (green) |
| `MODIFIED` | `✎ MODIFIED (N)` | `#e0af68` (amber) |
| `UNTRACKED` | `? UNTRACKED (N)` | `#db4b4b` (red) |

The `(N)` count is omitted when `modified_count == 0`.

### Selecting a repo
Selection is driven by Textual's `ListView.Highlighted` event, not `ListView.Selected`. This means navigating with arrow keys immediately triggers the main panel to update — no need to press Enter.

---

## `RepoSidebar` (`ui/sidebar.py`)

**Inherits:** `textual.widgets.Static`

### Purpose
The left panel container. Manages the title header, search input, and the `ListView`.

### Composition
```
RepoSidebar
├── Static (id="sidebar-title")    ← "⚡ GitPulse" header
├── Input  (id="search-input")     ← Filter repos...
└── ListView (id="repo-list")      ← Scrollable list of RepoListItem
```

### Messages Emitted

#### `RepoSidebar.RepoSelected`
```python
class RepoSelected(Message):
    repo_info: RepoInfo
```
Posted when the user highlights a different list item. Received by `GitPulseApp.on_repo_sidebar_repo_selected()`.

#### `RepoSidebar.SearchChanged`
```python
class SearchChanged(Message):
    query: str  # current text in the search box
```
Posted on every keystroke in the search input. Received by `GitPulseApp.on_repo_sidebar_search_changed()`.

### Methods

#### `populate(repos)`
```python
def populate(self, repos: list[RepoInfo]) -> None
```
Clears the `ListView` and rebuilds it from `repos`. Automatically moves focus to the first item.

#### `focus_search()`
```python
def focus_search(self) -> None
```
Moves keyboard focus to the search `Input`. Called by `GitPulseApp.action_search()` when the user presses `/`.

---

## `MainPanel` (`ui/tabs.py`)

**Inherits:** `textual.widgets.Static`

### Purpose
The right panel. Hosts a `TabbedContent` with six `TabPane` children.

### Composition
```
MainPanel
└── TabbedContent
    ├── TabPane "📋 Status"   → Static (id="status-content")
    ├── TabPane "📝 Commits"  → DataTable (id="commits-table")
    ├── TabPane "🔀 Diff"     → Static (id="diff-content")
    ├── TabPane "🌿 Branches" → ListView (id="branch-list")
    ├── TabPane "🌐 Remotes"  → Static (id="remotes-content")
    └── TabPane "🏷️ Tags"     → DataTable (id="tags-table")
```

### Messages Emitted

#### `MainPanel.BranchSwitchRequested`
```python
class BranchSwitchRequested(Message):
    branch_name: str
```
Posted when the user presses Enter (`ListView.Selected`) on a `BranchListItem` in the Branches tab. Received by `GitPulseApp.on_main_panel_branch_switch_requested()`.

### Methods

#### `load_repo(repo_path, repo_info=None)`
```python
def load_repo(self, repo_path: Path, repo_info: RepoInfo | None = None) -> None
```
The main entry point. Calls all six `_load_*` methods sequentially to populate every tab.

#### `_load_status(repo_path, info)` 
Populates `#status-content`. Renders:
1. Repo summary header (name, path, branch, last commit, commit count, contributors)
2. Staged files section (box-drawn borders, green colour)
3. Unstaged files section (amber)
4. Untracked files section (red)
5. Stash list (cyan)

#### `_load_commits(repo_path)`
Clears and refills `#commits-table` with columns: `Hash`, `Author`, `Date`, `Message`, `Files`, `+/-`.

#### `_load_diff(repo_path)`
Updates `#diff-content`. For repos with changes, renders a `rich.syntax.Syntax` object with `theme="monokai"` and line numbers.

#### `_load_branches(repo_path)`
Refills `#branch-list` with `BranchListItem` entries.

#### `_load_remotes(repo_path)`
Updates `#remotes-content` with each remote's name, URL, and `↑ahead ↓behind` sync status.

#### `_load_tags(repo_path)`
Clears and refills `#tags-table` with columns: `Tag`, `Date`, `Tagger`, `Message`.

---

## `BranchListItem` (`ui/tabs.py`)

**Inherits:** `textual.widgets.ListItem`

### Purpose
One row in the Branches tab. Current branch shown in green with a `●` marker and `(current)` label; other branches shown in plain text with `  ` indent.

### Constructor
```python
BranchListItem(branch_info: BranchInfo)
```

### Interaction
When the user presses Enter, `MainPanel.on_list_view_selected()` catches the `ListView.Selected` event, confirms the item is a `BranchListItem`, and posts `MainPanel.BranchSwitchRequested`.

---

## Adding a New Tab

1. Add a new `TabPane` to `MainPanel.compose()`:
   ```python
   with TabPane("🆕 MyTab", id="tab-mytab"):
       yield DataTable(id="my-table")  # or Static, ListView, etc.
   ```

2. If using a `DataTable`, set up columns in `on_mount()`:
   ```python
   my_table: DataTable = self.query_one("#my-table", DataTable)
   my_table.add_columns("Col1", "Col2")
   ```

3. Add a `_load_mytab(repo_path)` method and call it from `load_repo()`.

4. Add the corresponding data function in `git_ops.py` and a data class if needed.

5. Update `ui/styles.tcss` if the tab needs custom styling.

---

## Adding a New Sidebar Action

1. Add a `Message` subclass in `RepoSidebar`.
2. Listen for the relevant Textual event (e.g. `on_key`, `on_button_pressed`).
3. Post your message with `self.post_message(...)`.
4. Handle it in `GitPulseApp` with a method named `on_<widget_classname_snake>_<message_classname_snake>()`.
