// SPDX-License-Identifier: MIT

import assert from "node:assert/strict";
import test from "node:test";

import { LOOPBACK_HOST, parseRelayConfig } from "../../src/relay/config.js";

test("parses an explicit CLI allowlist and keeps the bind address on loopback", () => {
  const config = parseRelayConfig(
    [
      "--tunnel-id",
      "example-tunnel",
      "--cluster-id",
      "use1",
      "--port",
      "2200",
      "--port",
      "2201",
      "--port",
      "2200",
    ],
    {},
  );

  assert.equal(config.localForwardingHostAddress, LOOPBACK_HOST);
  assert.deepEqual(config.ports, [2200, 2201]);
  assert.equal(config.tunnelId, "example-tunnel");
  assert.equal(config.clusterId, "use1");
});

test("reads non-secret settings from the environment", () => {
  const config = parseRelayConfig([], {
    REMOTE_SSH_TUNNEL_ID: "example-tunnel",
    REMOTE_SSH_TUNNEL_CLUSTER_ID: "use1",
    REMOTE_SSH_TUNNEL_PORTS: "2200, 2201",
    REMOTE_SSH_TUNNEL_GITHUB_USER: "example-user",
  });

  assert.deepEqual(config.ports, [2200, 2201]);
  assert.equal(config.githubUser, "example-user");
});

test("accepts a friendly VS Code tunnel name without internal IDs", () => {
  const config = parseRelayConfig(
    ["--tunnel-name", "example-host", "--port", "2200"],
    {},
  );

  assert.equal(config.tunnelName, "example-host");
  assert.equal(config.tunnelId, undefined);
  assert.equal(config.clusterId, undefined);
});

test("rejects ambiguous friendly-name and internal-ID selectors", () => {
  assert.throws(
    () =>
      parseRelayConfig(
        [
          "--tunnel-name",
          "example-host",
          "--tunnel-id",
          "example-id",
          "--cluster-id",
          "use1",
          "--port",
          "2200",
        ],
        {},
      ),
    /either/i,
  );
});

for (const [name, argv] of [
  ["missing ports", ["--tunnel-id", "example", "--cluster-id", "use1"]],
  ["zero port", ["--tunnel-id", "example", "--cluster-id", "use1", "--port", "0"]],
  ["large port", ["--tunnel-id", "example", "--cluster-id", "use1", "--port", "65536"]],
  ["non-numeric port", ["--tunnel-id", "example", "--cluster-id", "use1", "--port", "ssh"]],
]) {
  test(`rejects ${name}`, () => {
    assert.throws(() => parseRelayConfig(argv, {}), /port/i);
  });
}

test("does not accept a configurable listen address", () => {
  assert.throws(
    () =>
      parseRelayConfig(
        [
          "--tunnel-id",
          "example",
          "--cluster-id",
          "use1",
          "--port",
          "2200",
          "--listen-host",
          "0.0.0.0",
        ],
        {},
      ),
    /Unknown option/i,
  );
});
