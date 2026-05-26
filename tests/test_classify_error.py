"""
Tests for classify_error() in gitpulse/git_ops.py

Covers:
- TimeoutError → actionable timed-out message with exclude_dirs hint
- All existing error patterns still produce correct hints
- Fallback for unknown exceptions
- Accepts both exception instances and string inputs
"""

import pytest

from gitpulse.git_ops import classify_error


# ---------------------------------------------------------------------------
# Return type contract
# ---------------------------------------------------------------------------

class TestReturnContract:
    def test_always_returns_two_tuple(self):
        result = classify_error(Exception("something"))
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_both_elements_are_strings(self):
        hint, detail = classify_error(Exception("something"))
        assert isinstance(hint, str)
        assert isinstance(detail, str)

    def test_accepts_string_input(self):
        hint, detail = classify_error("some error string")
        assert isinstance(hint, str)
        assert isinstance(detail, str)

    def test_never_raises(self):
        for exc in (
            Exception("generic"),
            ValueError("bad value"),
            TimeoutError(60, "timed out"),
            RuntimeError("boom"),
            "raw string",
            "",
        ):
            hint, detail = classify_error(exc)
            assert hint  # non-empty


# ---------------------------------------------------------------------------
# TimeoutError (new branch)
# ---------------------------------------------------------------------------

class TestTimeoutError:
    def test_timeout_error_returns_timed_out_hint(self):
        hint, _ = classify_error(TimeoutError(60, "Operation timed out"))
        assert "timed out" in hint.lower()

    def test_timeout_hint_mentions_network_or_cloud(self):
        hint, _ = classify_error(TimeoutError(60, "Operation timed out"))
        assert "network" in hint.lower() or "cloud" in hint.lower()

    def test_timeout_hint_mentions_exclude_dirs(self):
        hint, _ = classify_error(TimeoutError(60, "Operation timed out"))
        assert "exclude_dirs" in hint

    def test_timeout_detail_preserves_original_message(self):
        exc = TimeoutError(60, "Operation timed out")
        _, detail = classify_error(exc)
        assert detail == str(exc)

    def test_timeout_error_no_args(self):
        hint, _ = classify_error(TimeoutError())
        assert "timed out" in hint.lower()

    def test_timeout_error_with_custom_message(self):
        hint, _ = classify_error(TimeoutError("custom timeout"))
        assert "timed out" in hint.lower()


# ---------------------------------------------------------------------------
# Existing error patterns (regression tests)
# ---------------------------------------------------------------------------

class TestExistingPatterns:
    def test_permission_denied(self):
        hint, _ = classify_error(Exception("Permission denied"))
        assert "authentication" in hint.lower() or "credential" in hint.lower()

    def test_authentication_failed(self):
        hint, _ = classify_error(Exception("Authentication failed"))
        assert "authentication" in hint.lower()

    def test_push_rejected_non_fast_forward(self):
        hint, _ = classify_error(Exception("rejected: non-fast-forward"))
        assert "push" in hint.lower() or "rejected" in hint.lower()

    def test_merge_conflict(self):
        hint, _ = classify_error(Exception("merge conflict in file.txt"))
        assert "conflict" in hint.lower() or "merge" in hint.lower()

    def test_detached_head(self):
        hint, _ = classify_error(Exception("detached HEAD"))
        assert "detached" in hint.lower() or "head" in hint.lower() or "branch" in hint.lower()

    def test_index_lock(self):
        hint, _ = classify_error(Exception("index.lock exists"))
        assert "lock" in hint.lower()

    def test_network_unreachable(self):
        hint, _ = classify_error(Exception("could not resolve host: github.com"))
        assert "network" in hint.lower() or "connection" in hint.lower()

    def test_no_upstream(self):
        hint, _ = classify_error(Exception("no upstream configured"))
        assert "upstream" in hint.lower()

    def test_would_be_overwritten(self):
        hint, _ = classify_error(Exception("Your changes would be overwritten"))
        assert "overwritten" in hint.lower() or "stash" in hint.lower()

    def test_unknown_error_uses_message_as_hint(self):
        msg = "some totally unknown git error that matches nothing"
        hint, detail = classify_error(Exception(msg))
        assert msg in hint or msg in detail

    def test_detail_always_preserves_original(self):
        exc = Exception("original error text")
        _, detail = classify_error(exc)
        assert "original error text" in detail


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_string(self):
        hint, detail = classify_error("")
        assert isinstance(hint, str)

    def test_very_long_message_is_truncated_in_hint(self):
        long_msg = "x" * 500
        hint, detail = classify_error(Exception(long_msg))
        assert len(hint) <= 200  # hint should be reasonably short

    def test_timeout_is_checked_before_string_patterns(self):
        # A TimeoutError whose str() happens to contain "permission denied"
        # should still return the TimeoutError hint, not the auth hint.
        exc = TimeoutError("permission denied but actually a timeout")
        hint, _ = classify_error(exc)
        assert "timed out" in hint.lower()
