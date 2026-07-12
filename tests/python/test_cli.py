# SPDX-License-Identifier: MIT

import pytest

from remote_ssh_tunnel.cli import build_environment, parse_args


def test_parses_a_direct_command_without_a_shell() -> None:
    args = parse_args(["--port", "2200", "--", "/usr/bin/id", "-un"])

    assert args.command == ["/usr/bin/id", "-un"]
    assert args.host == "127.0.0.1"
    assert args.raw_output is False


def test_passes_only_named_environment_values() -> None:
    env = build_environment(["LANG"], {"LANG": "C.UTF-8", "SECRET": "not-forwarded"})

    assert env == {"LANG": "C.UTF-8"}


def test_missing_named_environment_value_is_an_error() -> None:
    with pytest.raises(ValueError, match="MISSING"):
        build_environment(["MISSING"], {})


def test_rejects_non_finite_deadlines() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--port", "2200", "--deadline", "nan", "--", "true"])
