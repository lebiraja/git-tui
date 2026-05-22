# ⚡ gitpulse (npm)

npm launcher for **GitPulse** — a developer-focused terminal dashboard that
scans a directory for local Git repositories and shows live status, commits,
diffs, branches, and more.

This npm package is a **thin wrapper**. The application itself is written in
Python and published to PyPI as [`gitpulse-tui`](https://pypi.org/project/gitpulse-tui/).
Installing via npm simply bootstraps an isolated Python environment and launches
that package — there is no duplicated logic, and Python remains the single
source of truth.

## Install

```bash
npm install -g gitpulse-tui
```

On install, the wrapper:

1. Detects a host Python 3.10+ interpreter.
2. Creates an isolated virtual environment at `~/.gitpulse/venv`.
3. Installs the matching `gitpulse-tui` version from PyPI into it.

Then just run:

```bash
gitpulse                          # scan the current directory
gitpulse --root /path/to/repos    # scan a custom directory
gitpulse --commits 20             # show 20 commits per repo
gitpulse --digest --since 7d      # print an activity digest
gitpulse --version
```

All arguments are forwarded transparently to the Python CLI.

## Requirements

- **Node.js** ≥ 16 (for the launcher only)
- **Python** ≥ 3.10 (the application runtime)
- **git** available on `PATH`
- Linux or macOS (Windows is best-effort)

## How it works

```
npm install -g gitpulse-tui
   └─ postinstall → ~/.gitpulse/venv → pip install gitpulse-tui==<version>

gitpulse <args>
   └─ bin/gitpulse.js → spawn <venv>/python -m gitpulse <args>   (stdio inherited)
```

The npm and PyPI versions are kept in lockstep by CI: npm `vX.Y.Z` always
installs `gitpulse-tui==X.Y.Z`.

If the npm `postinstall` step cannot complete (e.g. offline), it does **not**
fail the install — the launcher automatically retries the setup the first time
you run `gitpulse`.

## Environment variables

| Variable | Effect |
|---|---|
| `GITPULSE_FORCE_REINSTALL=1` | Rebuild the `~/.gitpulse/venv` from scratch before launching |
| `GITPULSE_SKIP_POSTINSTALL=1` | Skip the Python bootstrap during `npm install` (CI/Docker) |

## Troubleshooting

**`The Python 'venv' module is unavailable`** (Debian/Ubuntu)

```bash
sudo apt install python3-venv
GITPULSE_FORCE_REINSTALL=1 gitpulse --version
```

**`Python 3.10 or newer ... not found`**

Install Python 3.10+ from <https://www.python.org/downloads/>, then re-run
`npm install -g gitpulse-tui`.

**The environment looks broken**

```bash
GITPULSE_FORCE_REINSTALL=1 gitpulse --version
```

## License

AGPL-3.0 — see [LICENSE](./LICENSE).
