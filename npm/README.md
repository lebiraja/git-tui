# ⚡ gitpulse (npm)

npm launcher for **GitPulse** — a developer-focused terminal dashboard that
scans a directory for local Git repositories and shows live status, commits,
diffs, branches, and more.

This npm package is a **thin wrapper**. The application itself is written in
Python and published to PyPI as [`gitpulse-tui`](https://pypi.org/project/gitpulse-tui/).
Installing via npm simply bootstraps an isolated Python environment and launches
that package — there is no duplicated logic, and Python remains the single
source of truth.

## Why GitPulse?

A lot of development happens late at night, and not everyone commits or pushes
their changes right away. With "vibe coding" becoming so popular, many people
now juggle several projects at once — and that makes it genuinely hard to keep
track of every local repository.

GitPulse exists to solve exactly that. It gives you a single dashboard for all
your local repos, so at a glance you can see what's committed but not yet
pushed, what's changed but not yet committed, the number of modified files, the
current branch, the last commit, and everything else about the state of each
local Git repository.

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

If the npm `postinstall` step cannot complete, it does **not** fail the install
— the launcher retries the setup the first time you run `gitpulse`. Progress is
printed to stderr, so `gitpulse scan --json > out.json` stays valid even when
the bootstrap runs mid-command.

### "1 package had install scripts blocked"

Recent npm versions block install scripts by default, so you may see:

```
npm warn install-scripts   gitpulse-tui@X.Y.Z (postinstall: node scripts/postinstall.js)
```

**This is safe to ignore.** The Python runtime is set up automatically the next
time you run `gitpulse` — you will see a one-line notice while it finishes.

To let the postinstall run at install time instead, append the flag to a real
install command:

```bash
npm install -g --allow-scripts=gitpulse-tui gitpulse-tui@latest
```

Note that `npm install -g --allow-scripts=gitpulse-tui` **on its own**, with no
package named, fails with `Cannot destructure property 'name' of '.for'` — npm's
own warning text omits the package argument.

To allow it permanently:

```bash
npm config set allow-scripts=gitpulse-tui --location=user
```

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
