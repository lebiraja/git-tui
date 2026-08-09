# GitPulse for coding agents

GitPulse reports the state of **every local git repository under a directory**
in one call. `git status` answers for one repo; this answers for all of them, as
JSON.

Applies to any agent that reads this file (Claude Code, Cursor, Codex, Aider,
and others). Claude Code users can instead install the richer skill in
[`skills/gitpulse/`](./skills/gitpulse/SKILL.md).

## Install

```bash
pip install gitpulse-tui        # or: pipx install gitpulse-tui
gitpulse --version              # verify before relying on it
```

If a flag or field documented here is missing, the installed copy is old.
`gitpulse --check-update` reports whether a newer release exists and installs
nothing. Do **not** run `gitpulse --update` unless the user asks for it — it
modifies their environment.

## The command

```bash
gitpulse scan --root ~/Projects --json --indent 0
```

Only JSON goes to stdout — safe to pipe straight into a parser. Use
`--indent 0` when parsing; drop it when a human will read the output.

Narrow at the source rather than fetching everything and filtering:

```bash
gitpulse scan --json --dirty     # uncommitted changes only
gitpulse scan --json --ahead     # unpushed commits only
gitpulse scan --ndjson           # one object per line
```

## Output

```json
{
  "schema_version": 1,
  "scanned_at": "2026-08-07T15:49:41+00:00",
  "root": "/home/you/Projects",
  "repo_count": 12,
  "repos": [
    {
      "name": "gitpulse",
      "path": "/home/you/Projects/gitpulse",
      "branch": "main",
      "status": "clean",
      "readable": true,
      "modified_count": 0,
      "ahead": 0,
      "behind": 0,
      "stash_count": 0,
      "has_stale_branches": false,
      "last_commit": { "ts": 1754553600, "iso": "…", "message": "…" },
      "total_commits": 142,
      "contributor_count": 3,
      "commit_activity": [0, 1, 4, 2, 0, 7, 3]
    }
  ],
  "errors": []
}
```

`status` ∈ `clean` | `modified` | `untracked` | `unreadable`.
Repos are sorted most-recently-committed first.
`commit_activity` is commits per week for 7 weeks, oldest first.

## Rules for reading it

**`"readable": false` means unknown, not clean.** Such a repo could not be
inspected. Never report it as having nothing to do — name it and say its state
is undetermined.

**Check `errors[]` before summarising.** A non-empty array means the picture is
incomplete.

**`ahead: 0` does not prove a branch is pushed.** It is also `0` when the branch
has no upstream at all. Say so rather than implying everything is synced.

**Exit code 0 does not mean the fleet is clean.** It means the scan succeeded.
Read the data. Exit `1` means the scan itself failed (bad root, bad `--since`).

## Field reference

| Question | Field |
|---|---|
| Uncommitted work? | `status != "clean"` or `modified_count > 0` |
| Unpushed commits? | `ahead > 0` |
| Needs a pull? | `behind > 0` |
| Diverged? | `ahead > 0 && behind > 0` |
| Forgotten WIP? | `stash_count > 0` |
| Branch cleanup available? | `has_stale_branches` |

## Prose instead of data

```bash
gitpulse context                  # Markdown, action-ordered, for a prompt
gitpulse context --max-repos 15   # cap it on a large fleet
gitpulse digest --since 7d        # "what did I commit this week"
```

Use `context` when you will summarise for a human anyway — cheaper than
fetching JSON and rewriting it. Use `digest` for activity over a window;
`--since` takes `1d`, `7d`, `2w`, `4h`, `yesterday`, `today`, or `YYYY-MM-DD`.

## In-process (Python)

```python
from gitpulse.api import scan_fleet, scan_fleet_detailed, repo_state

unpushed = [r for r in scan_fleet("~/Projects") if r.ahead > 0]
result = scan_fleet_detailed("~/Projects")   # also carries .errors
one = repo_state("~/Projects/gitpulse")
```

`gitpulse.api` is read-only and never imports Textual, so it is cheap to import
into a non-TUI process.

## Choosing a root

`--root` is optional; without it GitPulse uses `scan.roots` from
`~/.config/gitpulse/config.toml`, then the current directory. Scanning `~`
directly is slow and noisy — ask which directory the user means rather than
guessing.

## Cost and scope

Each repo costs roughly seven git subprocesses, run in parallel. Scan once and
reuse the result within a task instead of re-running per question. Tune with
`--max-workers N`.

Everything documented here is **read-only**. GitPulse's mutating operations
(commit, push, branch delete, bulk fetch) are intentionally not part of this
contract — use `git` directly so writes stay explicit and scoped.
