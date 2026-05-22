"use strict";

/**
 * install.js — Idempotent Python venv bootstrapper for the GitPulse npm wrapper.
 *
 * Creates an isolated virtual environment at ~/.gitpulse/venv and installs the
 * version-pinned `gitpulse-tui` package from PyPI into it. The npm package
 * carries no Python logic — it only orchestrates this install and then launches
 * the Python entry point.
 */

const fs = require("fs");
const { spawnSync } = require("child_process");

const { findPython, pythonMissingMessage } = require("./python");
const { gitpulseDir, venvDir, venvPython, stateFile } = require("./paths");

const PYPI_PACKAGE = "gitpulse-tui";

/** Error subclass carrying a pre-formatted, user-facing remediation message. */
class InstallError extends Error {}

function log(line) {
  process.stdout.write(`${line}\n`);
}

function readState() {
  try {
    return JSON.parse(fs.readFileSync(stateFile(), "utf8"));
  } catch (_) {
    return null;
  }
}

function writeState(version, pythonPath) {
  fs.writeFileSync(
    stateFile(),
    JSON.stringify(
      {
        installedVersion: version,
        pythonPath: pythonPath,
        updatedAt: new Date().toISOString(),
      },
      null,
      2,
    ) + "\n",
  );
}

/** True if the venv interpreter exists and is usable. */
function venvPythonExists() {
  try {
    fs.accessSync(venvPython(), fs.constants.X_OK);
    return true;
  } catch (_) {
    return false;
  }
}

/** Inspect a failed spawn result and throw an InstallError with guidance. */
function throwForFailure(stage, result, targetVersion) {
  const stderr = (result && result.stderr ? result.stderr : "").toString();
  const stdout = (result && result.stdout ? result.stdout : "").toString();
  const combined = `${stdout}\n${stderr}`;
  let hint;

  if (/No module named (venv|ensurepip)|ensurepip is not available/i.test(combined)) {
    hint =
      "The Python 'venv' module is unavailable.\n" +
      "  Debian/Ubuntu:  sudo apt install python3-venv\n" +
      "  Fedora:         sudo dnf install python3-venv";
  } else if (
    new RegExp(`No matching distribution.*${PYPI_PACKAGE}`, "i").test(combined) ||
    /Could not find a version that satisfies/i.test(combined)
  ) {
    hint =
      `gitpulse-tui==${targetVersion} was not found on PyPI yet.\n` +
      "  A new release can take a minute to propagate — retry shortly with:\n" +
      "    GITPULSE_FORCE_REINSTALL=1 gitpulse";
  } else if (
    /Could not (fetch URL|connect)|Network is unreachable|Temporary failure in name resolution|timed out|SSLError|ProxyError/i.test(
      combined,
    )
  ) {
    hint =
      "A network error occurred while contacting PyPI.\n" +
      "  Check your internet connection / proxy settings and retry:\n" +
      "    GITPULSE_FORCE_REINSTALL=1 gitpulse";
  } else if (/Permission denied|EACCES/i.test(combined)) {
    hint =
      `Permission was denied while writing to ${gitpulseDir()}.\n` +
      "  Ensure your user owns that directory and retry.";
  } else {
    hint = "Re-run with GITPULSE_FORCE_REINSTALL=1 to rebuild from scratch.";
  }

  const detail = stderr.trim() || stdout.trim() || "(no output captured)";
  throw new InstallError(
    `GitPulse setup failed during: ${stage}\n\n${hint}\n\n--- captured output ---\n${detail}`,
  );
}

/** Remove a possibly-corrupt venv directory so it can be rebuilt. */
function removeVenv() {
  try {
    fs.rmSync(venvDir(), { recursive: true, force: true });
  } catch (_) {
    /* best effort */
  }
}

/**
 * Ensure the version-pinned Python GitPulse package is installed in the venv.
 *
 * @param {object} opts
 * @param {string} opts.targetVersion  Exact version to pin (e.g. "1.2.2").
 * @param {boolean} [opts.force]       Rebuild even if state looks current.
 * @returns {string} Absolute path to the venv Python interpreter.
 */
function ensurePythonPackage(opts) {
  const targetVersion = opts.targetVersion;
  const force = Boolean(opts.force);

  // Fast path — already on the right version.
  if (!force) {
    const state = readState();
    if (state && state.installedVersion === targetVersion && venvPythonExists()) {
      return venvPython();
    }
  }

  // Locate a host interpreter to bootstrap the venv.
  const python = findPython();
  if (!python) {
    throw new InstallError(pythonMissingMessage());
  }
  log(`▸ Using Python ${python.version} (${python.command})`);

  fs.mkdirSync(gitpulseDir(), { recursive: true });

  // Create (or recreate) the venv.
  if (force) {
    removeVenv();
  }
  if (!venvPythonExists()) {
    log("▸ Creating isolated environment at ~/.gitpulse/venv …");
    const venvArgs = python.args.concat(["-m", "venv", venvDir()]);
    const venvResult = spawnSync(python.command, venvArgs, {
      encoding: "utf8",
      timeout: 120000,
    });
    if (!venvResult || venvResult.status !== 0) {
      removeVenv();
      throwForFailure("creating virtual environment", venvResult, targetVersion);
    }
    log("  ✓ Environment created");
  }

  // Upgrade pip (best-effort — uses the latest pip for reliability).
  log("▸ Upgrading pip …");
  const pipUpgrade = spawnSync(
    venvPython(),
    ["-m", "pip", "install", "--upgrade", "pip"],
    { encoding: "utf8", timeout: 180000 },
  );
  if (!pipUpgrade || pipUpgrade.status !== 0) {
    log("  ! pip upgrade skipped (non-fatal) — continuing");
  } else {
    log("  ✓ pip up to date");
  }

  // Install the exact-pinned GitPulse package.
  const spec = `${PYPI_PACKAGE}==${targetVersion}`;
  log(`▸ Installing ${spec} from PyPI …`);
  const install = spawnSync(
    venvPython(),
    ["-m", "pip", "install", "--upgrade", spec],
    { encoding: "utf8", timeout: 300000 },
  );
  if (!install || install.status !== 0) {
    throwForFailure(`installing ${spec}`, install, targetVersion);
  }
  log(`  ✓ Installed ${spec}`);

  writeState(targetVersion, venvPython());
  return venvPython();
}

module.exports = { ensurePythonPackage, InstallError, PYPI_PACKAGE };
