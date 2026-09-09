# Third-Party Notices

This source repository is MIT-licensed except where a file or directory states
otherwise.

## Microsoft dev tunnels SDK

The Node.js runtime depends on version `1.3.50` of:

- `@microsoft/dev-tunnels-connections`
- `@microsoft/dev-tunnels-contracts`
- `@microsoft/dev-tunnels-management`

These packages are distributed under the MIT License. Source and license:
<https://github.com/microsoft/dev-tunnels/tree/85c5efe5447005c0953db3d34226682b26c1ede3>

The relay also directly pins `vscode-jsonrpc` version `4.0.0` for the SDK's
cancellation-token contract. It is distributed under the MIT License. Source and
license: <https://github.com/microsoft/vscode-languageserver-node>

## MessagePack for Python

The Python runtime depends on `msgpack` version `1.2.2`, distributed under the
Apache License 2.0. Source and license:
<https://github.com/msgpack/msgpack-python>

## VS Code Remote interface assets

Generalized interface documentation and fixtures under
`assets/vscode-interface/` are adapted from or informed by material in the
Microsoft `vscode-remote-release` repository and are separately licensed under
CC-BY-4.0. That directory contains the license text, attribution, pinned source
revision, and modification notice.

The VS Code CLI, VS Code Server, Remote extensions, `.vsix` packages, product
artwork, and proprietary binaries are not distributed by this repository. Those
products have separate Microsoft terms. See:

- <https://github.com/microsoft/vscode-remote-release/blob/main/LICENSE-extensions>
- <https://code.visualstudio.com/docs/remote/tunnels#_using-the-code-cli>
