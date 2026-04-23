# UI Components

This document describes every Textual widget used in GitPulse, their composition, messages they emit, and how to extend them.

---

## Overview

### Custom widgets

| Widget | File | Role |
|--------|------|------|
| `RepoSidebar` | `ui/sidebar.py` | Left panel — title + search + repo list |
| `RepoListItem` | `ui/sidebar.py` | One row in the sidebar per repo |
| `MainPanel` | `ui/tabs.py` | Right panel — TabbedContent host (7 tabs) |
| `BranchListItem` | `ui/tabs.py` | One row in the Branches tab |
| `DiffFileItem` | `ui/tabs.py` | One row in the Diff tab file picker |
| `StatusFileItem` | `ui/tabs.py` | One interactive row in the Status tab |

### Modal screens

| Screen | File | Purpose |
|--------|------|---------|
| `CommitModal` | `ui/tabs.py` | Stage summary + commit message input |
| `NewBranchModal` | `ui/tabs.py` | New branch name input |
| `CommitDiffModal` | `ui/tabs.py` | Read-only scrollable diff for one commit |

Standard Textual widgets used directly: `Header`, `Footer`, `Horizontal`, `Vertical`, `ScrollableContainer`, `TabbedContent`, `TabPane`, `ListView`, `ListItem`, `Static`, `DataTable`, `Input`, `Button`.

---

## `RepoListItem` (`ui/sidebar.py`)

**Inherits:** `textual.widgets.ListItem`

### Purpose
Represents a single repository in the sidebar's scrollable list. Displays:
- **Line 1:** Bold repo name + colour-coded status badge with file count
- **Line 2:** Branch icon + branch name + relative time + 7-week sparkline

### Why a single `Static`?
Textual's layout engine has known issues with nested container widgets (`Horizontal`, `Grid`) inside `ListItem`. Using a **single `Static` with Rich markup** is the reliable approach. All formatting is done via Rich's markup syntax within one string.

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

### Selection behaviour
Selection is driven by Textual's `ListView.Highlighted` event, not `ListView.Selected`. Navigating with arrow keys immediately triggers the main panel to update — no need to press Enter.

---

## `RepoSidebar` (`ui/sidebar.py`)

**Inherits:** `textual.widgets.Static`

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
    query: str
```
Posted on every keystroke in the search input. Received by `GitPulseApp.on_repo_sidebar_search_changed()`.

### Methods

#### `populate(repos)`
Clears the `ListView` and rebuilds it from `repos`. Automatically moves focus to the first item.

#### `update_header(scanning, count=0)`
Updates the title bar. Shows `scanning…` text while the background scan is running, otherwise shows the repo count.

#### `focus_search()`
Moves keyboard focus to the search `Input`. Called by `GitPulseApp.action_search()` via the `/` key.

---

## `MainPanel` (`ui/tabs.py`)

**Inherits:** `textual.widgets.Widget`

### Purpose
The right panel. Hosts a `TabbedContent` with **seven** `TabPane` children. Tabs are loaded lazily — only the active tab is populated on repo switch; other tabs load on first visit.

### Composition
```
MainPanel
└── TabbedContent
    ├── TabPane "📋 Status"
    │     ├── Static (id="status-summary")       ← Rich Panel header
    │     ├── ListView (id="status-file-list")   ← StatusFileItem rows
    │     └── Static (id="status-hints")         ← Key hint bar
    ├── TabPane "📝 Commits"
    │     ├── DataTable (id="commits-table")
    │     └── Static (id="commits-hints")
    ├── TabPane "🔀 Diff"
    │     ├── Horizontal (id="diff-layout")
    │     │     ├── Vertical (id="diff-file-panel")
    │     │     │     ├── Static (id="diff-file-header")
    │     │     │     └── ListView (id="diff-file-list")   ← DiffFileItem rows
    │     │     └── ScrollableContainer (id="diff-view-panel")
    │     │           └── Static (id="diff-content")       ← Syntax diff
    │     └── Static (id="diff-footer")
    ├── TabPane "🌿 Branches"
    │     ├── ListView (id="branch-list")                  ← BranchListItem rows
    │     └── Static (id="branch-hints")
    ├── TabPane "🌐 Remotes"
    │     └── ScrollableContainer (id="remotes-scroll")
    │           └── Static (id="remotes-content")
    ├── TabPane "🏷️ Tags"
    │     └── DataTable (id="tags-table")
    └── TabPane "🌲 Tree"
          └── ScrollableContainer (id="tree-scroll")
                └── Static (id="tree-content")
