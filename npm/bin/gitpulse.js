#!/usr/bin/env node
"use strict";

/**
 * gitpulse.js — npm launcher for the Python GitPulse TUI.
 *
 * This is a thin wrapper: it ensures the version-pinned Python package is
 * installed in an isolated venv, then hands off entirely to it. All command
 * line arguments are forwarded transparently and stdin/stdout/stderr are
 * inherited so the Textual TUI works exactly as it does under pip.
 *
 * Wrapper behaviour is controlled only via environment variables, never CLI
 * flags, so argument forwarding to Python stays 100% transparent:
 *   GITPULSE_FORCE_REINSTALL=1   rebuild the venv before launching
 */

const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

const { ensurePythonPackage, InstallError } = require("../lib/install");
const { venvPython, stateFile } = require("../lib/paths");

const pkg = require(path.join(__dirname, "..", "package.json"));
const TARGET_VERSION = pkg.version;

function fail(message, code) {
  process.stderr.write(`\ngitpulse: ${message}\n\n`);
  process.exit(code || 1);
}

/** True when the venv already matches the version this launcher expects. */
function venvIsCurrent() {
  let state;
  try {
    state = JSON.parse(fs.readFileSync(stateFile(), "utf8"));
  } catch (_) {
    return false;
  }
  if (!state || state.installedVersion !== TARGET_VERSION) {
    return false;
  }
  try {
    fs.accessSync(venvPython(), fs.constants.X_OK);
    return true;
  } catch (_) {
    return false;
  }
}

/** Ensure the Python package is installed; returns the venv interpreter path. */
function prepareInterpreter() {
  const force = process.env.GITPULSE_FORCE_REINSTALL === "1";
  if (!force && venvIsCurrent()) {
    return venvPython();
  }
  try {
    return ensurePythonPackage({ targetVersion: TARGET_VERSION, force });
  } catch (err) {
    if (err instanceof InstallError) {
      fail(`could not prepare the Python runtime.\n\n${err.message}`, 1);
    }
    fail(`unexpected error preparing the Python runtime: ${err}`, 1);
  }
  return venvPython();
}

function main() {
  const interpreter = prepareInterpreter();
  const args = ["-m", "gitpulse"].concat(process.argv.slice(2));

  const child = spawn(interpreter, args, { stdio: "inherit" });

  // Forward termination signals so Ctrl+C / kill reaches the TUI cleanly.
  const forward = (signal) => {
    if (!child.killed) {
      try {
        child.kill(signal);
      } catch (_) {
        /* child already gone */
      }
    }
  };
  // Windows has no real POSIX signals; Node emulates SIGINT for Ctrl+C but
  // registering SIGTERM/SIGHUP there can throw, so guard each registration.
  for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
    try {
      process.on(signal, () => forward(signal));
    } catch (_) {
      /* unsupported on this platform */
    }
  }

  child.on("error", (err) => {
    if (err && err.code === "ENOENT") {
      fail(
        "the Python environment appears to be broken.\n" +
          "Rebuild it with:  GITPULSE_FORCE_REINSTALL=1 gitpulse --version",
        1,
      );
    }
    fail(`failed to launch GitPulse: ${err.message || err}`, 1);
  });

  child.on("exit", (code, signal) => {
    if (signal) {
      // Mirror POSIX convention: 128 + signal number.
      const signals = { SIGINT: 2, SIGTERM: 15, SIGHUP: 1, SIGQUIT: 3 };
      process.exit(128 + (signals[signal] || 0));
    }
    process.exit(code == null ? 1 : code);
  });
}

main();
