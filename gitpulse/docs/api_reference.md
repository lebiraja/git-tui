# API Reference

Complete reference for all public data classes and functions in `git_ops.py` and `scanner.py`.

---

## `scanner.py`

### `SKIP_DIRS`

```python
SKIP_DIRS: set[str]
```

A set of directory names that are **never recursed into** during scanning. Includes:
`node_modules`, `__pycache__`, `.venv`, `venv`, `env`, `.tox`, `.mypy_cache`, `.pytest_cache`, `dist`, `build`, `.eggs`, `site-packages`.

To add additional skip directories (e.g. a custom build output dir), extend this set before calling `scan_repos()`.

---

### `scan_repos(root)`

```python
def scan_repos(root: Path) -> list[Path]
```

Recursively scan `root` for directories that contain a `.git` folder.

**Parameters:**
- `root` — The top-level directory to begin scanning from. `~` is expanded, symlinks are resolved.

**Returns:**
- A list of absolute `Path` objects pointing to each discovered repository root, **sorted alphabetically by name** (case-insensitive). Note: sort-by-date happens in `main.py`, not here.

**Behaviour:**
- Once a `.git` directory is found in a folder, recursion **stops** — sub-repositories and git submodules are not returned separately.
- Directories starting with `.` are skipped.
- `PermissionError` on any directory is silently ignored.
- Returns an empty list if `root` is not a valid directory.

**Example:**
```python
from pathlib import Path
from scanner import scan_repos

repos = scan_repos(Path("~/projects"))
for r in repos:
    print(r)  # /home/user/projects/myapp
```

---

## `git_ops.py`

### Data Classes

#### `RepoStatus`

```python
class RepoStatus(enum.Enum):
    CLEAN     = "CLEAN"      # No changes at all
    MODIFIED  = "MODIFIED"   # Has staged or unstaged changes
    UNTRACKED = "UNTRACKED"  # Only untracked files present, no staged/unstaged
```

Used as the `status` field of `RepoInfo` and drives badge colouring in the sidebar.

---

#### `RepoInfo`

```python
@dataclass
class RepoInfo:
    name: str               # Directory basename (e.g. "myapp")
    path: Path              # Absolute path to repo root
    branch: str             # Current branch name, or "(detached)"
    status: RepoStatus      # CLEAN / MODIFIED / UNTRACKED
    last_commit_ts: float   # Unix timestamp of most recent commit (0.0 if no commits)
    last_commit_msg: str    # First line of most recent commit message
    modified_count: int     # Total number of staged + unstaged + untracked files
    total_commits: int      # Total commits on current branch (capped at 500)
    contributor_count: int  # Unique author count (capped at 500 commits)
```

> **Note:** `total_commits` and `contributor_count` are capped at 500 commit traversals for performance. Repos with >500 commits will show `500+` effectively.

---

#### `FileStatus`

```python
@dataclass
class FileStatus:
    staged: list[str]     # Files in the index vs HEAD (ready to commit)
    unstaged: list[str]   # Files in working tree vs index (modified but not staged)
    untracked: list[str]  # Files not tracked by git at all
```

Each element is a relative file path string (e.g. `"src/main.py"`).

---

#### `CommitInfo`

```python
@dataclass
class CommitInfo:
    short_hash: str     # 7-character hex SHA (e.g. "ab12cd3")
    author: str         # Author name and email as string
    date: str           # Formatted: "YYYY-MM-DD HH:MM"
    message: str        # First line of commit message
    files_changed: int  # Number of files touched in this commit
    insertions: int     # Lines added
    deletions: int      # Lines removed
```

`files_changed`, `insertions`, and `deletions` come from `commit.stats.total` (equivalent to `git show --stat`). They default to 0 if the stat lookup fails.

---

#### `BranchInfo`

```python
@dataclass
class BranchInfo:
    name: str          # Branch name (e.g. "main", "feature/auth")
    is_current: bool   # True if this is the currently checked-out branch
```

---

#### `StashEntry`

```python
@dataclass
class StashEntry:
    index: int     # stash@{index} number
    message: str   # The remainder of the stash list line (e.g. "WIP on main: abc1234 msg")
```

---

#### `RemoteInfo`

```python
@dataclass
class RemoteInfo:
    name: str    # Remote name (e.g. "origin")
    url: str     # Remote URL (e.g. "https://github.com/user/repo.git")
    ahead: int   # Commits local branch is ahead of remote tracking branch
    behind: int  # Commits local branch is behind remote tracking branch
```

`ahead` and `behind` are `0` if there is no tracking branch configured, or if the operation fails.

