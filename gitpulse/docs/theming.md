# Theming

GitPulse uses a custom **Tokyo Night**-inspired dark colour palette applied entirely through Textual CSS (`ui/styles.tcss`). This document explains the colour system, how the layout is built, and how to customise the appearance.

---

## Colour Palette

All colours are defined inline in `styles.tcss`. There is no central token file — use find-and-replace to change a colour globally.

| Role | Hex | Used For |
|------|-----|----------|
| **bg-deep** | `#16161e` | Sidebar background, DataTable even rows |
| **bg-base** | `#1a1b26` | Main panel background, TabPane background |
| **bg-surface** | `#1e2030` | Header, Footer, Tabs bar, DataTable header, sidebar title |
| **bg-highlight** | `#24283b` | Tab hover, focused footer key background |
| **bg-selection** | `#283457` | Highlighted ListView item, DataTable cursor row |
| **bg-hover** | `#1f2335` | Hovered list item |
| **text-primary** | `#c0caf5` | Default text, repo names |
| **text-muted** | `#a9b1d6` | Footer descriptions, branch names |
| **text-dim** | `#565f89` | Inactive tabs, dim timestamps, borders |
| **accent-blue** | `#7aa2f7` | Section headers, active tab, sidebar title, DataTable headers |
| **accent-purple** | `#bb9af7` | Branch names in sidebar |
| **accent-green** | `#9ece6a` | CLEAN badge background, staged file sections, current branch |
| **accent-amber** | `#e0af68` | MODIFIED badge background, unstaged file sections |
| **accent-red** | `#f7768e` | Untracked file sections |
| **badge-bg-modified** | `#e0af68` | MODIFIED badge text-on-bg |
| **badge-bg-untracked** | `#db4b4b` | UNTRACKED badge (darker red) |
| **badge-bg-clean** | `#2d7d46` | CLEAN badge (darker green) |
| **accent-cyan** | `#7dcfff` | Stash section headers |
| **border** | `#3b4261` | Panel borders, DataTable dividers |
| **border-section** | `#24283b` | List item bottom borders |

---

## Layout System

The app uses a two-column `Horizontal` layout:

```
Screen (background: #1a1b26)
└── Header (height: 1, docked top)
└── Horizontal (#app-grid, height: 1fr)
    ├── RepoSidebar (#sidebar-container, width: 36)
    └── MainPanel (#main-panel, width: 1fr)
└── Footer (docked bottom)
```

### Sidebar width

The sidebar is fixed at `width: 36` (characters). Adjust in `styles.tcss`:

```css
#sidebar-container {
    width: 36;      /* Change this */
    min-width: 30;  /* Minimum allowed */
    max-width: 50;  /* Maximum allowed */
}
```

### Main panel height stack

```
MainPanel (#main-panel, height: 1fr)
└── TabbedContent (height: 1fr)
    └── ContentSwitcher (height: 1fr)
        └── TabPane (height: 1fr, padding: 1 2)
            └── Widget (DataTable / Static / ListView, height: 1fr)
```

Every level must carry `height: 1fr` or Textual will collapse the pane to zero height. If adding a new tab, make sure the inner widget also has `height: 1fr`.

---

## Key CSS Selectors

### Status badge colours

Badges are rendered as Rich markup strings in Python (see `sidebar.py: _make_badge()`), not via CSS. To change badge colours, edit the markup strings in `_make_badge()`.

### ListView item highlight

```css
#repo-list:focus > RepoListItem.--highlight {
    background: #283457;
}
```

The `.--highlight` pseudo-class is added by Textual's `ListView` to the currently focused item. The `:focus` scoping on the parent means the highlight only appears when the list has keyboard focus.

### DataTable rows

```css
DataTable > .datatable--header { background: #1e2030; }
DataTable > .datatable--cursor { background: #283457; }
DataTable > .datatable--even-row { background: #1a1b26; }
DataTable > .datatable--odd-row  { background: #1e2030; }
```

### Tab active state

```css
Tab.-active {
    color: #7aa2f7;
    background: #1a1b26;
    text-style: bold;
}
Underline {
    color: #7aa2f7;  /* The animated underline indicator */
}
```

---

## Switching to a Different Theme

To switch to a different colour scheme, replace the hex values in `styles.tcss`. Here are the key groups to update:

