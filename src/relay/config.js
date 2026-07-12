// SPDX-License-Identifier: MIT

import { parseArgs } from "node:util";

import { ConfigurationError } from "./errors.js";

export const LOOPBACK_HOST = "127.0.0.1";

const IDENTIFIER_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;

function requireIdentifier(value, name) {
  if (!value || !IDENTIFIER_PATTERN.test(value)) {
    throw new ConfigurationError(`${name} must be a non-empty service identifier`);
  }
  return value;
}

function parsePorts(values) {
  const requested = values.flatMap((value) => String(value).split(","));
  const ports = [];
  const seen = new Set();

  for (const raw of requested) {
    const value = raw.trim();
    if (!/^\d+$/.test(value)) {
      throw new ConfigurationError(`Invalid port: ${value || "empty"}`);
    }
    const port = Number(value);
    if (!Number.isSafeInteger(port) || port < 1 || port > 65535) {
      throw new ConfigurationError(`Invalid port: ${value}`);
    }
    if (!seen.has(port)) {
      seen.add(port);
      ports.push(port);
    }
  }

  if (ports.length === 0) {
    throw new ConfigurationError("At least one explicit port is required");
  }
  return ports;
}

export function parseRelayConfig(argv, env = process.env) {
  let values;
  try {
    ({ values } = parseArgs({
      args: argv,
      strict: true,
      allowPositionals: false,
      options: {
        "tunnel-name": { type: "string" },
        "tunnel-id": { type: "string" },
        "cluster-id": { type: "string" },
        port: { type: "string", multiple: true },
        "github-user": { type: "string" },
        "host-id": { type: "string" },
        help: { type: "boolean", short: "h", default: false },
        version: { type: "boolean", short: "V", default: false },
      },
    }));
  } catch (error) {
    throw new ConfigurationError(error.message);
  }

  if (values.help || values.version) {
    return { help: values.help, version: values.version };
  }

  const rawTunnelName = values["tunnel-name"] ?? env.REMOTE_SSH_TUNNEL_NAME;
  const rawTunnelId = values["tunnel-id"] ?? env.REMOTE_SSH_TUNNEL_ID;
  const rawClusterId = values["cluster-id"] ?? env.REMOTE_SSH_TUNNEL_CLUSTER_ID;
  if (rawTunnelName && (rawTunnelId || rawClusterId)) {
    throw new ConfigurationError(
      "Select a tunnel using either its friendly name or its tunnel ID and cluster ID",
    );
  }
  const tunnelName = rawTunnelName
    ? requireIdentifier(rawTunnelName, "Tunnel name")
    : undefined;
  const tunnelId = tunnelName ? undefined : requireIdentifier(rawTunnelId, "Tunnel ID");
  const clusterId = tunnelName
    ? undefined
    : requireIdentifier(rawClusterId, "Cluster ID");
  const portValues = values.port ??
    (env.REMOTE_SSH_TUNNEL_PORTS ? [env.REMOTE_SSH_TUNNEL_PORTS] : []);

  return Object.freeze({
    tunnelId,
    clusterId,
    tunnelName,
    ports: Object.freeze(parsePorts(portValues)),
    githubUser: values["github-user"] ?? env.REMOTE_SSH_TUNNEL_GITHUB_USER,
    hostId: values["host-id"] ?? env.REMOTE_SSH_TUNNEL_HOST_ID,
    localForwardingHostAddress: LOOPBACK_HOST,
  });
}

export function relayHelp() {
  return `Usage: remote-ssh-tunnel-relay [options]

Required settings (CLI or environment):
  --tunnel-name NAME   REMOTE_SSH_TUNNEL_NAME (recommended)
    or both:
  --tunnel-id ID       REMOTE_SSH_TUNNEL_ID
  --cluster-id ID      REMOTE_SSH_TUNNEL_CLUSTER_ID
  --port PORT          REMOTE_SSH_TUNNEL_PORTS (comma-separated)

Optional:
  --github-user USER   GitHub CLI account to use
  --host-id ID         Select one host when a tunnel has multiple hosts
  -h, --help           Show help
  -V, --version        Show version

Authentication is read from GITHUB_TOKEN/GH_TOKEN and scrubbed immediately,
or obtained from the GitHub CLI credential store. The relay uses local loopback
(127.0.0.1, with an SDK-managed ::1 mirror where available) and rejects every
port outside the explicit allowlist.`;
}
