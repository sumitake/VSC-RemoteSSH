// SPDX-License-Identifier: MIT

import connections from "@microsoft/dev-tunnels-connections";
import contracts from "@microsoft/dev-tunnels-contracts";
import jsonrpc from "vscode-jsonrpc";

import { ConfigurationError, RelayConnectionError, isRetryableRelayError } from "./errors.js";

const { ConnectionStatus, TunnelRelayTunnelClient } = connections;
const { TunnelAccessScopes } = contracts;
const { CancellationTokenSource } = jsonrpc;

const TUNNEL_REQUEST_OPTIONS = Object.freeze({
  includePorts: true,
  tokenScopes: [TunnelAccessScopes.Connect],
});

export async function resolveTunnel(managementClient, tunnelSelector) {
  if (tunnelSelector.tunnelName) {
    const matches = await managementClient.listTunnels(undefined, undefined, {
      labels: [tunnelSelector.tunnelName, "vscode-server-launcher"],
      requireAllLabels: true,
      limit: 2,
    });
    if (matches.length !== 1) {
      throw new ConfigurationError(
        "A friendly tunnel name must resolve to exactly one VS Code tunnel",
      );
    }
    return managementClient.getTunnel(matches[0], TUNNEL_REQUEST_OPTIONS);
  }

  return managementClient.getTunnel(
    {
      tunnelId: tunnelSelector.tunnelId,
      clusterId: tunnelSelector.clusterId,
    },
    TUNNEL_REQUEST_OPTIONS,
  );
}

export async function connectWithAbort(
  client,
  tunnel,
  options,
  signal,
  dispose = () => client.dispose(),
  cancellationSource = new CancellationTokenSource(),
) {
  if (signal.aborted) {
    cancellationSource.cancel();
    await dispose();
    return;
  }

  let resolveAbort;
  const aborted = new Promise((resolve) => {
    resolveAbort = resolve;
  });
  const onAbort = () => {
    cancellationSource.cancel();
    resolveAbort(Promise.resolve(dispose()).catch(() => {}));
  };
  signal.addEventListener("abort", onAbort, { once: true });

  const connected = Promise.resolve()
    .then(() => client.connect(tunnel, options, cancellationSource.token))
    .then(
      () => ({ type: "connected" }),
      (error) => ({ type: "error", error }),
    );

  try {
    const outcome = await Promise.race([
      connected,
      aborted.then(() => ({ type: "aborted" })),
    ]);
    if (outcome.type === "error" && !signal.aborted) {
      throw outcome.error;
    }
  } finally {
    signal.removeEventListener("abort", onAbort);
  }
}

function waitForFinalDisconnect(client) {
  let finish;
  const disconnected = new Promise((resolve) => {
    finish = resolve;
  });

  const subscription = client.connectionStatusChanged((event) => {
    if (event.status !== ConnectionStatus.Disconnected) {
      return;
    }
    const retryable = event.disconnectError
      ? isRetryableRelayError(event.disconnectError)
      : true;
    finish(new RelayConnectionError({ retryable }));
  });

  return { disconnected, subscription };
}

export async function createSdkRelayClient({
  managementClient,
  tunnelSelector,
  localForwardingHostAddress,
  hostId,
  onStatus = () => {},
}) {
  let tunnel;
  try {
    tunnel = await resolveTunnel(managementClient, tunnelSelector);
  } catch (error) {
    if (!isRetryableRelayError(error)) {
      error.retryable = false;
    }
    throw error;
  }

  if (!tunnel) {
    throw new ConfigurationError("The requested tunnel was not found");
  }

  const client = new TunnelRelayTunnelClient(managementClient, () => {});
  client.acceptLocalConnectionsForForwardedPorts = true;
  client.localForwardingHostAddress = localForwardingHostAddress;
  const finalDisconnect = waitForFinalDisconnect(client);
  const sdkCancellationSource = new CancellationTokenSource();
  let cancellationRequested = false;
  const cancellationSource = {
    token: sdkCancellationSource.token,
    cancel() {
      if (!cancellationRequested) {
        cancellationRequested = true;
        sdkCancellationSource.cancel();
      }
    },
  };
  const statusSubscription = client.connectionStatusChanged((event) => {
    onStatus(event.status);
  });
  let disposed = false;
  const disposeOnce = async () => {
    if (disposed) {
      return;
    }
    disposed = true;
    cancellationSource.cancel();
    finalDisconnect.subscription.dispose();
    statusSubscription.dispose();
    await client.dispose();
    sdkCancellationSource.dispose();
  };

  return {
    portForwarding: client.portForwarding,
    async connect(_reference, signal) {
      if (signal.aborted) {
        return;
      }
      await connectWithAbort(
        client,
        tunnel,
        {
          enableRetry: true,
          enableReconnect: true,
          hostId,
          keepAliveIntervalInSeconds: 30,
        },
        signal,
        disposeOnce,
        cancellationSource,
      );
    },
    async waitForDisconnect(signal) {
      if (signal.aborted) {
        return;
      }
      const outcome = await new Promise((resolve) => {
        const abort = () => resolve();
        signal.addEventListener("abort", abort, { once: true });
        finalDisconnect.disconnected.then(resolve).finally(() => {
          signal.removeEventListener("abort", abort);
        });
      });
      if (outcome instanceof Error && !signal.aborted) {
        throw outcome;
      }
    },
    async dispose() {
      await disposeOnce();
    },
  };
}
