# FIXES

Running bug log. Newest on top.

---

## 2026-08-07 — Stale `Highlighted` event clobbers restored selection

**Symptom:** After filtering, the correct repo stayed selected for one frame and
then silently reverted to the first row.

**Root cause:** `RepoSidebar.populate()` calls `ListView.clear()` and re-appends
rows. Those mutations queue `Highlighted` events that are delivered *after*
`populate()` returns, carrying items from the *previous* list. The late event
overwrote the selection `populate()` had just restored. Only surfaced under the
async test pilot; in manual use it looked like intermittent flicker.

**Fix:** `gitpulse/ui/sidebar.py:297` — `on_list_view_highlighted` now ignores
any event whose `repo_info.path` is not in `_current_repos`.

**Verified:** `tests/test_ui_behaviour.py::TestFilterPreservesSelection` (3
tests), stable across 3 consecutive runs.

---

## 2026-08-07 — Filter box hijacked repo selection on every keystroke

**Symptom:** Typing in the filter box jumped the main panel to a different repo
on every character typed.

**Root cause:** `_apply_filter` called `_select_repo(self.repos[0])`
unconditionally after each keystroke, and `sidebar.populate()` was called
without `keep_path`, resetting `list_view.index` to 0. Two independent resets on
the same path. Each one re-triggered the threaded tab loaders, so it also caused
redundant git work per character. `_apply_fleet_filter` had the same defect.

**Fix:** `gitpulse/main.py:511` — added `_repopulate_preserving_selection()`,
which passes `keep_path` through and only falls back to the first row when the
current selection has genuinely been filtered out. Both call sites now use it.

**Verified:** `tests/test_ui_behaviour.py::TestFilterPreservesSelection`.

---

## 2026-08-07 — Repo scan ran ~7 sequential git subprocesses per repo

**Symptom:** Startup and every `r` refresh took time proportional to repo count;
the sidebar sat on "scanning…" for seconds on a large fleet.

**Root cause:** `_scan_worker` enriched repos with a plain list comprehension
(`[get_repo_info(p) for p in paths]`). Each `get_repo_info` call shells out to
git ~7 times (`rev_list`, `shortlog`, `log`, two `iter_commits`, `stash list`,
`for_each_ref`), all strictly serialized. `parallel.run_parallel` already
existed and was used by digest/bulk/stale — just not by the main scan.

**Fix:** `gitpulse/main.py:378` — fan out via `run_parallel` using
`cfg.bulk.max_workers`. Per-repo exceptions are collected into `_scan_errors`
and drained into the error log on the main thread.

**Verified:** `tests/test_api.py::TestScanFleet`; TUI smoke test against a
3-repo fleet.

---

## 2026-08-07 — Error ring buffer was unreachable

**Symptom:** Failures showed a 2-second toast with a short hint; the detailed
error was unrecoverable.

**Root cause:** `_error_log` was allocated and maintained by `_record_error`,
but nothing ever read it — no screen, no binding. It was also only wired to
scan failures; bulk-op and branch-switch failures never reached it.

**Fix:** Added `gitpulse/ui/error_log.py` (`ErrorLogScreen`), bound to `e`.
Bulk-op failures now route through `_record_error`
(`gitpulse/main.py:230`), and scan failures report a count with a "press e"
hint. Error text renders with `markup=False` since git stderr can contain
square brackets.

**Verified:** `tests/test_ui_behaviour.py::TestErrorLog`.

---

## 2026-08-07 — Unreadable repos reported as clean in JSON output

**Symptom:** A directory containing an invalid `.git` was emitted with
`"status": "clean"`, telling a consumer there was nothing to do.

**Root cause:** `get_repo_info` catches its own exceptions and returns a
placeholder `RepoInfo` with `branch="unknown"` and no history rather than
raising. That shape is indistinguishable from a genuinely clean repo, and the
only signal (`branch == "unknown"`) was undocumented.

**Fix:** `gitpulse/api.py:142` — added `is_unreadable()`; `repo_to_dict` emits
`"status": "unreadable"` with `"readable": false`. `context.py` lists these
under "Could not be read" with an explicit "unknown, not clean" note.

**Verified:** `tests/test_api.py::TestSerialization::test_unreadable_repo_is_not_reported_as_clean`,
`tests/test_context.py::test_unreadable_repo_is_flagged_not_counted_clean`.

---

## 2026-08-07 — Fleet status chips clipped off the sidebar

