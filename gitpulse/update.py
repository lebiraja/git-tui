"""
update.py — Version check and self-upgrade for GitPulse.

GitPulse ships through two channels: PyPI (pip / pipx) and npm, where a thin
wrapper bootstraps its own virtualenv at ``~/.gitpulse/venv`` and pins an exact
version. A single upgrade command cannot serve both — pip-upgrading inside the
npm wrapper's venv would be silently undone the next time the wrapper runs and
re-pinned the version recorded in its ``state.json``.

So this module detects *how* GitPulse was installed and either runs the right
command or prints it, rather than guessing and leaving a broken install.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from .utils import __version__

PYPI_JSON_URL = "https://pypi.org/pypi/gitpulse-tui/json"
PACKAGE = "gitpulse-tui"

# Install methods, in the order they are probed.
NPM = "npm"
PIPX = "pipx"
VENV = "venv"
SYSTEM = "system"


@dataclass
class Install:
    """How this GitPulse was installed, and how to upgrade it."""

    method: str
    #: Command to run for an in-place upgrade, or None if unsafe to self-run.
    command: list[str] | None
    #: What to tell the user when we will not run the upgrade ourselves.
    manual_hint: str
    #: Human-readable location, for display.
    location: str


def _npm_venv_root() -> Path:
    """The venv the npm wrapper manages (``~/.gitpulse/venv``)."""
    return Path.home() / ".gitpulse" / "venv"


def detect_install() -> Install:
    """Work out how this interpreter's GitPulse was installed."""
    exe = Path(sys.executable).resolve()
    prefix = Path(sys.prefix).resolve()

    # npm wrapper — its venv is re-pinned from npm/package.json on every
    # launch, so upgrading the Python package alone would be reverted.
    try:
        npm_root = _npm_venv_root().resolve()
        if prefix == npm_root or npm_root in exe.parents:
            return Install(
                method=NPM,
                command=None,
                manual_hint=(
                    "Installed via npm. Upgrade with:\n"
                    "    npm install -g gitpulse-tui@latest\n\n"
                    "The npm wrapper pins an exact Python package version, so "
                    "upgrading\nit with pip alone would be undone on the next "
                    "launch."
                ),
                location=str(npm_root),
            )
    except OSError:
        pass

    # pipx — each app gets its own venv under PIPX_HOME (or ~/.local/pipx).
    pipx_home = os.environ.get("PIPX_HOME")
    pipx_roots = [Path(pipx_home)] if pipx_home else []
    pipx_roots += [Path.home() / ".local" / "pipx", Path.home() / ".local" / "share" / "pipx"]
    for root in pipx_roots:
        try:
            if root.resolve() in prefix.parents:
                return Install(
                    method=PIPX,
                    command=["pipx", "upgrade", PACKAGE],
                    manual_hint=f"    pipx upgrade {PACKAGE}",
                    location=str(prefix),
                )
        except OSError:
            continue

    # A regular virtualenv — safe to upgrade in place with this interpreter.
    if sys.prefix != sys.base_prefix:
        return Install(
            method=VENV,
            command=[
                sys.executable, "-m", "pip", "install", "--upgrade",
                "--quiet", "--disable-pip-version-check", PACKAGE,
            ],
            manual_hint=f"    {sys.executable} -m pip install --upgrade {PACKAGE}",
            location=str(prefix),
        )

    # System / user install. PEP 668 marks distro-managed interpreters where
    # pip should not write; never run an upgrade against those.
    externally_managed = Path(sysconfig.get_path("stdlib")) / "EXTERNALLY-MANAGED"
    if externally_managed.exists():
        return Install(
            method=SYSTEM,
            command=None,
            manual_hint=(
                "This Python is managed by your operating system, so GitPulse "
                "will not\nmodify it. Install into an isolated environment "
                "instead:\n"
                f"    pipx install --force {PACKAGE}"
            ),
            location=str(prefix),
        )

    return Install(
        method=SYSTEM,
        command=[
            sys.executable, "-m", "pip", "install", "--upgrade",
            "--quiet", "--disable-pip-version-check", PACKAGE,
        ],
        manual_hint=f"    {sys.executable} -m pip install --upgrade {PACKAGE}",
        location=str(prefix),
    )


def fetch_latest_version(timeout: float = 5.0) -> str:
    """Return the newest version of *gitpulse-tui* published on PyPI.

    Raises:
        URLError: the network call failed or timed out.
        ValueError: PyPI returned something unparseable.
    """
    request = Request(
        PYPI_JSON_URL,
        headers={"User-Agent": f"gitpulse/{__version__}"},
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https URL
        payload = json.load(response)
    try:
        return str(payload["info"]["version"])
    except (KeyError, TypeError) as exc:
        raise ValueError("unexpected response from PyPI") from exc


def _version_tuple(version: str) -> tuple:
    """Parse a version into integer components for comparison.

    Non-numeric suffixes are truncated, so ``1.2.3rc1`` compares equal to
    ``1.2.3`` rather than before it. GitPulse's release pipeline only ever
    publishes plain ``X.Y.Z``, so this is not worth a full PEP 440 parser; the
    consequence of the simplification is that a pre-release is never reported
    as an available upgrade.
    """
    parts: list[int] = []
    for chunk in version.split("."):
        digits = ""
        for ch in chunk:
            if not ch.isdigit():
                break
            digits += ch
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def is_newer(latest: str, current: str) -> bool:
    """True if *latest* is a strictly greater version than *current*."""
    return _version_tuple(latest) > _version_tuple(current)


def run_update(check_only: bool = False) -> int:
    """Compare the installed version against PyPI and upgrade if possible.

    Returns a process exit code.
    """
    print(f"gitpulse {__version__} (installed)")

    try:
        latest = fetch_latest_version()
    except URLError as exc:
        print(f"Error: could not reach PyPI — {exc.reason}", file=sys.stderr)
        return 1
    except (ValueError, TimeoutError, OSError) as exc:
        print(f"Error: could not check for updates — {exc}", file=sys.stderr)
        return 1

    if not is_newer(latest, __version__):
        if latest != __version__:
            # Ahead of PyPI — an editable checkout or a pre-release.
            print(f"gitpulse {latest} is the latest published release.")
            print("You are running a newer or unpublished build.")
        else:
            print("Already up to date.")
        return 0

    print(f"gitpulse {latest} is available.")

    install = detect_install()

    if check_only or install.command is None:
        print()
        if install.command is None:
            print(install.manual_hint)
        else:
            print("Upgrade with:")
            print(install.manual_hint)
        return 0

    print(f"Upgrading via {install.method} at {install.location} …")

    try:
        result = subprocess.run(install.command, check=False)
    except OSError as exc:
        print(f"Error: could not run the upgrade — {exc}", file=sys.stderr)
        print("Run it manually:", file=sys.stderr)
        print(install.manual_hint, file=sys.stderr)
        return 1

    if result.returncode != 0:
        print(file=sys.stderr)
        print("Upgrade failed. Run it manually:", file=sys.stderr)
        print(install.manual_hint, file=sys.stderr)
        return result.returncode

    print()
    print(f"Upgraded to gitpulse {latest}. Restart gitpulse to use it.")
    return 0
