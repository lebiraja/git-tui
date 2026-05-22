"use strict";

/**
 * python.js — Host Python interpreter detection for the GitPulse npm wrapper.
 *
 * Probes the common interpreter names and returns the first one that satisfies
 * GitPulse's minimum requirement of Python 3.10+.
 */

const { spawnSync } = require("child_process");

const MIN_MAJOR = 3;
const MIN_MINOR = 10;

// Probe candidates in priority order. `py -3` is the Windows launcher.
function candidates() {
  if (process.platform === "win32") {
    return [
      { command: "py", args: ["-3"] },
      { command: "python", args: [] },
      { command: "python3", args: [] },
    ];
  }
  return [
    { command: "python3", args: [] },
    { command: "python", args: [] },
  ];
}

/**
 * Run `<candidate> -c "<print version>"` and parse "MAJOR MINOR".
 * Returns { major, minor } or null if the candidate is unusable.
 */
function probeVersion(candidate) {
  const probeArgs = candidate.args.concat([
    "-c",
    "import sys; print(sys.version_info[0], sys.version_info[1])",
  ]);
  let result;
  try {
    result = spawnSync(candidate.command, probeArgs, {
      encoding: "utf8",
      timeout: 15000,
    });
  } catch (_) {
    return null;
  }
  if (!result || result.status !== 0 || !result.stdout) {
    return null;
  }
  const parts = result.stdout.trim().split(/\s+/);
  if (parts.length < 2) {
    return null;
  }
  const major = parseInt(parts[0], 10);
  const minor = parseInt(parts[1], 10);
  if (Number.isNaN(major) || Number.isNaN(minor)) {
    return null;
  }
  return { major, minor };
}

function meetsMinimum(version) {
  if (version.major > MIN_MAJOR) return true;
  return version.major === MIN_MAJOR && version.minor >= MIN_MINOR;
}

/**
 * Find a usable Python interpreter.
 *
 * Returns { command, args, version: "X.Y" } for the first candidate that is
 * Python 3.10+, or null if none qualifies.
 */
function findPython() {
  for (const candidate of candidates()) {
    const version = probeVersion(candidate);
    if (version && meetsMinimum(version)) {
      return {
        command: candidate.command,
        args: candidate.args,
        version: `${version.major}.${version.minor}`,
      };
    }
  }
  return null;
}

/** Human-readable error shown when no suitable interpreter is found. */
function pythonMissingMessage() {
  return [
    `GitPulse requires Python ${MIN_MAJOR}.${MIN_MINOR} or newer, but no`,
    "suitable interpreter was found on your PATH.",
    "",
    "  Install Python 3.10+ from https://www.python.org/downloads/",
    "  (Linux: use your package manager, e.g. `sudo apt install python3`)",
    "",
    "Then re-run:  npm install -g gitpulse",
  ].join("\n");
}

module.exports = { findPython, pythonMissingMessage, MIN_MAJOR, MIN_MINOR };