```

### Key Bindings (active when MainPanel has focus)

| Key | Action |
|-----|--------|
| `s` | Stage highlighted file (Status tab) |
| `u` | Unstage highlighted file (Status tab) |
| `a` | Stage all changes |
| `Shift+U` | Unstage all |
| `c` | Open commit modal |
| `n` | Open new branch modal |

### Messages Emitted

#### `MainPanel.BranchSwitchRequested`
```python
class BranchSwitchRequested(Message):
    branch_name: str
```
Posted when the user presses Enter on a `BranchListItem`. Received by `GitPulseApp.on_main_panel_branch_switch_requested()` which calls `git_ops.switch_branch()` and rescans.

#### `MainPanel.ReloadRequested`
```python
class ReloadRequested(Message):
    pass
```
Posted after a successful commit, branch create, or branch delete. Received by `GitPulseApp.on_main_panel_reload_requested()` which triggers a background rescan to update the sidebar.

### Methods

#### `load_repo(repo_path, repo_info=None)`
Main entry point. Clears `_loaded_tabs` and loads only the currently active tab. Other tabs will load on demand.

#### `_load_tab(tab_id)` / `_reload_tab(tab_id)`
`_load_tab` is a no-op if the tab is already in `_loaded_tabs`. `_reload_tab` forcibly clears the cache entry and reloads.

#### `_load_status(repo_path, info)`
Populates the Status summary panel and `StatusFileItem` list view:
1. Rich `Panel` header (name, path, branch, last commit, stats, stash count)
2. Section headers (`── Staged (N) ──` etc.) as plain `ListItem` separators
3. `StatusFileItem` for each file, colour-coded by stage state

#### `_load_commits(repo_path)`
Refills `#commits-table` with columns: `Hash`, `Author`, `Date`, `Message`, `Files`, `+/-`.

#### `_load_diff(repo_path)`
Populates the file picker (`#diff-file-list`) from `get_changed_files()`. The diff viewer (`#diff-content`) is populated on demand as the user navigates the file list.

#### `_load_branches(repo_path)`
Refills `#branch-list` with `BranchListItem` entries.

#### `_load_remotes(repo_path)`
Updates `#remotes-content` with each remote's name, URL, and `↑ahead ↓behind` sync status.

#### `_load_tags(repo_path)`
Refills `#tags-table` with columns: `Tag`, `Date`, `Tagger`, `Message`.

#### `_load_tree(repo_path)`
Renders the Rich `Tree` from `get_file_tree()` into `#tree-content` inside a `ScrollableContainer`.

#### `_show_file_diff(item)`
Called on `ListView.Highlighted` in the Diff tab. Fetches `get_file_diff()` for the highlighted `DiffFileItem` and renders it as a `Syntax` object.

#### `_open_commit_diff()`
Reads the selected row from `#commits-table`, fetches `get_commit_diff()`, and pushes `CommitDiffModal` onto the screen stack.

---

## `StatusFileItem` (`ui/tabs.py`)

**Inherits:** `textual.widgets.ListItem`

### Purpose
One interactive file row in the Status tab's `ListView`. Shows the file path with icon and colour-coded stage state.

### Constructor
```python
StatusFileItem(filepath: str, status: str)
# status: "staged" | "unstaged" | "untracked"
```

### Colours
| Status | Icon | Colour |
|--------|------|--------|
| `staged` | ✅ | `#9ece6a` (green) |
| `unstaged` | ✏️ | `#e0af68` (amber) |
| `untracked` | ❓ | `#f7768e` (red) |

### Interaction
`MainPanel.action_stage_file()` / `action_unstage_file()` query `file_list.highlighted_child` and act on the selected `StatusFileItem`.

---

## `DiffFileItem` (`ui/tabs.py`)

**Inherits:** `textual.widgets.ListItem`

