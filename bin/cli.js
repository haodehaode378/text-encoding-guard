#!/usr/bin/env node
"use strict";

const { spawnSync } = require("child_process");
const path = require("path");

const srcDir = path.resolve(__dirname, "..", "src");

function findPython() {
  for (const cmd of ["python3", "python"]) {
    const r = spawnSync(cmd, ["--version"], { stdio: "ignore" });
    if (r.status === 0) return cmd;
  }
  return null;
}

const python = findPython();
if (!python) {
  console.error(
    "[ai-text-encoding-guard] Error: Python 3.10+ is required but not found.\n" +
      "Install Python from https://www.python.org/downloads/ and try again."
  );
  process.exit(1);
}

const args = process.argv.slice(2);
const result = spawnSync(python, ["-m", "check_mojibake", ...args], {
  cwd: process.cwd(),
  stdio: "inherit",
  env: { ...process.env, PYTHONPATH: srcDir + path.delimiter + (process.env.PYTHONPATH || "") },
});

process.exit(result.status ?? 1);
