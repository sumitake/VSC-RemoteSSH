# VS Code Remote Interface Assets

This directory is the explicit licensing boundary for generalized interface
documentation and fixtures adapted from or informed by the Microsoft
[`vscode-remote-release`](https://github.com/microsoft/vscode-remote-release)
repository and observed VS Code Remote tunnel behavior.

## Attribution

- Creator: Microsoft Corporation and contributors.
- Source repository: <https://github.com/microsoft/vscode-remote-release>
- Source revision: `1803940623da0ba648084b5ba0b1265b2b854ae4`
- Repository license: CC-BY-4.0, copied in [LICENSE](LICENSE).
- Source metadata: [SOURCE.json](SOURCE.json).

## Modifications

The project authors replaced deployment-specific values with placeholders,
reorganized the interface lifecycle into implementation-neutral JSON fixtures,
added explicit message directions and security expectations, and omitted all
product code, extension packages, binaries, artwork, logs, credentials, and host
metadata. The fixtures are descriptive test assets; they are not Microsoft APIs
or a promise of upstream compatibility.

## Contents

- [`fixtures/protocol-v5-flow.json`](fixtures/protocol-v5-flow.json): generalized
  hello, version, spawn, stream, and result message sequence.

Only files inside this directory are covered by this directory's CC-BY-4.0
notice. Original project code elsewhere remains under the root MIT license.

VS Code CLI, VS Code Server, and the Remote extensions are installed separately
by users and remain governed by Microsoft's separate product terms:
<https://github.com/microsoft/vscode-remote-release/blob/main/LICENSE-extensions>
