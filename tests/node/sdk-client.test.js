// SPDX-License-Identifier: MIT

import assert from "node:assert/strict";
import test from "node:test";

import { connectWithAbort, resolveTunnel } from "../../src/relay/sdk-client.js";

test("resolves one VS Code tunnel by its friendly-name label", async () => {
  const expected = { tunnelId: "opaque", clusterId: "use1" };
  let receivedOptions;
  const managementClient = {
    async listTunnels(cluster, domain, options) {
      assert.equal(cluster, undefined);
      assert.equal(domain, undefined);
      receivedOptions = options;
      return [expected];
    },
    async getTunnel(reference, options) {
      assert.equal(reference, expected);
      assert.equal(options.includePorts, true);
      assert.deepEqual(options.tokenScopes, ["connect"]);
      return { ...expected, accessTokens: { connect: "not-a-real-token" } };
    },
  };

  const tunnel = await resolveTunnel(managementClient, { tunnelName: "example-host" });

  assert.equal(tunnel.tunnelId, expected.tunnelId);
  assert.deepEqual(tunnel.accessTokens, { connect: "not-a-real-token" });
  assert.deepEqual(receivedOptions.labels, ["example-host", "vscode-server-launcher"]);
  assert.equal(receivedOptions.requireAllLabels, true);
  assert.equal(receivedOptions.limit, 2);
});

test("fails closed when a friendly name is missing or ambiguous", async () => {
  for (const matches of [[], [{ tunnelId: "one" }, { tunnelId: "two" }]]) {
    const managementClient = {
      listTunnels: async () => matches,
      getTunnel: async () => {
        throw new Error("getTunnel must not run for an ambiguous selector");
      },
    };
    await assert.rejects(
      resolveTunnel(managementClient, { tunnelName: "example-host" }),
      /exactly one/i,
    );
  }
});

test("one abort disposes and releases a pending SDK connection", async () => {
  const controller = new AbortController();
  let disposed = 0;
  let cancelled = 0;
  let receivedCancellationToken;
  const cancellationSource = {
    token: { kind: "test-cancellation-token" },
    cancel() {
      cancelled += 1;
    },
  };
  const client = {
    connect: (_tunnel, _options, cancellationToken) => {
      receivedCancellationToken = cancellationToken;
      return new Promise(() => {});
    },
    async dispose() {
      disposed += 1;
    },
  };

  const pending = connectWithAbort(
    client,
    {},
    {},
    controller.signal,
    () => client.dispose(),
    cancellationSource,
  );
  controller.abort();
  await pending;

  assert.equal(receivedCancellationToken, cancellationSource.token);
  assert.equal(cancelled, 1);
  assert.equal(disposed, 1);
});
