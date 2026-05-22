"use strict";

/**
 * paths.js — Cross-platform path helpers for the GitPulse npm wrapper.
 *
 * All runtime state lives in a stable per-user directory (~/.gitpulse) so it
 * survives npm package upgrades and avoids permission issues with global
 * node_modules locations.
 */

const os = require("os");
const path = require("path");

/** Root directory for all npm-wrapper-managed GitPulse state. */
function gitpulseDir() {
  return path.join(os.homedir(), ".gitpulse");
}

/** Directory holding the isolated Python virtual environment. */
function venvDir() {
  return path.join(gitpulseDir(), "venv");
}

/**
 * Absolute path to the Python interpreter inside the venv.
 * Windows venvs use Scripts/python.exe; POSIX venvs use bin/python.
 */
function venvPython() {
  if (process.platform === "win32") {
    return path.join(venvDir(), "Scripts", "python.exe");
  }
  return path.join(venvDir(), "bin", "python");
}

/** JSON file recording the installed version + interpreter path. */
function stateFile() {
  return path.join(gitpulseDir(), "state.json");
}

module.exports = { gitpulseDir, venvDir, venvPython, stateFile };
