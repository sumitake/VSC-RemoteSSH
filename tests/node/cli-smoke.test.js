// SPDX-License-Identifier: MIT

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import test from "node:test";

test("the installed SDK graph loads through the executable", () => {
  const result = spawnSync(
    process.execPath,
    ["bin/remote-ssh-tunnel-relay.js", "--help"],
    { encoding: "utf8" },
  );

  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /127\.0\.0\.1/);
  assert.equal(result.stderr, "");
});
