"""
Coverage for the self-update path.

Network access is always stubbed — these tests never reach PyPI, and never run
a real installer.
"""

from __future__ import annotations

from pathlib import Path
from urllib.error import URLError

import pytest

from gitpulse import update as up
from gitpulse.update import Install, is_newer, run_update


class TestVersionComparison:
    @pytest.mark.parametrize(
        "latest,current,expected",
        [
            ("1.2.16", "1.2.15", True),
            ("1.2.15", "1.2.15", False),
            ("1.2.15", "1.2.16", False),
            ("1.2.10", "1.2.9", True),      # numeric, not lexicographic
            ("1.10.0", "1.9.0", True),
            ("2.0.0", "1.9.9", True),
            ("1.3.0", "1.2.99", True),
        ],
    )
    def test_is_newer(self, latest, current, expected):
        assert is_newer(latest, current) is expected

    def test_shorter_version_is_not_newer(self):
        assert is_newer("1.2", "1.2.1") is False


class TestDetectInstall:
    def test_venv_is_upgradable_in_place(self, monkeypatch):
        # Arrange — look like a virtualenv, and not like npm/pipx
        monkeypatch.setattr(up.sys, "prefix", "/tmp/venv")
        monkeypatch.setattr(up.sys, "base_prefix", "/usr")
        monkeypatch.setattr(up, "_npm_venv_root", lambda: Path("/nonexistent"))

        # Act
        install = up.detect_install()

        # Assert
        assert install.method == up.VENV
        assert install.command is not None
        assert "--upgrade" in install.command

    def test_npm_install_refuses_to_self_upgrade(self, monkeypatch, tmp_path):
        """pip-upgrading the npm venv would be undone on the next launch."""
        # Arrange — pretend this interpreter lives in the npm-managed venv
        npm_root = tmp_path / "venv"
        npm_root.mkdir()
        monkeypatch.setattr(up, "_npm_venv_root", lambda: npm_root)
        monkeypatch.setattr(up.sys, "prefix", str(npm_root))

        # Act
        install = up.detect_install()

        # Assert
        assert install.method == up.NPM
        assert install.command is None
        assert "npm install -g gitpulse-tui@latest" in install.manual_hint

    def test_externally_managed_python_is_not_touched(self, monkeypatch, tmp_path):
        """PEP 668 marks distro Pythons where pip must not write."""
        # Arrange — not a venv, not npm, and marked externally managed
        monkeypatch.setattr(up.sys, "prefix", "/usr")
        monkeypatch.setattr(up.sys, "base_prefix", "/usr")
        monkeypatch.setattr(up, "_npm_venv_root", lambda: Path("/nonexistent"))
        (tmp_path / "EXTERNALLY-MANAGED").write_text("")
        monkeypatch.setattr(
            up.sysconfig, "get_path", lambda name: str(tmp_path)
        )

        # Act
        install = up.detect_install()

        # Assert
        assert install.method == up.SYSTEM
        assert install.command is None
        assert "pipx" in install.manual_hint


class TestRunUpdate:
    def test_reports_already_up_to_date(self, monkeypatch, capsys):
        # Arrange
        monkeypatch.setattr(up, "__version__", "1.2.16")
        monkeypatch.setattr(up, "fetch_latest_version", lambda timeout=5.0: "1.2.16")

        # Act
        code = run_update()

        # Assert
        assert code == 0
        assert "Already up to date" in capsys.readouterr().out

    def test_network_failure_exits_nonzero(self, monkeypatch, capsys):
        # Arrange
        def boom(timeout=5.0):
            raise URLError("no route to host")

        monkeypatch.setattr(up, "fetch_latest_version", boom)

        # Act
        code = run_update()

        # Assert
        assert code == 1
        assert "could not reach PyPI" in capsys.readouterr().err

    def test_check_only_never_runs_a_command(self, monkeypatch, capsys):
        # Arrange
        ran = []
        monkeypatch.setattr(up, "__version__", "1.0.0")
        monkeypatch.setattr(up, "fetch_latest_version", lambda timeout=5.0: "9.9.9")
        monkeypatch.setattr(up.subprocess, "run", lambda *a, **k: ran.append(a))

        # Act
        code = run_update(check_only=True)

        # Assert
        assert code == 0
        assert ran == []
        assert "9.9.9 is available" in capsys.readouterr().out

    def test_unsupported_channel_prints_manual_hint_only(self, monkeypatch, capsys):
        # Arrange — an install we refuse to upgrade ourselves
        ran = []
        monkeypatch.setattr(up, "__version__", "1.0.0")
        monkeypatch.setattr(up, "fetch_latest_version", lambda timeout=5.0: "9.9.9")
        monkeypatch.setattr(up.subprocess, "run", lambda *a, **k: ran.append(a))
        monkeypatch.setattr(
            up, "detect_install",
            lambda: Install(up.NPM, None, "    npm install -g gitpulse-tui@latest", "/x"),
        )

        # Act
        code = run_update()

        # Assert
        assert code == 0
        assert ran == []
        assert "npm install -g" in capsys.readouterr().out

    def test_failed_upgrade_surfaces_the_manual_command(self, monkeypatch, capsys):
        # Arrange
        class Failed:
            returncode = 1

        monkeypatch.setattr(up, "__version__", "1.0.0")
        monkeypatch.setattr(up, "fetch_latest_version", lambda timeout=5.0: "9.9.9")
        monkeypatch.setattr(up.subprocess, "run", lambda *a, **k: Failed())
        monkeypatch.setattr(
            up, "detect_install",
            lambda: Install(up.VENV, ["false"], "    pip install -U gitpulse-tui", "/x"),
        )

        # Act
        code = run_update()

        # Assert
        assert code == 1
        assert "pip install -U gitpulse-tui" in capsys.readouterr().err

    def test_running_ahead_of_pypi_is_not_an_error(self, monkeypatch, capsys):
        """An editable checkout is often newer than the published release."""
        # Arrange
        monkeypatch.setattr(up, "__version__", "2.0.0")
        monkeypatch.setattr(up, "fetch_latest_version", lambda timeout=5.0: "1.2.16")

        # Act
        code = run_update()

        # Assert
        assert code == 0
        assert "newer or unpublished" in capsys.readouterr().out