---

#### `TagInfo`

```python
@dataclass
class TagInfo:
    name: str     # Tag name (e.g. "v1.0.0")
    date: str     # Formatted: "YYYY-MM-DD HH:MM"
    message: str  # First line of tag annotation message (or commit message for lightweight tags)
    tagger: str   # Tagger name (or commit author for lightweight tags)
```

---

### Helper Functions

#### `relative_time(ts)`

```python
def relative_time(ts: float) -> str
```

Convert a Unix timestamp to a human-readable relative string.

| Condition | Output |
|-----------|--------|
| `ts == 0` | `"never"` |
| `< 60s` | `"just now"` |
| `< 1h` | `"Xm ago"` |
| `< 1d` | `"Xh ago"` |
| `< 1w` | `"Xd ago"` |
| `< 1mo` | `"Xw ago"` |
| `< 1y` | `"Xmo ago"` |
| `≥ 1y` | `"Xy ago"` |

Used in the sidebar to show activity next to each repo.

---

### Public API Functions

#### `get_repo_info(path)`

```python
def get_repo_info(path: Path) -> RepoInfo
```

Return a full `RepoInfo` summary for one repository. This is the most expensive call — it traverses up to 500 commits to count totals and contributors.

**Parameters:**
- `path` — Absolute path to the repository root.

**Returns:** `RepoInfo`

**Error handling:** Returns a safe default `RepoInfo` (status=CLEAN, all counts=0) if the path is not a valid git repo.

---

#### `get_status(path)`

```python
def get_status(path: Path) -> FileStatus
```

Return categorised file lists for a repository.

**Returns:** `FileStatus` with three lists: `staged`, `unstaged`, `untracked`.

**Implementation detail:**
- `staged` = `repo.index.diff("HEAD")` — index vs last commit
- `unstaged` = `repo.index.diff(None)` — working tree vs index
- `untracked` = `repo.untracked_files`

---

#### `get_commits(path, n=10)`

```python
def get_commits(path: Path, n: int = 10) -> list[CommitInfo]
```

Return the last `n` commits on the current branch, most recent first.

**Parameters:**
- `path` — Repo root path.
- `n` — Max number of commits to return (default: 10).

**Returns:** `list[CommitInfo]`

**Note:** Each `CommitInfo` includes diff stats from `commit.stats.total`. This adds a small overhead per commit.

---

#### `get_diff(path)`

```python
def get_diff(path: Path) -> str
```

Return the uncommitted diff as a raw string.

**Logic:**
1. Try `git diff` (unstaged changes)
2. If empty, try `git diff --cached` (staged changes)
3. If still empty, return `"No uncommitted changes."`

**Returns:** A unified diff string, or an informational/error message.

---

#### `get_branches(path)`

```python
def get_branches(path: Path) -> list[BranchInfo]
```

Return all local branches.

**Returns:** `list[BranchInfo]`, where `is_current=True` for the active branch. In detached HEAD state, all branches have `is_current=False`.

---

#### `switch_branch(path, branch_name)`

```python
def switch_branch(path: Path, branch_name: str) -> str
```

Checkout a branch by name.

**Parameters:**
- `path` — Repo root path.
- `branch_name` — Name of the branch to switch to.

**Returns:** A human-readable result string (either success or error message).

**Note:** This is the only function in the module that **mutates** repository state. It runs `git checkout <branch_name>`.

---

#### `get_stashes(path)`

```python
def get_stashes(path: Path) -> list[StashEntry]
```

Return a list of stash entries.

**Returns:** `list[StashEntry]`, empty list if no stashes or on error.

**Implementation detail:** Parses the output of `git stash list`.

---

#### `get_remotes(path)`

```python
def get_remotes(path: Path) -> list[RemoteInfo]
```

Return all configured remotes with ahead/behind sync counts.

**Returns:** `list[RemoteInfo]`

**Ahead/behind logic:** Uses `repo.iter_commits(rev_range)` with ranges like `origin/main..main` and `main..origin/main`. Returns 0/0 if no tracking branch is configured.

---

#### `get_tags(path, n=15)`

```python
def get_tags(path: Path, n: int = 15) -> list[TagInfo]
```

Return the most recent `n` tags sorted by date descending.

**Parameters:**
- `path` — Repo root path.
- `n` — Max tags to return (default: 15).

**Returns:** `list[TagInfo]`

**Annotated vs lightweight tags:** For annotated tags, uses `tag_ref.tag` for date and message. For lightweight tags, uses the tagged commit's date and message.
