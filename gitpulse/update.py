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
import shutil
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


def _npm_global_root() -> Path | None:
    """Return npm's global node_modules directory, or None if npm is absent."""
    npm = shutil.which("npm")
    if npm is None:
        return None
    try:
        result = subprocess.run(
            [npm, "root", "-g"],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return Path(result.stdout.strip())


def _npm_upgrade_command() -> list[str] | None:
    """Build the command that upgrades the global npm package.

    Global npm prefixes are frequently root-owned, so the install needs sudo.
    Since ``--update`` is an interactive command with an inherited terminal,
    sudo can simply prompt for a password the way it would if the user typed
    the command themselves.

    Returns None when there is nothing sensible to run — no npm, or root is
    needed but there is no terminal to prompt on (a cron job or a pipe), where
    sudo would hang instead of asking.
    """
    npm = shutil.which("npm")
    if npm is None:
        return None

    base = [npm, "install", "-g", "gitpulse-tui@latest"]

    root = _npm_global_root()
    if root is None or os.access(root, os.W_OK):
        return base

    # Root needed from here on.
    if os.geteuid() == 0:
        return base

    sudo = shutil.which("sudo")
    if sudo is None:
        return None

    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        # Non-interactive: only proceed if sudo needs no password.
        try:
            probe = subprocess.run(
                [sudo, "-n", "true"], capture_output=True, timeout=10, check=False
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return [sudo, "-n", *base] if probe.returncode == 0 else None

    return [sudo, *base]


def detect_install() -> Install:
    """Work out how this interpreter's GitPulse was installed."""
    exe = Path(sys.executable).resolve()
    prefix = Path(sys.prefix).resolve()

    # npm wrapper — upgrade the npm package, not the venv. The wrapper pins an
    # exact gitpulse-tui==X.Y.Z from its own package.json and re-installs it on
    # the next launch, so a pip upgrade inside the venv would be reverted.
    try:
        npm_root = _npm_venv_root().resolve()
        if prefix == npm_root or npm_root in exe.parents:
            return Install(
                method=NPM,
                command=_npm_upgrade_command(),
                manual_hint=(
                    "    npm install -g gitpulse-tui@latest\n"
                    "    (or with sudo, if your global npm prefix needs root)"
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
                f"    pipx install --force {PACKAGE}\n\n"
                "This Python is managed by your operating system, so GitPulse "
                "will not\nmodify it — install into an isolated environment "
                "instead."
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
        print("Upgrade with:")
        print(install.manual_hint)
        return 0

    print(f"Upgrading via {install.method} …")

    # Warn before sudo stops for a password, so the prompt is not a surprise.
    if install.command[0].endswith("sudo") and "-n" not in install.command[:2]:
        print("Your global npm directory is root-owned; sudo will ask for your password.")

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

    if install.method == NPM:
        # The npm package is upgraded, but its pinned Python venv is not
        # rebuilt until the wrapper next runs. Do it now so the very next
        # command is already on the new version.
        _sync_npm_venv()

    print()
    print(f"Upgraded to gitpulse {latest}. Restart gitpulse to use it.")
    return 0


def _sync_npm_venv() -> None:
    """Rebuild the npm wrapper's pinned venv immediately after an upgrade.

    Invoking the wrapper once is enough: it compares its package.json version
    against state.json and re-installs the Python package when they differ.
    Progress goes to stderr, so this stays quiet on stdout.
    """
    launcher = shutil.which("gitpulse")
    if launcher is None:
        return
    try:
        subprocess.run(
            [launcher, "--version"],
            stdout=subprocess.DEVNULL,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        pass  # best effort — the wrapper will self-heal on the next run
