// SPDX-License-Identifier: MIT

import assert from "node:assert/strict";
import test from "node:test";

import { runRelayAttempt, superviseRelay } from "../../src/relay/supervisor.js";

class FakeRelayClient {
  constructor({ connectError = null, actions = [] } = {}) {
    this.connectError = connectError;
    this.actions = actions;
    this.filter = null;
  }

  portForwarding(listener) {
    this.actions.push("filter");
    this.filter = listener;
    return { dispose() {} };
  }

  async connect() {
    this.actions.push("connect");
    if (this.connectError) {
      throw this.connectError;
    }
  }

  async waitForDisconnect() {
    this.actions.push("wait");
  }

  async dispose() {
    this.actions.push("dispose");
  }
}

test("installs the immutable port filter before connecting", async () => {
  const actions = [];
  const client = new FakeRelayClient({ actions });

  await runRelayAttempt({
    createClient: () => client,
    tunnel: { tunnelId: "not-logged" },
    allowedPorts: new Set([2200]),
    signal: AbortSignal.timeout(1000),
  });

  assert.deepEqual(actions, ["filter", "connect", "wait", "dispose"]);

  const denied = { portNumber: 22, cancel: false };
  client.filter(denied);
  assert.equal(denied.cancel, true);

  const allowed = { portNumber: 2200, cancel: false };
  client.filter(allowed);
  assert.equal(allowed.cancel, false);
});

test("creates and pre-filters a fresh client for every recovery attempt", async () => {
  const attempts = [];
  const transient = Object.assign(new Error("temporary"), { retryable: true });
  const clients = [
    new FakeRelayClient({ connectError: transient, actions: [] }),
    new FakeRelayClient({ actions: [] }),
  ];

  await superviseRelay({
    createClient: () => {
      const client = clients.shift();
      attempts.push(client);
      return client;
    },
    tunnel: {},
    allowedPorts: new Set([2200]),
    signal: AbortSignal.timeout(1000),
    sleep: async () => {},
    random: () => 0,
  });

  assert.deepEqual(attempts[0].actions, ["filter", "connect", "dispose"]);
  assert.deepEqual(attempts[1].actions, ["filter", "connect", "wait", "dispose"]);

  const deniedAfterRecovery = { portNumber: 22, cancel: false };
  attempts[1].filter(deniedAfterRecovery);
  assert.equal(deniedAfterRecovery.cancel, true);
});

test("does not retry non-transient failures", async () => {
  let creations = 0;
  const fatal = Object.assign(new Error("fatal"), { retryable: false });

  await assert.rejects(
    superviseRelay({
      createClient: () => {
        creations += 1;
        return new FakeRelayClient({ connectError: fatal });
      },
      tunnel: {},
      allowedPorts: new Set([2200]),
      signal: AbortSignal.timeout(1000),
      sleep: async () => {},
    }),
    fatal,
  );

  assert.equal(creations, 1);
});
