"""
main.py — The GitPulse Textual application.

Defines GitPulseApp, the root TUI. Argument parsing and the non-interactive
subcommands live in gitpulse.cli; this module is imported only when the TUI is
actually launched.

Scanning runs in a background worker thread so the UI stays responsive.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Input, ListView
from textual.containers import Horizontal, Vertical
from textual.worker import Worker, WorkerState

from . import config as _config
from . import watcher as _watcher
from .git_ops import (
    RepoInfo, classify_error, get_repo_info, is_dirty, stash_create,
    switch_branch,
)
from .parallel import run_parallel
from .scanner import scan_repos
from .ui.bulk_results import BulkResultsScreen
from .ui.command_palette import CommandPaletteModal
from .ui.confirm_modal import ConfirmModal, DirtyTreeModal
from .ui.digest_screen import DigestScreen
from .ui.error_log import ErrorLogScreen
from .ui.fleet_status import FleetStatus
from .ui.header import AppHeader, TAB_IDS
from .ui.help_modal import HelpModal
from .ui.sidebar import RepoSidebar
from .ui.stale_screen import StaleScreen
from .ui.tabs import MainPanel


class GitPulseApp(App):
    """
    GitPulse — A developer-focused Git repository dashboard TUI.

    Scans a root directory for all local git repos and displays live
    status, recent commits, diffs, and branch management.
    Repos are sorted by most recent commit (most active first).
    """

    CSS_PATH = str(Path(__file__).parent / "ui" / "styles.tcss")

    TITLE = "GitPulse"
    SUB_TITLE = "Git Repo Dashboard"

    # Every binding carries a stable `id` so users can remap it from
    # config.toml ([keymap] section). IDs are API — renaming one breaks
    # a user's keymap, so treat them as fixed once released.
    BINDINGS = [
        Binding("q", "quit", "Quit", id="app.quit", show=True),
        Binding("r", "refresh", "Refresh", id="app.refresh", show=True),
        Binding("w", "toggle_watch", "Watch", id="app.toggle_watch", show=True),
        Binding("d", "open_digest", "Digest", id="app.digest", show=True),
        Binding("colon", "open_palette", "Actions", id="app.palette", show=True),
        Binding("b", "open_stale", "Stale", id="app.stale", show=True),
        Binding("P", "push_all", "Push all", id="app.push_all", show=True),
        Binding("e", "open_error_log", "Errors", id="app.error_log", show=True),
        Binding("slash", "search", "Search", id="app.search", show=True),
        Binding("escape", "clear_search", "Clear", id="app.clear_search", show=False),
        Binding("tab", "focus_next", "Next", id="app.focus_next", show=False),
        Binding("shift+tab", "focus_previous", "Prev", id="app.focus_prev", show=False),
        Binding("right_square_bracket", "next_tab", "Next Tab", id="app.next_tab", show=False),
        Binding("left_square_bracket", "prev_tab", "Prev Tab", id="app.prev_tab", show=False),
        Binding("j", "cursor_down", "Down", id="app.cursor_down", show=False),
        Binding("k", "cursor_up", "Up", id="app.cursor_up", show=False),
        Binding("question_mark", "open_help", "Help", id="app.help", show=True),
    ]

    def __init__(
        self,
        root_dir: Path,
        commits: int = 10,
        watch: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.root_dir = root_dir
        self.commits = commits          # How many commits to show in Commits tab
        self.repos: list[RepoInfo] = []
        self._all_repos: list[RepoInfo] = []  # Unfiltered master list
        self._selected_repo: RepoInfo | None = None
        self._scanning = False          # Guard against concurrent scans
        self._watch_enabled = watch     # Whether watch mode is on
        self._watch_paused = False      # Toggled by 'w' key
        self._signatures: dict = {}     # path → (HEAD mtime, index mtime, refs mtime, packed-refs mtime)
        self._fleet_category: str = ""  # Active fleet-filter category ("" = none)
        self._error_log: list[str] = []  # Ring buffer of raw error details (cap 50)
        self._bulk_in_flight: int = 0    # Count of active bulk/git workers (for indicator)
        self._scan_errors: list[str] = []  # Per-repo scan failures, drained on the main thread

    # -----------------------------------------------------------------
    # Layout
    # -----------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield AppHeader(id="app-header")
        with Horizontal(id="app-grid"):
            with Vertical(id="sidebar-column"):
                yield FleetStatus(id="fleet-status")
                yield RepoSidebar(id="sidebar-container")
            yield MainPanel(id="main-panel", commits=self.commits)
        yield Footer()

    # -----------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------

    def on_mount(self) -> None:
        """Initial scan on startup; start watch-mode interval if enabled."""
        self._start_scan()
        if self._watch_enabled:
            cfg = _config.get()
            self.set_interval(cfg.watch.interval_seconds, self._tick_watch)
            self.sub_title = "watch: ● live"
        else:
            self.sub_title = "watch: off"
        # Focus the repo list so global letter bindings (w/d/b/r) work
        # without keystrokes being captured by the search Input.
        try:
            self.set_focus(self.query_one("#repo-list"))
        except Exception:
            pass

    # -----------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------

    def action_refresh(self) -> None:
        """Rescan all repositories (bound to 'r')."""
        if self._scanning:
            self.notify("Scan already in progress…", timeout=2)
            return
        self._start_scan()
        self.notify("Scanning repositories… ⚡", timeout=2)

    def action_open_digest(self) -> None:
        """Open the activity digest modal (bound to 'd')."""
        cfg = _config.get()
        self.push_screen(DigestScreen(
            repos=self._all_repos,
            author_patterns=cfg.author.emails or [],
            default_window=cfg.digest.default_window,
        ))

    def action_open_stale(self) -> None:
        """Open stale-branch cleanup modal (bound to 'b')."""
        cfg = _config.get()
        self.push_screen(StaleScreen(
            repo_paths=[r.path for r in self._all_repos],
            stale_weeks=cfg.stale.weeks,
            default_branches=cfg.stale.default_branches,
            max_workers=cfg.bulk.max_workers,
        ))

    def action_open_palette(self) -> None:
        """Open the bulk-action command palette (bound to ':')."""
        sidebar: RepoSidebar = self.query_one("#sidebar-container", RepoSidebar)
        sel_count = len(sidebar.selected_repos())

        async def _after_palette(result: tuple | None) -> None:
            if result is None:
                return
            action_key, scope = result
            if scope == "selected":
                target_repos = sidebar.selected_repos()
            elif scope == "all":
                target_repos = list(self._all_repos)
            else:
                target_repos = [self._selected_repo] if self._selected_repo else []

            if not target_repos:
                self.notify("No repos to act on", timeout=2)
                return

            destructive = action_key in ("push", "pull", "gc", "clean", "prune")
            if destructive:
                names = ", ".join(r.name for r in target_repos[:5])
                extra = f" +{len(target_repos) - 5} more" if len(target_repos) > 5 else ""
                async def _after_confirm(ok: bool | None) -> None:
                    if ok:
                        self._dispatch_bulk(action_key, target_repos)
                self.push_screen(
                    ConfirmModal(
                        title=f"Run '{action_key}' on {len(target_repos)} repo(s)?",
                        body=f"[bold #8b5cf6]{names}[/]{extra}",
                        danger=action_key in ("push", "clean"),
                    ),
                    _after_confirm,
                )
            else:
                self._dispatch_bulk(action_key, target_repos)

        self.push_screen(CommandPaletteModal(selected_count=sel_count), _after_palette)

    def _dispatch_bulk(self, action_key: str, repos: list) -> None:
        """Fan out a bulk git operation over repos using a thread pool worker."""
        from .git_ops import (
            git_clean_dry, git_fetch, git_gc, git_pull, git_push,
            git_remote_prune,
        )

        _ops = {
            "fetch":   lambda r: git_fetch(r.path),
            "pull":    lambda r: git_pull(r.path),
            "push":    lambda r: git_push(r.path),
            "gc":      lambda r: git_gc(r.path),
            "prune":   lambda r: git_remote_prune(r.path),
            "clean":   lambda r: git_clean_dry(r.path),
            "refresh": lambda r: get_repo_info(r.path),
        }
        op = _ops.get(action_key)
        if op is None:
            self.notify(f"Unknown action: {action_key}", severity="error", timeout=3)
            return

        cfg = _config.get()
        results_screen = BulkResultsScreen(action=action_key, total=len(repos))
        self.push_screen(results_screen)

        def _worker() -> None:
            def _progress(completed, total, repo, result):
                self.call_from_thread(results_screen.append_row, repo, result)
                if isinstance(result, Exception):
                    _, detail = classify_error(result)
                    self.call_from_thread(
                        self._record_error, f"{action_key} · {repo.name}: {detail}"
                    )

            run_parallel(op, repos, max_workers=cfg.bulk.max_workers, on_progress=_progress)
            # After bulk refresh, trigger a rescan to update sidebar
            if action_key in ("pull", "refresh"):
                self.call_from_thread(self._start_scan)

        self._bulk_in_flight += 1
        self._update_busy_indicator()
        self.run_worker(_worker, thread=True, group="bulk", exclusive=False)

    def _update_busy_indicator(self) -> None:
        """Reflect active workers in the sub-title so the user has feedback."""
        watch_part = "watch: ● live" if (self._watch_enabled and not self._watch_paused) else (
            "watch: ○ paused" if self._watch_enabled else "watch: off"
        )
        if self._bulk_in_flight > 0:
            self.sub_title = f"⚙ working ({self._bulk_in_flight})  ·  {watch_part}"
        else:
            self.sub_title = watch_part

    def action_toggle_watch(self) -> None:
        """Pause / resume watch mode (bound to 'w')."""
        self._watch_paused = not self._watch_paused
        sidebar: RepoSidebar = self.query_one("#sidebar-container", RepoSidebar)
        if self._watch_paused:
            sidebar.update_header(scanning=False, count=len(self._all_repos), live=False)
            self.sub_title = "watch: ○ paused"
            self.notify("⏸  Watch mode PAUSED — press w to resume", severity="warning", timeout=4)
        else:
            sidebar.update_header(scanning=False, count=len(self._all_repos), live=True)
            self.sub_title = "watch: ● live"
            self.notify("▶  Watch mode RESUMED — auto-refresh on", severity="information", timeout=3)

    def action_search(self) -> None:
        """Focus the search input (bound to '/')."""
        sidebar: RepoSidebar = self.query_one("#sidebar-container", RepoSidebar)
        sidebar.focus_search()

    def action_next_tab(self) -> None:
        """Switch to the next content tab (bound to ']')."""
        self._cycle_tab(1)

    def action_prev_tab(self) -> None:
        """Switch to the previous content tab (bound to '[')."""
        self._cycle_tab(-1)

    def _cycle_tab(self, delta: int) -> None:
        main: MainPanel = self.query_one("#main-panel", MainPanel)
        current = main._active_tab()
        try:
            idx = TAB_IDS.index(current)
        except ValueError:
            idx = 0
        self._switch_tab(TAB_IDS[(idx + delta) % len(TAB_IDS)])

    def _switch_tab(self, tab_id: str) -> None:
        """Switch the active content tab and sync the header highlight."""
        header: AppHeader = self.query_one("#app-header", AppHeader)
        header.set_active(tab_id)
        main: MainPanel = self.query_one("#main-panel", MainPanel)
        main.show_tab(tab_id)

    def on_app_header_tab_changed(self, message: AppHeader.TabChanged) -> None:
        """User clicked a tab in the header."""
        self._switch_tab(message.tab_id)

    def action_push_all(self) -> None:
        """Shift+P — push every repo currently visible in the sidebar (after confirm)."""
        targets = list(self.repos) if self.repos else list(self._all_repos)
        if not targets:
            self.notify("No repos to push", timeout=2)
            return
        names = ", ".join(r.name for r in targets[:5])
        extra = f" +{len(targets) - 5} more" if len(targets) > 5 else ""
        async def _after(ok: bool | None) -> None:
            if ok:
                self._dispatch_bulk("push", targets)
        self.push_screen(
            ConfirmModal(
                title=f"Push {len(targets)} repo(s)?",
                body=f"[bold #8b5cf6]{names}[/]{extra}",
                danger=True,
            ),
            _after,
        )

    def action_open_help(self) -> None:
        """Show the keyboard-shortcut cheat sheet (bound to '?')."""
        self.push_screen(HelpModal())

    def action_clear_search(self) -> None:
        """Clear search and refocus repo list."""
        inp = self.query_one("#search-input", Input)
        inp.value = ""
        self.query_one("#repo-list").focus()

    def action_open_error_log(self) -> None:
        """Show recorded error details (bound to 'e')."""
        self.push_screen(ErrorLogScreen(self._error_log))

    def _move_cursor(self, delta: int) -> None:
        """Move the repo-list highlight by *delta* rows (vim j/k)."""
        lv = self.query_one("#repo-list", ListView)
        if not lv.children:
            return
        current = lv.index if lv.index is not None else 0
        lv.index = max(0, min(current + delta, len(lv.children) - 1))

    def action_cursor_down(self) -> None:
        """Move down one repo (vim 'j')."""
        self._move_cursor(1)

    def action_cursor_up(self) -> None:
        """Move up one repo (vim 'k')."""
        self._move_cursor(-1)

    # -----------------------------------------------------------------
    # Background scan worker
    # -----------------------------------------------------------------

    def _start_scan(self) -> None:
        """Launch the repository scan in a background worker thread."""
        self._scanning = True
        try:
            sidebar: RepoSidebar = self.query_one("#sidebar-container", RepoSidebar)
            sidebar.update_header(scanning=True)
        except Exception:
            pass
        self.run_worker(self._scan_worker, thread=True, exclusive=True, group="scan")

    def _scan_worker(self) -> list[RepoInfo]:
        """Worker function: scan filesystem and collect RepoInfo objects.

        Runs in a thread — no UI calls allowed here.
        Returns the sorted list of RepoInfo for the main thread to consume.
        """
        cfg = _config.get()
        extra_skip = set(cfg.scan.exclude_dirs) if cfg.scan.exclude_dirs else None
        paths = scan_repos(self.root_dir, extra_skip=extra_skip)

        # get_repo_info() spawns ~7 git subprocesses per repo, so enriching a
        # fleet serially dominates scan time. Fan out over a bounded pool;
        # run_parallel captures per-item exceptions so one unreadable repo
        # can't fail the whole scan.
        results = run_parallel(get_repo_info, paths, max_workers=cfg.bulk.max_workers)

        infos: list[RepoInfo] = []
        for path, result in results:
            if isinstance(result, Exception):
                _, detail = classify_error(result)
                self._scan_errors.append(f"{path}: {detail}")
            else:
                infos.append(result)

        infos.sort(key=lambda r: r.last_commit_ts, reverse=True)
        return infos

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Called on the main thread when the worker finishes."""
        group = getattr(event.worker, "group", None)
        if event.state in (WorkerState.SUCCESS, WorkerState.ERROR, WorkerState.CANCELLED):
            if group == "bulk" and self._bulk_in_flight > 0:
                self._bulk_in_flight -= 1
                self._update_busy_indicator()
        if event.state == WorkerState.SUCCESS and event.worker.result is not None:

            if group == "watch":
                # Single-repo refresh from watch tick
                updated: RepoInfo = event.worker.result
                self._refresh_single_repo(updated)
                return

            if group == "branch_switch":
                # Result is (switch_message, updated_RepoInfo)
                switch_msg, updated_info = event.worker.result
                self.notify(switch_msg, timeout=3)
                self._refresh_single_repo(updated_info)
                return

            if group not in (None, "scan"):
                # Unknown group (e.g. git_op owned by MainPanel) — ignore here.
                return

            # Full scan result
            self._scanning = False
            infos: list[RepoInfo] = event.worker.result
            self._all_repos = infos
            self.repos = list(infos)

            # Drain per-repo scan failures collected in the worker thread.
            if self._scan_errors:
                failed = len(self._scan_errors)
                for detail in self._scan_errors:
                    self._record_error(detail)
                self._scan_errors.clear()
                self.notify(
                    f"{failed} repo{'s' if failed != 1 else ''} could not be read — press e",
                    severity="warning",
                    timeout=5,
                )

            # Snapshot signatures for watch mode
            self._signatures = _watcher.snapshot(infos)

            # Determine which repo to keep highlighted across the rescan.
            keep_path = self._selected_repo.path if self._selected_repo else None
            keep = None
            if keep_path is not None:
                for r in self.repos:
                    if r.path == keep_path:
                        keep = r
                        break

            sidebar: RepoSidebar = self.query_one("#sidebar-container", RepoSidebar)
            live = self._watch_enabled and not self._watch_paused
            sidebar.update_header(scanning=False, count=len(infos), live=live)
            sidebar.populate(self.repos, keep_path=keep.path if keep else None)

            fleet: FleetStatus = self.query_one("#fleet-status", FleetStatus)
            fleet.update_counters(infos)

            if keep is not None:
                # Refresh in-memory ref + subtitle without forcing a full tab
                # reload (the user's tabs already have current data).
                self._selected_repo = keep
                self.sub_title = f"{keep.name}  ·  {keep.branch}"
            elif self.repos:
                self._select_repo(self.repos[0])

        elif event.state == WorkerState.ERROR:
            self._scanning = False
            hint, detail = classify_error(event.worker.error)
            self.notify(f"Scan failed: {hint}", severity="error", timeout=6)
            self._record_error(detail)

    def _record_error(self, detail: str) -> None:
        """Append a raw error detail to the in-app ring buffer (cap 50)."""
        if not detail:
            return
        self._error_log.append(detail)
        if len(self._error_log) > 50:
            del self._error_log[0 : len(self._error_log) - 50]

    def _tick_watch(self) -> None:
        """Called on a timer interval — check for changed repos and re-enrich them."""
        if self._watch_paused or not self._all_repos:
            return
        changed = _watcher.changed_repos(self._all_repos, self._signatures)
        for repo in changed:
            # Update signature immediately to avoid re-triggering before worker completes
            self._signatures[repo.path] = _watcher.repo_signature(repo.path)
            path = repo.path
            self.run_worker(
                lambda p=path: get_repo_info(p),
                thread=True,
                group="watch",
                exclusive=False,
            )

    def _refresh_single_repo(self, updated: RepoInfo) -> None:
        """Apply a single watch-refresh result without re-populating the whole list."""
        # Update master list in place
        for i, r in enumerate(self._all_repos):
            if r.path == updated.path:
                self._all_repos[i] = updated
                break
        else:
            self._all_repos.append(updated)

        # Re-sort by activity
        self._all_repos.sort(key=lambda r: r.last_commit_ts, reverse=True)
        self.repos = list(self._all_repos)

        sidebar: RepoSidebar = self.query_one("#sidebar-container", RepoSidebar)
        sidebar.populate(self.repos)

        fleet: FleetStatus = self.query_one("#fleet-status", FleetStatus)
        fleet.update_counters(self._all_repos)

        # If the updated repo is selected, refresh the main panel too
        if self._selected_repo and self._selected_repo.path == updated.path:
            self._selected_repo = updated
            main: MainPanel = self.query_one("#main-panel", MainPanel)
            main.load_repo(updated.path, updated)

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _select_repo(self, repo_info: RepoInfo) -> None:
        """Load a repo's data into the main panel."""
        self._selected_repo = repo_info
        # Update header subtitle to reflect the active repo + branch
        self.sub_title = f"{repo_info.name}  ·  {repo_info.branch}"
        main: MainPanel = self.query_one("#main-panel", MainPanel)
        main.load_repo(repo_info.path, repo_info)

    def _repopulate_preserving_selection(self) -> None:
        """Refresh the sidebar from ``self.repos``, keeping the current repo selected.

        The active repo only changes when it has been filtered out of view; a
        narrowing filter must not yank the user away from what they're reading
        (each re-select also re-triggers the main panel's tab loaders).
        """
        keep = self._selected_repo.path if self._selected_repo else None
        still_visible = keep is not None and any(r.path == keep for r in self.repos)

        sidebar: RepoSidebar = self.query_one("#sidebar-container", RepoSidebar)
        sidebar.populate(self.repos, keep_path=keep if still_visible else None)

        if not still_visible and self.repos:
            self._select_repo(self.repos[0])

    def _apply_filter(self, query: str) -> None:
        """Filter the repo list by name, preserving any active fleet filter."""
        q = query.strip().lower()
        base = self._fleet_filtered_repos()
        self.repos = [r for r in base if q in r.name.lower()] if q else list(base)
        self._repopulate_preserving_selection()

    def _fleet_filtered_repos(self) -> list[RepoInfo]:
        """Return _all_repos filtered by the current fleet category (if any)."""
        from .git_ops import RepoStatus
        _predicates = {
            "dirty":   lambda r: r.status != RepoStatus.CLEAN,
            "behind":  lambda r: r.behind > 0,
            "ahead":   lambda r: r.ahead > 0,
            "stashes": lambda r: r.stash_count > 0,
            "stale":   lambda r: r.has_stale_branches,
        }
        pred = _predicates.get(self._fleet_category)
        if pred is None:
            return list(self._all_repos)
        return [r for r in self._all_repos if pred(r)]

    def _apply_fleet_filter(self, category: str) -> None:
        """Filter sidebar to repos matching a fleet-status category and highlight chip."""
        self._fleet_category = category
        self.repos = self._fleet_filtered_repos()
        self._repopulate_preserving_selection()

        fleet: FleetStatus = self.query_one("#fleet-status", FleetStatus)
        fleet.set_active_filter(category)

    # -----------------------------------------------------------------
    # Message handlers
    # -----------------------------------------------------------------

    def on_repo_sidebar_repo_selected(self, message: RepoSidebar.RepoSelected) -> None:
        """User navigated to a different repo in the sidebar."""
        self._select_repo(message.repo_info)

    def on_repo_sidebar_search_changed(self, message: RepoSidebar.SearchChanged) -> None:
        """User typed in the search bar."""
        self._apply_filter(message.query)

    def on_repo_sidebar_selection_changed(self, message: RepoSidebar.SelectionChanged) -> None:
        """Update the header when the multi-select set changes."""
        sidebar: RepoSidebar = self.query_one("#sidebar-container", RepoSidebar)
        live = self._watch_enabled and not self._watch_paused
        sidebar.update_header(scanning=False, count=len(self._all_repos), live=live)

    def on_fleet_status_filter_requested(self, message: FleetStatus.FilterRequested) -> None:
        """User clicked a fleet chip — filter sidebar to matching repos."""
        self._apply_fleet_filter(message.category)

    def on_main_panel_branch_switch_requested(
        self, message: MainPanel.BranchSwitchRequested
    ) -> None:
        """User pressed Enter on a branch — confirm always; warn if dirty."""
        if self._selected_repo is None:
            return

        path = self._selected_repo.path
        repo_name = self._selected_repo.name
        branch_name = message.branch_name
        current_branch = self._selected_repo.branch
        if branch_name == current_branch:
            self.notify(f"Already on '{branch_name}'", timeout=2)
            return

        def _run_switch(stash_first: bool = False) -> None:
            def _worker() -> tuple[str, RepoInfo]:
                pre = ""
                if stash_first:
                    pre = stash_create(path, f"gitpulse auto-stash before switch to {branch_name}") + "\n"
                msg = pre + switch_branch(path, branch_name)
                info = get_repo_info(path)
                return msg, info
            self.run_worker(_worker, thread=True, group="branch_switch", exclusive=False)

        dirty, summary = is_dirty(path)
        if dirty:
            async def _after_dirty(choice) -> None:
                if choice == "stash":
                    _run_switch(stash_first=True)
                elif choice == "force":
                    _run_switch(stash_first=False)
            self.push_screen(
                DirtyTreeModal(repo_name=repo_name, dirty_summary=summary, target_branch=branch_name),
                _after_dirty,
            )
        else:
            async def _after_confirm(ok: bool | None) -> None:
                if ok:
                    _run_switch(stash_first=False)
            self.push_screen(
                ConfirmModal(
                    title=f"Switch to '{branch_name}'?",
                    body=f"Checkout [bold #8b5cf6]{branch_name}[/] in {repo_name}?",
                ),
                _after_confirm,
            )

    def on_main_panel_reload_requested(self, message: MainPanel.ReloadRequested) -> None:
        """Fired after a commit / stash / branch op.

        Just re-enrich the active repo in the background and patch the sidebar;
        do NOT trigger a full filesystem rescan (that's what was wiping the
        user's tab state and selection).
        """
        if self._selected_repo is None:
            return
        path = self._selected_repo.path
        self.run_worker(
            lambda p=path: get_repo_info(p),
            thread=True,
            group="watch",
            exclusive=False,
        )


# -----------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------

def main() -> None:
    """Backwards-compatible shim — the CLI lives in gitpulse.cli."""
    from .cli import main as _cli_main

    _cli_main()


if __name__ == "__main__":
    main()
