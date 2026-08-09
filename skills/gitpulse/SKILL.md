---
name: gitpulse
description: Inspect the state of every local git repository under a directory in one call — which repos have uncommitted changes, unpushed commits, stashes, or stale branches. Use when the user asks about "my repos", "all my projects", "what have I not pushed", "what am I working on", "anything uncommitted", "which repos need attention", before a standup or end-of-day wrap-up, when writing a status update spanning several repos, or when a task requires knowing the state of more than one repository at once. Requires the `gitpulse` CLI (pip install gitpulse-tui).
---

# GitPulse — fleet-wide git state

`git status` answers for one repo. GitPulse answers for all of them at once, as
JSON, in a single call.

## Check availability first

```bash
gitpulse --version
```

If this fails, GitPulse is not installed. Tell the user:
`pip install gitpulse-tui` (or `pipx install gitpulse-tui`). Do not attempt to
install it yourself unless asked.

## The one command that matters

```bash
gitpulse scan --root ~/Projects --json
```

Emits a single JSON document on stdout and nothing else — safe to pipe straight
into a parser.

### Narrowing

```bash
gitpulse scan --root ~/Projects --json --dirty    # uncommitted changes only
gitpulse scan --root ~/Projects --json --ahead    # unpushed commits only
gitpulse scan --root ~/Projects --ndjson          # one object per line
gitpulse scan --root ~/Projects --json --indent 0 # compact, fewer tokens
```

Prefer `--dirty` / `--ahead` over scanning everything and filtering yourself —
it is the same cost to run and far fewer tokens to read back.

Use `--indent 0` whenever you are only going to parse the output. Reserve
indented JSON for when the user will read it directly.

## Response shape

```json
{
  "schema_version": 1,
  "scanned_at": "2026-08-07T15:49:41+00:00",
  "root": "/home/lebi/Projects",
  "repo_count": 12,
  "repos": [
    {
      "name": "gitpulse",
      "path": "/home/lebi/Projects/gitpulse",
      "branch": "main",
      "status": "clean",
      "readable": true,
      "modified_count": 0,
      "ahead": 0,
      "behind": 0,
      "stash_count": 0,
      "has_stale_branches": false,
      "last_commit": {
        "ts": 1754553600,
        "iso": "2026-08-07T08:00:00+00:00",
        "message": "chore: bump version to 1.2.15"
      },
      "total_commits": 142,
      "contributor_count": 3
    }
  ],
  "errors": []
}
```

`status` is one of `clean`, `modified`, `untracked`, `unreadable`.

`commit_activity` (omitted above) is commits per week for the last 7 weeks,
oldest first.

### Read `readable` before you conclude anything

**A repo with `"readable": false` has `"status": "unreadable"` — its state is
unknown, not clean.** Never report such a repo as having nothing to do. Say its
state could not be determined, and name it.

Repos that could not be opened at all appear in the top-level `errors` array as
`{"path": ..., "error": ...}`. Check it before summarising; a non-empty
`errors` array means the picture is incomplete.

## Interpreting the fields

| Question | Field |
|---|---|
| Uncommitted work? | `status != "clean"`, or `modified_count > 0` |
| Unpushed commits? | `ahead > 0` |
| Needs a pull? | `behind > 0` |
| Both, i.e. diverged? | `ahead > 0 && behind > 0` |
| Forgotten work in progress? | `stash_count > 0` |
| Branch cleanup available? | `has_stale_branches` |
| Recently active? | `last_commit.ts`, sorted descending by default |

Repos come back sorted most-recently-committed first.

`ahead`/`behind` are `0` when a branch has no upstream — that is not the same as
being in sync. If it matters, say so rather than implying the repo is pushed.

## When the user wants prose, not data

```bash
gitpulse context --root ~/Projects
```

Markdown built for a context window: repos needing attention first, an unpushed
work table, stale branches, and clean repos collapsed to a single name list.
Use this when you are about to summarise the fleet for a human anyway — it is
cheaper than fetching JSON and rewriting it. Cap it with `--max-repos N` on a
large fleet.

For "what did I do this week", use the author digest instead:

```bash
gitpulse digest --since 7d
gitpulse digest --since 7d --author you@example.com
```

`--since` accepts `1d`, `7d`, `2w`, `4h`, `yesterday`, `today`, or `YYYY-MM-DD`.

## Python API

When already in Python, skip the subprocess. `gitpulse.api` is read-only and
never imports Textual:

```python
from gitpulse.api import scan_fleet, scan_fleet_detailed, repo_state

unpushed = [r for r in scan_fleet("~/Projects") if r.ahead > 0]

result = scan_fleet_detailed("~/Projects")   # carries .errors too
one = repo_state("~/Projects/gitpulse")
```

## Choosing a root

`--root` is optional. Without it GitPulse uses the first entry in
`scan.roots` from `~/.config/gitpulse/config.toml`, then falls back to the
current directory. Pass `--root` explicitly when the user names a directory;
omit it to respect their configured default.

Scanning `~` directly is slow and noisy. Ask which directory they mean rather
than guessing, unless a config default exists.

## Cost

Each repo costs roughly seven git subprocesses, run in parallel. A few dozen
repos is fast; several hundred is not. Scan once and reuse the result within a
task rather than re-running per question. Tune with `--max-workers N`.

## Scope

Every command here is **read-only**. GitPulse's mutating operations (commit,
push, branch delete, bulk fetch) are deliberately not exposed to this skill —
use `git` directly for those, so the write stays visible and scoped to one repo.

Exit codes: `0` success, `1` bad root or bad `--since` spec. A dirty fleet is
still exit `0` — check the data, not the exit code.
