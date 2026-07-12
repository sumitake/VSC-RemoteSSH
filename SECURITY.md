# Security Policy

## Supported versions

Security fixes are applied to the current default branch. No stable release is
supported until it is listed in this table.

| Version | Supported |
| --- | --- |
| `main` | Yes |

## Report a vulnerability

Use GitHub's private vulnerability reporting for this repository. Do not open a
public issue containing credentials, real tunnel identifiers, hostnames, account
names, exploit details, or unredacted logs.

Include the affected commit, operating system, Node.js and Python versions, a
minimal reproduction, and the expected security invariant. Maintainers will
acknowledge a complete report as capacity permits; this project does not promise
a fixed response or remediation SLA.

## Security boundaries

- The relay binds only to local loopback (`127.0.0.1` and the SDK's `::1` mirror)
  and forwards only explicitly allowed ports.
- GitHub tokens are read from the environment once and scrubbed, or obtained from
  the GitHub CLI credential store. Tokens must never appear in CLI arguments.
- The RPC endpoint and all remote output are untrusted. Protocol frames, stream
  transitions, output volume, and execution arguments are validated and bounded.
- `--raw-output` disables terminal-control sanitization. Never use it when output
  is attached to a terminal unless the remote command is fully trusted.
- Any local user able to connect to another user's loopback sockets is inside the
  client-host trust boundary. Use normal operating-system account isolation.

See [Security model](docs/architecture-and-operations.md#security-model) for the
full threat model and recovery behavior.
