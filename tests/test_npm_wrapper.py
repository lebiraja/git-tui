"""
Guards on the npm launcher's output discipline.

The wrapper bootstraps its Python venv lazily, which means the bootstrap can
run *mid-command* the first time after an npm upgrade (npm blocks postinstall
scripts by default). If that progress output goes to stdout it corrupts
`gitpulse scan --json`, whose documented contract is that stdout carries only
JSON.

These are static checks rather than a node test suite: the repo has no npm test
harness, and the property worth protecting is simply "never write progress to
stdout".
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

NPM_LIB = Path(__file__).resolve().parent.parent / "npm" / "lib"
NPM_BIN = Path(__file__).resolve().parent.parent / "npm" / "bin"
NPM_SCRIPTS = Path(__file__).resolve().parent.parent / "npm" / "scripts"


def _js_sources() -> list[Path]:
    files = list(NPM_LIB.glob("*.js")) + list(NPM_BIN.glob("*.js"))
    files += list(NPM_SCRIPTS.glob("*.js"))
    return [f for f in files if f.is_file()]


@pytest.mark.skipif(not NPM_LIB.is_dir(), reason="npm wrapper not present")
class TestWrapperWritesProgressToStderr:
    def test_no_js_file_writes_to_stdout(self):
        """Progress must go to stderr so piped JSON stays parseable."""
        offenders = []
        for path in _js_sources():
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                if "process.stdout.write" in line:
                    offenders.append(f"{path.name}:{lineno}")

        assert not offenders, (
            "npm wrapper writes to stdout at "
            + ", ".join(offenders)
            + " — this corrupts `gitpulse scan --json`. Use process.stderr."
        )

    def test_install_log_helper_targets_stderr(self):
        # Arrange
        source = (NPM_LIB / "install.js").read_text()

        # Act — locate the log() helper body
        match = re.search(r"function log\(line\) \{(.*?)\}", source, re.S)

        # Assert
        assert match, "install.js no longer defines a log() helper"
        assert "process.stderr.write" in match.group(1)

    def test_bootstrap_explains_itself(self):
        """A silent wall of install output mid-command is not acceptable UX."""
        # Arrange
        source = (NPM_LIB / "install.js").read_text()

        # Assert
        assert "postinstall" in source, (
            "install.js should explain that npm blocked the postinstall step "
            "when it bootstraps mid-command"
        )
