from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from lvk_paluworld_server_manager import server


def test_build_start_bash_command_contains_path_and_start_command() -> None:
    command = server.build_start_bash_command()
    assert server.PALSERVER_PATH in command
    assert server.START_COMMAND in command
    assert command == f"cd {server.PALSERVER_PATH} && {server.START_COMMAND}"


def test_build_powershell_args_wraps_bash_command_with_wsl() -> None:
    args = server.build_powershell_args("cd foo && ./bar.sh")
    assert args[0] == "powershell.exe"
    assert "-NoExit" in args
    assert args[-1] == 'wsl bash -c "cd foo && ./bar.sh"'


def test_build_background_args_wraps_bash_command_without_no_exit() -> None:
    args = server.build_background_args("cd foo && ./bar.sh")
    assert args[0] == "powershell.exe"
    assert "-NoExit" not in args
    assert args[-1] == 'wsl bash -c "cd foo && ./bar.sh"'


@patch("lvk_paluworld_server_manager.server.subprocess.Popen")
def test_start_server_visible_opens_new_console(mock_popen: MagicMock) -> None:
    server.start_server_visible()

    assert mock_popen.call_count == 1
    args, kwargs = mock_popen.call_args
    assert args[0][0] == "powershell.exe"
    assert "-NoExit" in args[0]
    assert kwargs["creationflags"] == server._CREATE_NEW_CONSOLE


@patch("lvk_paluworld_server_manager.server.subprocess.Popen")
def test_start_server_background_pipes_stdout(mock_popen: MagicMock) -> None:
    server.start_server_background()

    assert mock_popen.call_count == 1
    args, kwargs = mock_popen.call_args
    assert args[0][0] == "powershell.exe"
    assert "-NoExit" not in args[0]
    assert kwargs["stdout"] == server.subprocess.PIPE
    assert kwargs["stderr"] == server.subprocess.STDOUT
    assert kwargs["text"] is True


@patch("lvk_paluworld_server_manager.server.subprocess.run")
def test_stop_server_runs_pkill_via_wsl(mock_run: MagicMock) -> None:
    server.stop_server()

    assert mock_run.call_count == 1
    args, kwargs = mock_run.call_args
    command_args = args[0]
    assert command_args[0] == "powershell.exe"
    assert "pkill -f PalServer.sh" in command_args[-1]
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True


def _completed(returncode: int, stdout: str = "") -> MagicMock:
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    return result


@patch("lvk_paluworld_server_manager.server.subprocess.run")
def test_check_wsl_available_true_when_status_and_list_succeed(
    mock_run: MagicMock,
) -> None:
    mock_run.side_effect = [
        _completed(0),
        _completed(0, "Ubuntu\x00"),
    ]

    assert server.check_wsl_available() is True


@patch("lvk_paluworld_server_manager.server.subprocess.run")
def test_check_wsl_available_false_when_status_fails(mock_run: MagicMock) -> None:
    mock_run.side_effect = [_completed(1)]

    assert server.check_wsl_available() is False
    assert mock_run.call_count == 1


@patch("lvk_paluworld_server_manager.server.subprocess.run")
def test_check_wsl_available_false_when_list_empty(mock_run: MagicMock) -> None:
    mock_run.side_effect = [_completed(0), _completed(0, "\x00")]

    assert server.check_wsl_available() is False


@patch("lvk_paluworld_server_manager.server.subprocess.run")
def test_check_wsl_available_false_on_exception(mock_run: MagicMock) -> None:
    mock_run.side_effect = OSError("wsl.exe not found")

    assert server.check_wsl_available() is False


@patch("lvk_paluworld_server_manager.server._run_wsl_bash_check")
def test_check_steamcmd_installed_delegates_to_bash_check(
    mock_check: MagicMock,
) -> None:
    mock_check.return_value = True

    assert server.check_steamcmd_installed() is True
    mock_check.assert_called_once_with(
        "command -v steamcmd >/dev/null 2>&1 || test -f ~/Steam/steamcmd.sh"
    )


@patch("lvk_paluworld_server_manager.server._run_wsl_bash_check")
def test_check_palserver_installed_delegates_to_bash_check(
    mock_check: MagicMock,
) -> None:
    mock_check.return_value = True

    assert server.check_palserver_installed() is True
    mock_check.assert_called_once_with(f"test -x {server.PALSERVER_PATH}/PalServer.sh")


@patch("lvk_paluworld_server_manager.server.subprocess.run")
def test_run_wsl_bash_check_returns_false_on_exception(mock_run: MagicMock) -> None:
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="wsl.exe", timeout=15)

    assert server._run_wsl_bash_check("true") is False


@patch("lvk_paluworld_server_manager.server.check_palserver_installed")
@patch("lvk_paluworld_server_manager.server.check_steamcmd_installed")
@patch("lvk_paluworld_server_manager.server.check_wsl_available")
def test_check_environment_short_circuits_when_wsl_unavailable(
    mock_wsl: MagicMock, mock_steamcmd: MagicMock, mock_palserver: MagicMock
) -> None:
    mock_wsl.return_value = False

    result = server.check_environment()

    assert result.wsl_available is False
    assert result.steamcmd_installed is False
    assert result.palserver_installed is False
    assert result.ok is False
    assert result.missing == [
        "WSL",
        "SteamCMD",
        "Palworld Dedicated Server (PalServer.sh)",
    ]
    mock_steamcmd.assert_not_called()
    mock_palserver.assert_not_called()


@patch("lvk_paluworld_server_manager.server.check_palserver_installed")
@patch("lvk_paluworld_server_manager.server.check_steamcmd_installed")
@patch("lvk_paluworld_server_manager.server.check_wsl_available")
def test_check_environment_ok_when_everything_available(
    mock_wsl: MagicMock, mock_steamcmd: MagicMock, mock_palserver: MagicMock
) -> None:
    mock_wsl.return_value = True
    mock_steamcmd.return_value = True
    mock_palserver.return_value = True

    result = server.check_environment()

    assert result.ok is True
    assert result.missing == []
