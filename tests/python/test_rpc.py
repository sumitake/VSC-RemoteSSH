# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import Iterable

import msgpack
import pytest

from remote_ssh_tunnel.rpc import (
    OutputLimitError,
    ProtocolError,
    RpcClient,
    UnsupportedProtocolError,
)


class ScriptedSocket:
    def __init__(self, messages: Iterable[object]) -> None:
        self.chunks = [b"".join(msgpack.packb(message, use_bin_type=True) for message in messages)]
        self.sent: list[object] = []
        self.closed = False
        self.timeouts: list[float] = []

    def sendall(self, payload: bytes) -> None:
        self.sent.append(msgpack.unpackb(payload, raw=False))

    def recv(self, _size: int) -> bytes:
        return self.chunks.pop(0) if self.chunks else b""

    def settimeout(self, timeout: float) -> None:
        self.timeouts.append(timeout)

    def close(self) -> None:
        self.closed = True


def scripted_client(messages: list[object], **kwargs: object) -> tuple[RpcClient, ScriptedSocket]:
    sock = ScriptedSocket(messages)
    client = RpcClient(
        port=45001,
        socket_factory=lambda *_args, **_kwargs: sock,
        request_id_factory=lambda: 7,
        **kwargs,
    )
    return client, sock


def test_runs_a_direct_command_and_routes_advertised_streams() -> None:
    stdout: list[bytes] = []
    stderr: list[bytes] = []
    client, sock = scripted_client(
        [
            {
                "id": None,
                "method": "version",
                "params": {"version": "1.2.3", "protocol_version": 5},
            },
            {
                "id": None,
                "method": "streams_started",
                "params": {"for_request_id": 7, "stream_ids": [10, 11, 12]},
            },
            {"id": None, "method": "stream_data", "params": {"stream": 11, "segment": b"hello\n"}},
            {
                "id": None,
                "method": "stream_data",
                "params": {"stream": 12, "segment": b"warning\n"},
            },
            {"id": None, "method": "stream_ended", "params": {"stream": 11}},
            {"id": None, "method": "stream_ended", "params": {"stream": 12}},
            {"id": 7, "result": {"exit_code": 0, "message": "ok"}},
        ]
    )

    exit_code = client.run(
        command="/usr/bin/example",
        args=["one", "two words"],
        cwd=None,
        env={},
        stdout=stdout.append,
        stderr=stderr.append,
    )

    assert exit_code == 0
    assert stdout == [b"hello\n"]
    assert stderr == [b"warning\n"]
    assert sock.sent[0] == {
        "id": None,
        "method": "version",
        "params": {"version": "1.2.3", "protocol_version": 5},
    }
    assert sock.sent[1] == {
        "id": 7,
        "method": "spawn",
        "params": {
            "command": "/usr/bin/example",
            "args": ["one", "two words"],
            "cwd": None,
            "env": {},
        },
    }
    assert sock.sent[2] == {"id": None, "method": "stream_ended", "params": {"stream": 10}}
    assert sock.closed is True


def test_fails_closed_on_an_unsupported_protocol() -> None:
    client, sock = scripted_client(
        [
            {
                "id": None,
                "method": "version",
                "params": {"version": "1.2.3", "protocol_version": 6},
            }
        ]
    )

    with pytest.raises(UnsupportedProtocolError):
        client.run(command="true", args=[], stdout=lambda _data: None, stderr=lambda _data: None)

    assert sock.closed is True


def test_rejects_stream_data_before_streams_are_advertised() -> None:
    client, sock = scripted_client(
        [
            {
                "id": None,
                "method": "version",
                "params": {"version": "1.2.3", "protocol_version": 5},
            },
            {"id": None, "method": "stream_data", "params": {"stream": 11, "segment": b"bad"}},
        ]
    )

    with pytest.raises(ProtocolError, match="stream"):
        client.run(command="true", args=[], stdout=lambda _data: None, stderr=lambda _data: None)

    assert sock.closed is True


def test_rejects_duplicate_stream_start_messages() -> None:
    client, _sock = scripted_client(
        [
            {
                "id": None,
                "method": "version",
                "params": {"version": "1.2.3", "protocol_version": 5},
            },
            {
                "id": None,
                "method": "streams_started",
                "params": {"for_request_id": 7, "stream_ids": [10, 11, 12]},
            },
            {
                "id": None,
                "method": "streams_started",
                "params": {"for_request_id": 7, "stream_ids": [20, 21, 22]},
            },
        ]
    )

    with pytest.raises(ProtocolError, match="duplicate"):
        client.run(command="true", args=[], stdout=lambda _data: None, stderr=lambda _data: None)


def test_enforces_the_aggregate_output_limit_before_writing() -> None:
    output: list[bytes] = []
    client, sock = scripted_client(
        [
            {
                "id": None,
                "method": "version",
                "params": {"version": "1.2.3", "protocol_version": 5},
            },
            {
                "id": None,
                "method": "streams_started",
                "params": {"for_request_id": 7, "stream_ids": [10, 11, 12]},
            },
            {"id": None, "method": "stream_data", "params": {"stream": 11, "segment": b"12345"}},
        ],
        max_output_bytes=4,
    )

    with pytest.raises(OutputLimitError):
        client.run(command="true", args=[], stdout=output.append, stderr=output.append)

    assert output == []
    assert sock.closed is True


def test_rejects_non_byte_stream_payloads() -> None:
    client, _sock = scripted_client(
        [
            {
                "id": None,
                "method": "version",
                "params": {"version": "1.2.3", "protocol_version": 5},
            },
            {
                "id": None,
                "method": "streams_started",
                "params": {"for_request_id": 7, "stream_ids": [10, 11, 12]},
            },
            {"id": None, "method": "stream_data", "params": {"stream": 11, "segment": "text"}},
        ]
    )

    with pytest.raises(ProtocolError, match="bytes"):
        client.run(command="true", args=[], stdout=lambda _data: None, stderr=lambda _data: None)


def test_rejects_streams_for_another_request() -> None:
    client, _sock = scripted_client(
        [
            {
                "id": None,
                "method": "version",
                "params": {"version": "1.2.3", "protocol_version": 5},
            },
            {
                "id": None,
                "method": "streams_started",
                "params": {"for_request_id": 8, "stream_ids": [10, 11, 12]},
            },
        ]
    )

    with pytest.raises(ProtocolError, match="request"):
        client.run(command="true", args=[], stdout=lambda _data: None, stderr=lambda _data: None)


def test_rejects_invalid_direct_api_inputs_before_connecting() -> None:
    with pytest.raises(ValueError, match="timeouts"):
        RpcClient(port=45001, deadline=float("nan"))

    client, sock = scripted_client([])
    with pytest.raises(ValueError, match="cwd"):
        client.run(
            command="true",
            args=[],
            cwd="bad\x00path",
            stdout=lambda _data: None,
            stderr=lambda _data: None,
        )
    assert sock.closed is False
