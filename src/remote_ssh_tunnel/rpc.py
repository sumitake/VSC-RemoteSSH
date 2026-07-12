# SPDX-License-Identifier: MIT

from __future__ import annotations

import math
import secrets
import socket
import time
from collections.abc import Callable, Sequence
from typing import Any, Protocol

import msgpack

SUPPORTED_PROTOCOL = 5
DEFAULT_MAX_FRAME_BYTES = 1024 * 1024
DEFAULT_MAX_OUTPUT_BYTES = 16 * 1024 * 1024


class SocketLike(Protocol):
    def sendall(self, payload: bytes) -> None: ...

    def recv(self, size: int) -> bytes: ...

    def settimeout(self, timeout: float) -> None: ...

    def close(self) -> None: ...


class RpcError(Exception):
    """Base class for local RPC failures."""


class ProtocolError(RpcError):
    """Raised when the remote endpoint violates the expected protocol."""


class UnsupportedProtocolError(ProtocolError):
    """Raised when the endpoint advertises an unsupported protocol version."""


class OutputLimitError(RpcError):
    """Raised before remote output would exceed the configured aggregate limit."""


class RemoteCommandError(RpcError):
    """Raised when the endpoint reports a remote spawn failure."""


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_port(port: int) -> int:
    if not _is_int(port) or not 1 <= port <= 65535:
        raise ValueError("port must be an integer from 1 to 65535")
    return port


