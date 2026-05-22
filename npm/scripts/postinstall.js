"use strict";

/**
 * postinstall.js — runs after `npm install -g gitpulse`.
 *
 * Bootstraps the Python venv and installs the version-pinned gitpulse-tui
 * package. Crucially, a failure here NEVER hard-fails `npm install`: it prints
 * actionable guidance and exits 0, because the launcher (bin/gitpulse.js)
 * self-heals on first run. This also keeps `npm install --ignore-scripts`
 * users working — the launcher rebuilds on demand.
 */

const path = require("path");
const { ensurePythonPackage } = require("../lib/install");

function main() {
  // Allow CI / Docker layer caching to skip the Python bootstrap.
  if (process.env.GITPULSE_SKIP_POSTINSTALL === "1") {
    console.log("GITPULSE_SKIP_POSTINSTALL=1 — skipping Python setup.");
    return;
  }

  const pkg = require(path.join(__dirname, "..", "package.json"));

  try {
    ensurePythonPackage({ targetVersion: pkg.version });
    console.log("\n✓ GitPulse is ready. Run `gitpulse` to launch.\n");
  } catch (err) {
    // Do not fail the npm install — degrade gracefully.
    const msg = err && err.message ? err.message : String(err);
    console.warn(
      [
        "",
        "────────────────────────────────────────────────────────────",
        " GitPulse: Python setup did not complete during npm install.",
        "────────────────────────────────────────────────────────────",
        msg,
        "",
        " This is not fatal — GitPulse will try again automatically the",
        " first time you run `gitpulse`. To retry now:",
        "",
        "   GITPULSE_FORCE_REINSTALL=1 gitpulse --version",
        "────────────────────────────────────────────────────────────",
        "",
      ].join("\n"),
    );
  }
}

main();
process.exit(0);
