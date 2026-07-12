// SPDX-License-Identifier: MIT

import { isRetryableRelayError } from "./errors.js";

function installPortFilter(client, allowedPorts) {
  const immutableAllowlist = new Set(allowedPorts);
  return client.portForwarding((event) => {
    if (!Number.isInteger(event?.portNumber) || !immutableAllowlist.has(event.portNumber)) {
      event.cancel = true;
    }
  });
}

export async function runRelayAttempt({ createClient, tunnel, allowedPorts, signal }) {
  const client = await createClient();
  let subscription;
  try {
    subscription = installPortFilter(client, allowedPorts);
    await client.connect(tunnel, signal);
    await client.waitForDisconnect(signal);
  } finally {
    subscription?.dispose();
    await client.dispose();
  }
}

function abortableSleep(milliseconds, signal) {
  if (signal.aborted) {
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    const timer = setTimeout(finish, milliseconds);
    signal.addEventListener("abort", finish, { once: true });

    function finish() {
      clearTimeout(timer);
      signal.removeEventListener("abort", finish);
      resolve();
    }
  });
}

export async function superviseRelay({
  createClient,
  tunnel,
  allowedPorts,
  signal,
  sleep = abortableSleep,
  random = Math.random,
  onRetry = () => {},
}) {
  let failures = 0;

  while (!signal.aborted) {
    try {
      await runRelayAttempt({ createClient, tunnel, allowedPorts, signal });
      return;
    } catch (error) {
      if (signal.aborted) {
        return;
      }
      if (!isRetryableRelayError(error)) {
        throw error;
      }

      failures += 1;
      const ceiling = Math.min(30_000, 1_000 * 2 ** Math.min(failures - 1, 5));
      const delay = Math.round(ceiling * (0.75 + random() * 0.5));
      onRetry({ failures, delay });
      await sleep(delay, signal);
    }
  }
}
