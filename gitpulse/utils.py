"""
utils.py — Shared utilities for GitPulse.

Contains helpers that are used across multiple modules so they don't
need to live inside domain-specific files (e.g. git_ops.py).
"""

from __future__ import annotations

from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Package version — single source of truth
# ---------------------------------------------------------------------------

__version__ = "1.2.1"


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def relative_time(ts: float) -> str:
    """Convert a Unix timestamp to a human-readable relative time string.

    Examples: "just now", "5m ago", "3h ago", "2d ago", "1w ago", "4mo ago", "2y ago"
    """
    if ts == 0:
        return "never"
    now = datetime.now(timezone.utc).timestamp()
    diff = now - ts
    if diff < 60:
        return "just now"
    elif diff < 3600:
        m = int(diff // 60)
        return f"{m}m ago"
    elif diff < 86400:
        h = int(diff // 3600)
        return f"{h}h ago"
    elif diff < 604800:
        d = int(diff // 86400)
        return f"{d}d ago"
    elif diff < 2592000:
        w = int(diff // 604800)
        return f"{w}w ago"
    elif diff < 31536000:
        mo = int(diff // 2592000)
        return f"{mo}mo ago"
    else:
        y = int(diff // 31536000)
        return f"{y}y ago"