class RpcClient:
    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int,
        connect_timeout: float = 10.0,
        deadline: float = 300.0,
        max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
        socket_factory: Callable[..., SocketLike] = socket.create_connection,
        request_id_factory: Callable[[], int] = lambda: secrets.randbelow(2**31 - 1) + 1,
    ) -> None:
        if (
            not isinstance(host, str)
            or not host
            or len(host) > 255
            or any(ord(character) < 0x20 for character in host)
        ):
            raise ValueError("host must be a non-empty address")
        self.host = host
        self.port = _validate_port(port)
        if (
            isinstance(connect_timeout, bool)
            or not isinstance(connect_timeout, (int, float))
            or not math.isfinite(connect_timeout)
            or connect_timeout <= 0
            or isinstance(deadline, bool)
            or not isinstance(deadline, (int, float))
            or not math.isfinite(deadline)
            or deadline <= 0
        ):
            raise ValueError("timeouts must be positive")
        if not _is_int(max_frame_bytes) or not 1024 <= max_frame_bytes <= 16 * 1024 * 1024:
            raise ValueError("max_frame_bytes must be from 1 KiB to 16 MiB")
        if not _is_int(max_output_bytes) or max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive")
        self.connect_timeout = connect_timeout
        self.deadline = deadline
        self.max_frame_bytes = max_frame_bytes
        self.max_output_bytes = max_output_bytes
        self.socket_factory = socket_factory
        self.request_id_factory = request_id_factory

    def run(
        self,
        *,
        command: str,
        args: Sequence[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        stdout: Callable[[bytes], None],
        stderr: Callable[[bytes], None],
    ) -> int:
        if not isinstance(command, str) or not command or "\x00" in command:
            raise ValueError("command must be a non-empty executable path or name")
        if isinstance(args, (str, bytes)) or any(
            not isinstance(argument, str) or "\x00" in argument for argument in args
        ):
            raise ValueError("arguments must be strings without NUL bytes")
        if cwd is not None and (not isinstance(cwd, str) or "\x00" in cwd):
            raise ValueError("cwd must be a string without NUL bytes")
        environment = {} if env is None else dict(env)
        if any(
            not isinstance(key, str)
            or not isinstance(value, str)
            or "\x00" in key
            or "\x00" in value
            for key, value in environment.items()
        ):
            raise ValueError("environment names and values must be strings without NUL bytes")

        sock = self.socket_factory((self.host, self.port), timeout=self.connect_timeout)
        unpacker = msgpack.Unpacker(
            raw=False,
            strict_map_key=True,
            max_buffer_size=self.max_frame_bytes,
            max_str_len=min(self.max_frame_bytes, 64 * 1024),
            max_bin_len=self.max_frame_bytes,
            max_array_len=64,
            max_map_len=64,
            max_ext_len=0,
        )
        end_time = time.monotonic() + self.deadline
        try:
            hello = self._receive(sock, unpacker, end_time)
            remote_version = self._validate_hello(hello)
            self._send(
                sock,
                {
                    "id": None,
                    "method": "version",
                    "params": {"version": remote_version, "protocol_version": SUPPORTED_PROTOCOL},
                },
            )

            request_id = self.request_id_factory()
            if not _is_int(request_id) or not 1 <= request_id < 2**31:
                raise ValueError("request_id_factory returned an invalid ID")
            self._send(
                sock,
                {
                    "id": request_id,
                    "method": "spawn",
                    "params": {
                        "command": command,
                        "args": list(args),
                        "cwd": cwd,
                        "env": environment,
                    },
                },
            )
            return self._process_messages(
                sock,
                unpacker,
                end_time,
                request_id=request_id,
                stdout=stdout,
                stderr=stderr,
            )
        finally:
            sock.close()

    def _receive(
        self,
        sock: SocketLike,
        unpacker: msgpack.Unpacker,
        end_time: float,
    ) -> object:
        while True:
            try:
                return next(unpacker)
            except StopIteration:
                pass
            except (msgpack.BufferFull, ValueError, TypeError, msgpack.FormatError) as error:
                raise ProtocolError("invalid or oversized MessagePack frame") from error

            remaining = end_time - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("RPC deadline exceeded")
            sock.settimeout(min(remaining, 5.0))
            try:
                chunk = sock.recv(64 * 1024)
            except TimeoutError:
                continue
            if not chunk:
                raise ProtocolError("RPC endpoint closed before returning a result")
            try:
                unpacker.feed(chunk)
            except (msgpack.BufferFull, ValueError, TypeError) as error:
                raise ProtocolError("invalid or oversized MessagePack frame") from error

    @staticmethod
    def _send(sock: SocketLike, message: dict[str, Any]) -> None:
        sock.sendall(msgpack.packb(message, use_bin_type=True))

    @staticmethod
    def _validate_hello(message: object) -> str:
        if not isinstance(message, dict):
            raise ProtocolError("RPC hello must be a map")
        if (
            set(message) != {"id", "method", "params"}
            or message.get("id") is not None
            or message.get("method") != "version"
            or not isinstance(message.get("params"), dict)
        ):
            raise ProtocolError("RPC hello has an invalid version envelope")
        params = message["params"]
        if set(params) != {"version", "protocol_version"}:
            raise ProtocolError("RPC hello has unexpected version fields")
        version = params.get("version")
        protocol = params.get("protocol_version")
        if (
            not isinstance(version, str)
            or not version
            or len(version) > 128
            or any(ord(character) < 0x20 for character in version)
        ):
            raise ProtocolError("RPC hello has an invalid software version")
        if not _is_int(protocol):
            raise ProtocolError("RPC hello has an invalid protocol version")
        if protocol != SUPPORTED_PROTOCOL:
            raise UnsupportedProtocolError(f"unsupported RPC protocol version: {protocol}")
        return version

    def _process_messages(
        self,
        sock: SocketLike,
        unpacker: msgpack.Unpacker,
        end_time: float,
        *,
        request_id: int,
        stdout: Callable[[bytes], None],
        stderr: Callable[[bytes], None],
    ) -> int:
        streams: tuple[int, int, int] | None = None
        ended: set[int] = set()
        output_bytes = 0

        while True:
            message = self._receive(sock, unpacker, end_time)
            if not isinstance(message, dict):
                raise ProtocolError("RPC message must be a map")

            if message.get("id") == request_id:
                if "error" in message:
                    raise RemoteCommandError("remote command could not be started")
                if "result" not in message:
                    raise ProtocolError("RPC response is missing a result")
                if streams is None or not {streams[1], streams[2]}.issubset(ended):
                    raise ProtocolError("RPC response arrived before output streams ended")
                return self._parse_exit_code(message["result"])

            if set(message) != {"id", "method", "params"} or message.get("id") is not None:
                raise ProtocolError("RPC notification has an invalid envelope")
            method = message.get("method")
            params = message.get("params")
            if not isinstance(method, str) or not isinstance(params, dict):
                raise ProtocolError("RPC notification has an invalid shape")

            if method == "streams_started":
                if streams is not None:
                    raise ProtocolError("duplicate streams_started notification")
                if set(params) != {"for_request_id", "stream_ids"}:
                    raise ProtocolError("streams_started has unexpected fields")
                if params.get("for_request_id") != request_id:
                    raise ProtocolError("streams_started references another request")
                raw_streams = params.get("stream_ids")
                if (
                    not isinstance(raw_streams, list)
                    or len(raw_streams) != 3
                    or any(not _is_int(stream_id) or stream_id < 0 for stream_id in raw_streams)
                    or len(set(raw_streams)) != 3
                ):
                    raise ProtocolError("streams_started must advertise three unique stream IDs")
                streams = tuple(raw_streams)
                self._send(
                    sock,
                    {"id": None, "method": "stream_ended", "params": {"stream": streams[0]}},
                )
                continue

            if streams is None:
                raise ProtocolError("stream notification arrived before streams_started")

            expected_fields = {"stream"} if method == "stream_ended" else {"stream", "segment"}
            if set(params) != expected_fields:
                raise ProtocolError("stream notification has unexpected fields")
            stream_id = params.get("stream")
            if not _is_int(stream_id) or stream_id not in streams:
                raise ProtocolError("stream notification references an unknown stream")
            if method == "stream_ended":
                if stream_id in ended:
                    raise ProtocolError("duplicate stream_ended notification")
                ended.add(stream_id)
                continue
            if method != "stream_data":
                raise ProtocolError("RPC notification uses an unknown method")
            if stream_id in ended:
                raise ProtocolError("stream_data arrived after stream_ended")
            if stream_id == streams[0]:
                raise ProtocolError("remote endpoint sent data on the stdin stream")

            data = params.get("segment")
            if not isinstance(data, bytes):
                raise ProtocolError("stream_data payload must be bytes")
            if output_bytes + len(data) > self.max_output_bytes:
                raise OutputLimitError("remote output exceeded the configured limit")
            output_bytes += len(data)
            (stdout if stream_id == streams[1] else stderr)(data)

    @staticmethod
    def _parse_exit_code(result: object) -> int:
        if not isinstance(result, dict) or set(result) != {"exit_code", "message"}:
            raise ProtocolError("RPC response has an invalid result shape")
        message = result.get("message")
        if not isinstance(message, str) or len(message) > 4096:
            raise ProtocolError("RPC response has an invalid status message")
        exit_code = result.get("exit_code")
        if not _is_int(exit_code) or not 0 <= exit_code <= 255:
            raise ProtocolError("RPC response has an invalid exit code")
        return exit_code
