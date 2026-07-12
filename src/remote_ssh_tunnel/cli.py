# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import math
import os
import re
import sys
from collections.abc import Mapping, Sequence
from typing import BinaryIO, TextIO

from .output import SafeOutputRenderer
from .rpc import OutputLimitError, ProtocolError, RemoteCommandError, RpcClient

ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _port(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be from 1 to 65535")
    return port


def _positive_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return number


def _positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return number


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="remote-ssh-tunnel-rpc",
        description="Run one direct command through a local VS Code tunnel RPC endpoint.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", required=True, type=_port)
    parser.add_argument("--cwd")
    parser.add_argument("--pass-env", action="append", default=[], metavar="NAME")
    parser.add_argument("--connect-timeout", type=_positive_float, default=10.0)
    parser.add_argument("--deadline", type=_positive_float, default=300.0)
    parser.add_argument("--max-output-bytes", type=_positive_int, default=16 * 1024 * 1024)
    parser.add_argument(
        "--raw-output",
        action="store_true",
        help="write untrusted remote bytes unchanged; unsafe for terminals",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)
    parsed = parser.parse_args(argv)
    if parsed.command and parsed.command[0] == "--":
        parsed.command = parsed.command[1:]
    if not parsed.command:
        parser.error("a command is required after --")
    return parsed


def build_environment(names: Sequence[str], source: Mapping[str, str]) -> dict[str, str]:
    environment: dict[str, str] = {}
    for name in names:
        if not ENVIRONMENT_NAME.fullmatch(name):
            raise ValueError(f"invalid environment variable name: {name}")
        if name not in source:
            raise ValueError(f"environment variable is not set: {name}")
        environment[name] = source[name]
    return environment


class OutputTarget:
    def __init__(self, text: TextIO, binary: BinaryIO, *, raw: bool) -> None:
        self.text = text
        self.binary = binary
        self.raw = raw
        self.renderer = None if raw else SafeOutputRenderer()

    def write(self, data: bytes) -> None:
        if self.raw:
            self.binary.write(data)
            self.binary.flush()
            return
        renderer = self.renderer
        if renderer is None:
            raise RuntimeError("safe output renderer is unavailable")
        self.text.write(renderer.feed(data))
        self.text.flush()

    def finish(self) -> None:
        if self.raw:
            return
        renderer = self.renderer
        if renderer is None:
            raise RuntimeError("safe output renderer is unavailable")
        self.text.write(renderer.feed(b"", final=True))
        self.text.flush()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        environment = build_environment(args.pass_env, os.environ)
    except ValueError as error:
        print(f"configuration error: {error}", file=sys.stderr)
        return 64

    stdout = OutputTarget(sys.stdout, sys.stdout.buffer, raw=args.raw_output)
    stderr = OutputTarget(sys.stderr, sys.stderr.buffer, raw=args.raw_output)
    client = RpcClient(
        host=args.host,
        port=args.port,
        connect_timeout=args.connect_timeout,
        deadline=args.deadline,
        max_output_bytes=args.max_output_bytes,
    )

    try:
        return client.run(
            command=args.command[0],
            args=args.command[1:],
            cwd=args.cwd,
            env=environment,
            stdout=stdout.write,
            stderr=stderr.write,
        )
    except TimeoutError:
        print("RPC deadline exceeded", file=sys.stderr)
        return 75
    except ProtocolError:
        print("remote endpoint returned an invalid or unsupported RPC response", file=sys.stderr)
        return 76
    except OutputLimitError:
        print("remote output exceeded the configured limit", file=sys.stderr)
        return 74
    except RemoteCommandError:
        print("remote command could not be started", file=sys.stderr)
        return 69
    except OSError:
        print("could not connect to the local RPC endpoint", file=sys.stderr)
        return 69
    finally:
        stdout.finish()
        stderr.finish()


if __name__ == "__main__":
    raise SystemExit(main())
