"""
context.py — Fleet state rendered as a Markdown context pack.

Distinct from ``digest.py``: the digest answers "what did I do this week",
author-filtered and commit-centric. This answers "what is the current state of
this fleet, and what is unfinished" — state-first, ordered by what needs
attention, and bounded so a large fleet cannot flood a context window.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .api import ScanResult, is_unreadable
from .git_ops import RepoInfo, RepoStatus
from .utils import relative_time


def _needs_attention(r: RepoInfo) -> bool:
    """True if the repo has uncommitted, unpushed, or stashed work."""
    if is_unreadable(r):
        return False  # reported separately; not actionable work
    return (
        r.status != RepoStatus.CLEAN
        or r.ahead > 0
        or r.behind > 0
        or r.stash_count > 0
    )


def _attention_note(r: RepoInfo) -> str:
    """Human-readable summary of why a repo needs attention."""
    bits: list[str] = []
    if r.modified_count:
        bits.append(f"{r.modified_count} uncommitted file{'s' if r.modified_count != 1 else ''}")
    if r.ahead and r.behind:
        bits.append(f"diverged ({r.ahead} ahead / {r.behind} behind)")
    elif r.ahead:
        bits.append(f"{r.ahead} unpushed commit{'s' if r.ahead != 1 else ''}")
    elif r.behind:
        bits.append(f"{r.behind} commit{'s' if r.behind != 1 else ''} behind")
    if r.stash_count:
        bits.append(f"{r.stash_count} stash{'es' if r.stash_count != 1 else ''}")
    return ", ".join(bits) if bits else "needs attention"


def render_context(result: ScanResult, max_repos: int = 40) -> str:
    """Render *result* as a Markdown context pack.

    Args:
        result: A fleet scan from ``api.scan_fleet_detailed``.
        max_repos: Cap on rows listed in the detail sections. Repos beyond the
            cap are summarised as a count rather than dropped silently.
    """
    repos = result.repos
    stamp = result.scanned_at.replace(microsecond=0).isoformat()

    lines: list[str] = [
        f"# Fleet state — {stamp}",
        "",
        f"Root: `{result.root}` · {len(repos)} repo{'s' if len(repos) != 1 else ''}",
        "",
    ]

    unreadable = [r for r in repos if is_unreadable(r)]
    readable = [r for r in repos if not is_unreadable(r)]
    attention = [r for r in readable if _needs_attention(r)]
    unpushed = [r for r in readable if r.ahead > 0]
    stale = [r for r in readable if r.has_stale_branches]
    clean = [r for r in readable if not _needs_attention(r)]

    # --- Needs attention -------------------------------------------------
    lines.append("## Needs attention")
    lines.append("")
    if not attention:
        lines.append("_Nothing outstanding — every repo is clean and in sync._")
    else:
        for r in attention[:max_repos]:
            lines.append(f"- **{r.name}** (`{r.branch}`) — {_attention_note(r)}")
        if len(attention) > max_repos:
            lines.append(f"- _… and {len(attention) - max_repos} more_")
    lines.append("")

    # --- Unpushed work ---------------------------------------------------
    if unpushed:
        lines.append("## Unpushed work")
        lines.append("")
        lines.append("| repo | branch | ahead | last commit |")
        lines.append("|---|---|---|---|")
        for r in unpushed[:max_repos]:
            msg = r.last_commit_msg.replace("|", "\\|")
            when = relative_time(r.last_commit_ts)
            lines.append(f"| {r.name} | `{r.branch}` | {r.ahead} | {when} — {msg} |")
        if len(unpushed) > max_repos:
            lines.append(f"| _… {len(unpushed) - max_repos} more_ | | | |")
        lines.append("")

    # --- Stale branches --------------------------------------------------
    if stale:
        lines.append("## Repos with stale branches")
        lines.append("")
        for r in stale[:max_repos]:
            lines.append(f"- {r.name}")
        if len(stale) > max_repos:
            lines.append(f"- _… and {len(stale) - max_repos} more_")
        lines.append("")

    # --- Clean -----------------------------------------------------------
    if clean:
        lines.append(f"## Clean and synced ({len(clean)})")
        lines.append("")
        lines.append(", ".join(r.name for r in clean))
        lines.append("")

    # --- Errors ----------------------------------------------------------
    if unreadable or result.errors:
        lines.append("## Could not be read")
        lines.append("")
        lines.append(
            "_State below is unknown, not clean — these were not inspected._"
        )
        lines.append("")
        for r in unreadable[:max_repos]:
            lines.append(f"- `{r.path}`")
        for path, err in result.errors[:max_repos]:
            lines.append(f"- `{path}` — {err}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