### Purpose
One file entry in the Diff tab's file picker. Shows `+` for staged, `~` for unstaged, `?` for untracked.

### Constructor
```python
DiffFileItem(filepath: str, status: str)
# status: "staged" | "unstaged" | "untracked"
```

### Real-time preview
`MainPanel.on_list_view_highlighted()` listens for navigation events on `#diff-file-list` and immediately calls `_show_file_diff(item)` to update the right-side diff viewer.

---

## `BranchListItem` (`ui/tabs.py`)

**Inherits:** `textual.widgets.ListItem`

### Constructor
```python
BranchListItem(branch_info: BranchInfo)
```

Current branch: bold green with `●` marker and `(current)` label.  
Other branches: plain `#a9b1d6` with `  ` indent.

### Interaction
- **Enter** → posts `MainPanel.BranchSwitchRequested`
- **`d` key** → `_delete_selected_branch()` — guards against deleting the current branch

---

## Modal Screens

### `CommitModal` (`ui/tabs.py`)

**Inherits:** `textual.screen.ModalScreen`

Displayed when the user presses `c`. Shows:
1. Number of staged files and their names (up to 4 + "N more")
2. A text `Input` for the commit message
3. **Commit** / **Cancel** buttons

`dismiss(message)` is called with the typed message string (or `None` on cancel). The caller (async callback in `action_open_commit`) then calls `git_ops.commit_changes()`.

**Close:** `Esc`, cancel button, or `Enter` to submit.

---

### `NewBranchModal` (`ui/tabs.py`)

**Inherits:** `textual.screen.ModalScreen`

Displayed when the user presses `n`. Single text input for the branch name.

`dismiss(name)` is called with the branch name (or `None` on cancel). `git_ops.create_branch()` is called in the async callback.

---

### `CommitDiffModal` (`ui/tabs.py`)

**Inherits:** `textual.screen.ModalScreen`

Full-screen diff viewer for a single commit. Contains:
- Title bar showing `short_hash — commit message`
- `ScrollableContainer` wrapping `Syntax(diff, "diff", theme="monokai", line_numbers=True)`
- Footer showing line count + key hints

**Close:** `Esc` or `q`.

---

## Adding a New Tab

1. Add a new `TabPane` to `MainPanel.compose()`:
   ```python
   with TabPane("🆕 MyTab", id="tab-mytab"):
       with ScrollableContainer(id="mytab-scroll"):
           yield Static("", id="mytab-content")
   ```

2. Register the loader in `__init__`:
   ```python
   self._tab_loaders["tab-mytab"] = "_load_mytab"
   ```

3. Write the loader method:
   ```python
   def _load_mytab(self, repo_path: Path) -> None:
       content = self.query_one("#mytab-content", Static)
       content.update(...)
   ```

4. Update `_load_tab()` signature handling if the method needs `repo_info` (like `_load_status` does).

5. Add any required git data function in `git_ops.py`.

6. Add styles in `ui/styles.tcss` if needed.

7. Update `docs/ui_components.md` and `docs/api_reference.md`.

---

## Adding a New Modal Screen

1. Create a class inheriting `ModalScreen`:
   ```python
   class MyModal(ModalScreen):
       def compose(self) -> ComposeResult:
           with Container(id="my-dialog"):
               yield Input(id="my-input")
               yield Button("OK", id="btn-ok")

       def on_button_pressed(self, event: Button.Pressed) -> None:
           if event.button.id == "btn-ok":
               value = self.query_one("#my-input", Input).value
               self.dismiss(value)
   ```

2. Push it from `MainPanel` with a callback:
   ```python
   async def _after_modal(result: str | None) -> None:
       if result:
           # use result
           pass
   self.app.push_screen(MyModal(), _after_modal)
   ```

3. Add a `BINDINGS` entry or `on_key` handler to trigger it.

---

## Adding a New Sidebar Action

1. Add a `Message` subclass in `RepoSidebar`.
2. Listen for the relevant Textual event (e.g. `on_key`, `on_button_pressed`).
3. Post your message with `self.post_message(...)`.
4. Handle it in `GitPulseApp` with `on_<widget_classname_snake>_<message_classname_snake>()`.