1. **Backgrounds** — `#16161e`, `#1a1b26`, `#1e2030`, `#24283b`, `#283457`, `#1f2335`
2. **Text** — `#c0caf5`, `#a9b1d6`, `#565f89`
3. **Accent / blue** — `#7aa2f7`
4. **Green** — `#9ece6a`, `#2d7d46`
5. **Amber** — `#e0af68`
6. **Red** — `#f7768e`, `#db4b4b`
7. **Purple** — `#bb9af7`
8. **Cyan** — `#7dcfff`
9. **Borders** — `#3b4261`, `#24283b`

**Example: Dracula theme swap** — replace `#7aa2f7` (accent blue) with `#bd93f9` (Dracula purple), `#9ece6a` with `#50fa7b` (Dracula green), etc.

---

## Rich Markup in Python

Status headers, badge text, file section borders, and branch list labels are rendered using **Rich markup** inside `Static` widgets (not via TCSS). Rich markup syntax:

```python
"[bold #7aa2f7]Title[/]"         # Bold coloured text
"[dim italic]placeholder[/]"      # Dim italic
"[bold white on #2d7d46] CLEAN [/]"  # White text on green background
```

To change the appearance of these elements, edit the markup strings in `ui/sidebar.py` (`_make_badge`) and `ui/tabs.py` (`_load_status`, `_load_remotes`, etc.).

---

## Diff Syntax Highlighting

The Diff tab and CommitDiffModal use `rich.syntax.Syntax` with `theme="monokai"`. To change the theme:

```python
# In ui/tabs.py, _show_file_diff() and CommitDiffModal.compose():
Syntax(diff_text, "diff", theme="monokai", ...)  # ← Change "monokai"
```

Popular alternatives: `"github-dark"`, `"dracula"`, `"one-dark"`, `"solarized-dark"`. Run `python3 -c "from rich.syntax import Syntax; print(list(Syntax.THEMES)[:10])"` for the full list.

---

## New Layout Selectors (v1.2+)

### Status tab file list

```css
StatusFileItem {
    height: 1;
    padding: 0 1;
    background: #1a1b26;
}
StatusFileItem:hover { background: #1f2335; }
#status-file-list:focus > StatusFileItem.--highlight { background: #283457; }
```

### Diff tab split layout

The Diff tab uses a two-panel horizontal layout:

```
#diff-layout (Horizontal, height: 1fr)
├── #diff-file-panel (Vertical, width: 30)   ← file picker
└── #diff-view-panel (ScrollableContainer)   ← syntax diff
```

Key selectors:
```css
#diff-file-panel {
    width: 30;         /* file picker column width */
    border-right: vkey #3b4261;
}

DiffFileItem {
    height: 1;
    padding: 0 1;
}
DiffFileItem:hover { background: #1f2335; }
#diff-file-list:focus > DiffFileItem.--highlight { background: #283457; }

#diff-view-panel {
    width: 1fr;
    overflow-y: auto;
    overflow-x: auto;
}
```

### Modal dialogs

Modal dialogs define their own `DEFAULT_CSS`. The container elements use these selectors:

```css
/* CommitModal */
#commit-dialog { width: 64; background: #1e2030; border: thick #7aa2f7; }

/* NewBranchModal */
#new-branch-dialog { width: 52; background: #1e2030; border: thick #bb9af7; }

/* CommitDiffModal */
#cdiff-frame { width: 92%; height: 88%; background: #1e2030; border: thick #7aa2f7; }
#cdiff-scroll { width: 100%; height: 1fr; }
```

To change modal border colours, edit the `border:` values inside the respective `DEFAULT_CSS` class attributes in `ui/tabs.py`.

### Hint bars

All tab-bottom hint bars share the same selectors:
```css
#status-hints,
#commits-hints,
#branch-hints,
#diff-footer {
    height: 1;
    dock: bottom;
    background: #1e2030;
    color: #565f89;
    padding: 0 1;
    border-top: solid #3b4261;
}
```

### Scroll containers (Tree, Remotes)

Tree and Remotes tabs use `ScrollableContainer` so all content is accessible regardless of terminal height:

```css
#tree-scroll, #remotes-scroll {
    width: 100%;
    height: 1fr;
    background: #1a1b26;
    padding: 1 2;
}
```

The inner `Static` widgets (`#tree-content`, `#remotes-content`) use `height: auto` to expand to their content rather than being clipped.
