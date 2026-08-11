"""
Portability guards on install.sh / uninstall.sh.

These scripts run on the user's machine before anything Python does, so a
GNU-only construct is a hard install failure on macOS with no fallback path.
Reported in issue #43.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = [ROOT / "install.sh", ROOT / "uninstall.sh"]


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
class TestShellPortability:
    def test_script_exists(self, script):
        assert script.is_file()

    def test_no_gnu_only_sed_in_place(self, script):
        """`sed -i <script>` is GNU-only; BSD/macOS needs a backup suffix."""
        offenders = []
        for lineno, line in enumerate(script.read_text().splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue  # commentary explaining the pitfall is fine
            # Match `sed -i` NOT followed by a quoted backup suffix.
            if re.search(r"\bsed\s+-i(?!\s*(''|\"\"))", stripped):
                offenders.append(f"{script.name}:{lineno}: {stripped}")

        assert not offenders, (
            "GNU-only `sed -i` found; fails on macOS with 'invalid command "
            "code':\n  " + "\n  ".join(offenders)
        )

    def test_syntax_is_valid(self, script):
        result = subprocess.run(
            ["bash", "-n", str(script)], capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr

    def test_no_gnu_only_readlink_f(self, script):
        """`readlink -f` is absent on stock macOS (needs coreutils)."""
        offenders = [
            f"{script.name}:{n}: {ln.strip()}"
            for n, ln in enumerate(script.read_text().splitlines(), 1)
            if re.search(r"\breadlink\s+-f\b", ln) and not ln.strip().startswith("#")
        ]
        assert not offenders, "readlink -f is unavailable on stock macOS:\n  " + "\n  ".join(offenders)

    def test_no_gnu_only_grep_flags(self, script):
        """`grep -P` (PCRE) is not compiled into BSD grep."""
        offenders = [
            f"{script.name}:{n}"
            for n, ln in enumerate(script.read_text().splitlines(), 1)
            if re.search(r"\bgrep\s+(-\w*P|--perl-regexp)", ln)
            and not ln.strip().startswith("#")
        ]
        assert not offenders, f"grep -P is GNU-only: {offenders}"

    def test_venv_bin_dir_is_not_hardcoded(self, script):
        """Windows venvs use Scripts/, not bin/ — detect, do not assume."""
        text = script.read_text()
        if "$VENV/bin" not in text:
            return  # nothing hardcoded
        assert "Scripts" in text, (
            "hardcodes $VENV/bin without a Windows Scripts/ fallback"
        )
