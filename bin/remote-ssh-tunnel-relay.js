#!/usr/bin/env node
// SPDX-License-Identifier: MIT

import management from "@microsoft/dev-tunnels-management";

import { parseRelayConfig, relayHelp } from "../src/relay/config.js";
import { publicErrorCategory } from "../src/relay/errors.js";
import { acquireGitHubToken } from "../src/relay/github-token.js";
import { createLogger } from "../src/relay/logger.js";
import { createSdkRelayClient } from "../src/relay/sdk-client.js";
import { superviseRelay } from "../src/relay/supervisor.js";

const { ManagementApiVersions, TunnelAuthenticationSchemes, TunnelManagementHttpClient } =
  management;
const VERSION = "0.1.0";
const log = createLogger();

function scheduleExitFallback(code) {
  const forcedExit = setTimeout(() => process.exit(code), 250);
  forcedExit.unref();
}

async function main() {
  const config = parseRelayConfig(process.argv.slice(2));
  if (config.help) {
    process.stdout.write(`${relayHelp()}\n`);
    return;
  }
  if (config.version) {
    process.stdout.write(`${VERSION}\n`);
    return;
  }

  const token = acquireGitHubToken({ githubUser: config.githubUser });
  const managementClient = new TunnelManagementHttpClient(
    [{ name: "remote-ssh-tunnel", version: VERSION }],
    ManagementApiVersions.Version20230927preview,
    async () => `${TunnelAuthenticationSchemes.github} ${token}`,
  );
  managementClient.enableEventsReporting = false;
  managementClient.trace = () => {};

  const abortController = new AbortController();
  const stop = () => abortController.abort();
  process.once("SIGINT", stop);
  process.once("SIGTERM", stop);

  const tunnelSelector = {
    tunnelName: config.tunnelName,
    tunnelId: config.tunnelId,
    clusterId: config.clusterId,
  };

  log("info", "relay_starting", { ports: config.ports });
  try {
    await superviseRelay({
      createClient: () =>
        createSdkRelayClient({
          managementClient,
          tunnelSelector,
          localForwardingHostAddress: config.localForwardingHostAddress,
          hostId: config.hostId,
          onStatus: (status) => log("info", "relay_status", { status }),
        }),
      tunnel: tunnelSelector,
      allowedPorts: new Set(config.ports),
      signal: abortController.signal,
      onRetry: ({ failures, delay }) =>
        log("warn", "relay_retry", { attempt: failures, delay_ms: delay }),
    });
  } finally {
    process.removeListener("SIGINT", stop);
    process.removeListener("SIGTERM", stop);
    await managementClient.dispose();
  }
  log("info", "relay_stopped");
  if (abortController.signal.aborted) {
    scheduleExitFallback(0);
  }
}

main().catch((error) => {
  log("error", "relay_failed", { category: publicErrorCategory(error) });
  process.exitCode = 1;
  scheduleExitFallback(1);
});