**Symptom:** At narrow terminal widths only the first chip (`dirty N`) was
visible; `stale` and `all` were cut off entirely.

**Root cause:** Two compounding issues. `FleetStatus` subclassed `Widget`, and
its six `width: auto` chips plus a `fleet` label needed 42 columns against a
sidebar of ~31. Chips were silently clipped rather than wrapping or scrolling.

**Fix:** `gitpulse/ui/fleet_status.py:44` — `FleetStatus` now subclasses
`Horizontal`; dropped the redundant `fleet` label; abbreviated `behind`/`ahead`
to `↓`/`↑` and `stash`/`stale` to `stsh`/`stl`, with tooltips carrying the full
meaning. `styles.tcss` padding reduced to 0 with a 1-column chip margin.

**Verified:** `tests/test_ui_behaviour.py::TestFleetStrip` asserts all six chips
fit the strip's content area at an 95-column terminal; screenshots at 95 and
150 columns.

---

## 2026-08-07 — Status tab empty state contradicted the summary card

**Symptom:** With untracked files present, the Status card read "Untracked / 1
untracked" while the Staged pane below it said "Working tree is clean".

**Root cause:** `_empty_row` hardcoded the subtitle "Working tree is clean" for
every workspace list. An empty *Staged* list says nothing about the tree.

**Fix:** `gitpulse/ui/tabs.py:1071` — `_empty_row` takes a per-list `hint`;
each list now passes a subtitle describing only itself ("Press s on a file to
stage it", etc.).

**Verified:** Screenshot against a repo with untracked files.

---

## 2026-08-09 — npm wrapper corrupted `gitpulse scan --json`

**Symptom:** After `npm install -g gitpulse-tui@latest`, the first `gitpulse`
command printed venv bootstrap logs before its real output. Piping that run —
`gitpulse scan --json > fleet.json` — produced invalid JSON, breaking the
documented contract that stdout carries only JSON.

**Root cause:** npm blocks postinstall scripts by default now, so the Python
venv stays on the previous version. The launcher self-heals on next run, but
`log()` in `npm/lib/install.js:24` wrote progress to **stdout**, mixing it into
the command's output. Reproduced by clearing `~/.gitpulse/state.json` and
running `gitpulse scan --json` — `json.load` failed at char 0.

**Fix:** `npm/lib/install.js:23` — `log()` now writes to stderr. Added a notice
naming the version mismatch and the blocked postinstall, so a mid-command
bootstrap explains itself instead of appearing as an unexplained wall of output.
`npm/README.md` documents the "install scripts blocked" warning, including that
npm's own suggested `npm install -g --allow-scripts=gitpulse-tui` fails with
`Cannot destructure property 'name' of '.for'` when no package is named.

**Verified:** Same scenario now yields valid JSON (`repo_count 1300`) with the
explanation on stderr. `tests/test_npm_wrapper.py` guards it — confirmed the
test fails when `log()` is reverted to stdout.

---

## 2026-08-09 — install.sh alias broke when the checkout moved

**Symptom:** `gitpulse` resolved to
`/home/lebi/projects/git-tui/.venv/bin/python -m gitpulse` — a venv that no
longer existed — shadowing a working `/usr/bin/gitpulse` from npm. The shell
reported the alias, so `which gitpulse` looked fine while every invocation
failed.

**Root cause:** `install.sh:52` wrote `alias gitpulse="<abs path> -m gitpulse"`
into `.bashrc`, `.zshrc`, and `.bash_profile`. An absolute path baked into rc
files breaks silently when the repo is moved or deleted, takes precedence over
any pip/pipx/npm install, and never applied to fish at all.

**Fix:** `install.sh:48` — symlink the venv's console script into
`~/.local/bin` instead, which works in bash, zsh, and fish, and dies with the
checkout rather than outliving it. The installer also strips the old alias if
it finds one, and warns when `~/.local/bin` is not on PATH.
`uninstall.sh:46` removes the symlink, guarding with a literal `readlink` so it
only deletes a link pointing into this checkout.

**Verified:** Full install → uninstall cycle in a sandboxed `HOME`, including a
pre-seeded stale alias (removed) and a foreign `~/.local/bin/gitpulse` pointing
at `/usr/bin/gitpulse` (correctly left in place). The `readlink -f` variant was
caught failing during that test — `.venv` is deleted first, so the link is
dangling and `-f` returned empty, skipping removal.
