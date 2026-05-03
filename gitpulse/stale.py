"""
stale.py — Stale-branch analysis for GitPulse.

Categorises local branches across all repos into stale, merged, WIP, and
unmerged groups. Provides a quick-check used by get_repo_info() and a full
scan used by StaleScreen.
"""

from __future__ import annotations

from pathlib import Path

try:
    from gitpulse.git_ops import BranchDetail, get_branch_details
    from gitpulse.parallel import run_parallel
except ImportError:
    from git_ops import BranchDetail, get_branch_details  # type: ignore
    from parallel import run_parallel  # type: ignore


def categorize(
    branches: list[BranchDetail],
    stale_weeks: int = 8,
) -> dict[str, list[BranchDetail]]:
    """Split *branches* into named categories.

    Returns dict with keys: "all", "stale", "merged", "wip", "unmerged".
    Branches can appear in multiple categories (e.g. stale AND merged).
    """
    cutoff_days = stale_weeks * 7
    result: dict[str, list[BranchDetail]] = {
        "all":      list(branches),
        "stale":    [],
        "merged":   [],
        "wip":      [],
        "unmerged": [],
    }
    for b in branches:
        if b.is_current:
            continue  # Never flag the checked-out branch
        if b.age_days >= cutoff_days and not b.is_merged_into_default:
            result["stale"].append(b)
        if b.is_merged_into_default:
            result["merged"].append(b)
        if b.is_wip:
            result["wip"].append(b)
        if not b.is_merged_into_default and not b.is_current:
            result["unmerged"].append(b)

    return result


def count_stale_quick(
    path: Path,
    stale_weeks: int = 8,
    default_branches: list[str] | None = None,
) -> int:
    """Lightweight stale-branch count for sidebar enrichment.

    Returns the number of non-current branches older than *stale_weeks* that
    are not merged into the default branch.
    """
    details = get_branch_details(path, default_branches)
    cats = categorize(details, stale_weeks)
    return len(cats["stale"])


def gather_all_repos(
    repo_paths: list[Path],
    stale_weeks: int = 8,
    default_branches: list[str] | None = None,
    max_workers: int = 8,
) -> dict[str, list[BranchDetail]]:
    """Fan out get_branch_details across all repos and return merged categories."""
    def _fetch(path: Path) -> list[BranchDetail]:
        return get_branch_details(path, default_branches)

    results = run_parallel(_fetch, repo_paths, max_workers=max_workers)
    all_branches: list[BranchDetail] = []
    for _, res in results:
        if isinstance(res, list):
            all_branches.extend(res)

    return categorize(all_branches, stale_weeks)
