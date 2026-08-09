# STATUS

Project activity log. Newest on top.

---

## [2026-08-09 16:45] — Added `gitpulse --update` self-upgrade

**What:** `--update` checks PyPI for a newer release and upgrades in place;
`--check-update` reports without installing. `gitpulse/update.py` detects the
install channel (venv / pipx / npm wrapper / OS-managed Python) and either runs
the correct command or prints it.

**Why:** Requested. The complication is that GitPulse ships through two
channels — the npm wrapper bootstraps its own venv at `~/.gitpulse/venv` and
pins an exact `gitpulse-tui==X.Y.Z`, so a pip upgrade there is silently
reverted on the next launch. PEP 668 interpreters must not be written to at
all. A blind `pip install --upgrade` would have broken both.

**State:** DONE — verified with a real 1.2.15 → 1.2.16 upgrade in a throwaway
venv; 17 new tests (191 → 208), all offline (verified with `urlopen` blocked).

**Next:** —

---

## [2026-08-07 15:40] — Fleet overhaul: UI fixes, agent surface, release safety

**What:** Single branch `feat/fleet-overhaul` closing GitHub issues #26–#37
(epics #23, #24, #25). Three strands: (1) UI/UX correctness — filter selection,
parallel scan, error log, vim keys, responsive sidebar, fleet strip clipping,
misleading empty states; (2) agent mode — `gitpulse.api` (Textual-free library
surface), `gitpulse scan --json/--ndjson`, `gitpulse context` Markdown pack,
subcommand CLI in `gitpulse/cli.py`; (3) packaging — PyPI metadata, dependency
ceilings, a CI test gate, and 78 new tests.

**Why:** Competitive research showed every local-git MCP server is pinned to a
single repository and returns text rather than JSON — "which of my 40 repos have
unpushed work?" was unanswerable in one call, despite GitPulse already computing
it. The UI defects were real bugs found by reading `main.py` and `sidebar.py`.

**State:** DONE — 185 tests passing (was 107), TUI verified by screenshot at 95
and 150 columns.

**Next:** Merge the PR. An MCP server built on `gitpulse.api` is the natural
follow-on, deliberately left out of scope until the library surface settles.

---

## [2026-08-07 15:40] — Removed dual-import blocks from every module

**What:** Replaced the `try: from gitpulse.x / except ImportError: from x`
pattern in 12 modules with relative imports. Split `main.py` into `main.py`
(the Textual app) and `cli.py` (argument parsing + subcommands). Console script
now points at `gitpulse.cli:main`.

**Why:** The fallback branch mutated `sys.path` at import time, which makes
`import gitpulse` unsafe inside another process — a blocker for the library API.
It also meant every new module had to be added in two places.

**State:** DONE

**Next:** — (breaking change noted in the PR: `python gitpulse/main.py` no
longer works; use `python -m gitpulse`)

---

## [2026-08-07 15:40] — CI now gates publishing on tests

**What:** Added a `test` job (Python 3.10–3.13 matrix) that `build-and-publish`
depends on. Added `ci.yml` for pull requests and `latest-deps.yml` as a weekly
canary against unpinned upstream releases.

**Why:** `publish.yml` was the only workflow in the repo and had no test step —
every push to main published to PyPI *and* npm with 107 tests that had never
gated a release. The 3.10 matrix entry matters because `config.py` branches
between the `tomli` backport and stdlib `tomllib`, a path CI never exercised.

**State:** DONE

**Next:** —
