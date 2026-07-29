from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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
        _completed(0, b"Ubuntu\x00"),
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


# ---------------------------------------------------------------------------
# get_wsl_ip_address
# ---------------------------------------------------------------------------


@patch("lvk_paluworld_server_manager.server.subprocess.run")
def test_get_wsl_ip_address_returns_first_ip(mock_run: MagicMock) -> None:
    mock_run.return_value = _completed(0, "172.20.16.1 10.255.255.254 \n")

    result = server.get_wsl_ip_address()

    assert result == "172.20.16.1"
    args, kwargs = mock_run.call_args
    assert args[0] == ["wsl.exe", "-d", "Ubuntu", "hostname", "-I"]
    assert kwargs["timeout"] == 15


@patch("lvk_paluworld_server_manager.server.subprocess.run")
def test_get_wsl_ip_address_returns_none_when_command_fails(
    mock_run: MagicMock,
) -> None:
    mock_run.return_value = _completed(1, "")

    assert server.get_wsl_ip_address() is None


@patch("lvk_paluworld_server_manager.server.subprocess.run")
def test_get_wsl_ip_address_returns_none_on_oserror(mock_run: MagicMock) -> None:
    mock_run.side_effect = OSError("wsl.exe not found")

    assert server.get_wsl_ip_address() is None


@patch("lvk_paluworld_server_manager.server.socket.socket")
def test_get_windows_host_ip_address_returns_local_ip(mock_socket: MagicMock) -> None:
    mock_sock = MagicMock()
    mock_sock.getsockname.return_value = ("192.168.0.123", 0)
    mock_socket.return_value.__enter__.return_value = mock_sock

    assert server.get_windows_host_ip_address() == "192.168.0.123"


@patch("lvk_paluworld_server_manager.server.socket.socket")
def test_get_windows_host_ip_address_returns_none_on_error(mock_socket: MagicMock) -> None:
    mock_socket.side_effect = OSError("network unavailable")

    assert server.get_windows_host_ip_address() is None


@patch("lvk_paluworld_server_manager.server.urllib.request.urlopen")
def test_get_public_ip_address_returns_ip(mock_urlopen: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.read.return_value = b"203.0.113.45"
    mock_urlopen.return_value.__enter__.return_value = mock_response

    assert server.get_public_ip_address() == "203.0.113.45"


@patch("lvk_paluworld_server_manager.server.urllib.request.urlopen")
def test_get_public_ip_address_returns_none_on_failure(mock_urlopen: MagicMock) -> None:
    mock_urlopen.side_effect = Exception("timeout")

    assert server.get_public_ip_address() is None


# ---------------------------------------------------------------------------
# detect_windows_build / is_mirrored_mode_supported
# ---------------------------------------------------------------------------


@patch("lvk_paluworld_server_manager.server.sys.platform", "win32")
@patch("lvk_paluworld_server_manager.server.winreg", create=True)
def test_detect_windows_build_reads_registry(mock_winreg: MagicMock) -> None:

    mock_winreg.HKEY_LOCAL_MACHINE = 0
    mock_winreg.OpenKey.return_value = MagicMock()
    mock_winreg.QueryValueEx.return_value = ("22621", 1)
    mock_winreg.CloseKey.return_value = None

    # Patch the import inside the function via the module-level name
    with patch.dict("sys.modules", {"winreg": mock_winreg}):
        build = server.detect_windows_build()

    assert isinstance(build, int)


def test_is_mirrored_mode_supported_true_for_high_build() -> None:
    with patch("lvk_paluworld_server_manager.server.detect_windows_build", return_value=22621):
        assert server.is_mirrored_mode_supported() is True


def test_is_mirrored_mode_supported_false_for_low_build() -> None:
    with patch("lvk_paluworld_server_manager.server.detect_windows_build", return_value=19041):
        assert server.is_mirrored_mode_supported() is False


# ---------------------------------------------------------------------------
# read_wslconfig / is_mirrored_mode_enabled
# ---------------------------------------------------------------------------


def test_is_mirrored_mode_enabled_true_when_set(tmp_path: Path) -> None:
    cfg = tmp_path / ".wslconfig"
    cfg.write_text("[wsl2]\nnetworkingMode=mirrored\n", encoding="utf-8")

    with patch("lvk_paluworld_server_manager.server._WSLCONFIG_PATH", cfg):
        assert server.is_mirrored_mode_enabled() is True


def test_is_mirrored_mode_enabled_false_when_nat(tmp_path: Path) -> None:
    cfg = tmp_path / ".wslconfig"
    cfg.write_text("[wsl2]\nnetworkingMode=nat\n", encoding="utf-8")

    with patch("lvk_paluworld_server_manager.server._WSLCONFIG_PATH", cfg):
        assert server.is_mirrored_mode_enabled() is False


def test_is_mirrored_mode_enabled_false_when_file_missing(tmp_path: Path) -> None:
    with patch(
        "lvk_paluworld_server_manager.server._WSLCONFIG_PATH",
        tmp_path / ".wslconfig",
    ):
        assert server.is_mirrored_mode_enabled() is False


# ---------------------------------------------------------------------------
# enable_mirrored_mode
# ---------------------------------------------------------------------------


@patch("lvk_paluworld_server_manager.server.subprocess.run")
def test_enable_mirrored_mode_writes_wslconfig(
    mock_run: MagicMock, tmp_path: Path
) -> None:
    cfg = tmp_path / ".wslconfig"
    mock_run.return_value = _completed(0)

    with patch("lvk_paluworld_server_manager.server._WSLCONFIG_PATH", cfg):
        server.enable_mirrored_mode()

    assert cfg.exists()
    content = cfg.read_text(encoding="utf-8")
    assert "networkingmode = mirrored" in content.lower()

    # Verify wsl --shutdown was called
    args, _ = mock_run.call_args
    assert "wsl.exe" in args[0]
    assert "--shutdown" in args[0]


@patch("lvk_paluworld_server_manager.server.subprocess.run")
def test_enable_mirrored_mode_overwrites_existing_value(
    mock_run: MagicMock, tmp_path: Path
) -> None:
    cfg = tmp_path / ".wslconfig"
    cfg.write_text("[wsl2]\nnetworkingMode=nat\n", encoding="utf-8")
    mock_run.return_value = _completed(0)

    with patch("lvk_paluworld_server_manager.server._WSLCONFIG_PATH", cfg):
        server.enable_mirrored_mode()

    content = cfg.read_text(encoding="utf-8")
    assert "nat" not in content.lower()
    assert "networkingmode = mirrored" in content.lower()


# ---------------------------------------------------------------------------
# check_firewall_rule / add_firewall_rule
# ---------------------------------------------------------------------------


@patch("lvk_paluworld_server_manager.server.subprocess.run")
def test_check_firewall_rule_true_when_rule_exists(mock_run: MagicMock) -> None:
    mock_run.return_value = _completed(0)
    assert server.check_firewall_rule() is True
    args, _ = mock_run.call_args
    assert "netsh" in args[0]
    assert server.FIREWALL_RULE_NAME in " ".join(args[0])


@patch("lvk_paluworld_server_manager.server.subprocess.run")
def test_check_firewall_rule_false_when_rule_missing(mock_run: MagicMock) -> None:
    mock_run.return_value = _completed(1)
    assert server.check_firewall_rule() is False


@patch("lvk_paluworld_server_manager.server.subprocess.run")
def test_check_firewall_rule_false_on_oserror(mock_run: MagicMock) -> None:
    mock_run.side_effect = OSError("netsh not found")
    assert server.check_firewall_rule() is False


@patch("lvk_paluworld_server_manager.server.subprocess.run")
def test_add_firewall_rule_returns_true_on_success(mock_run: MagicMock) -> None:
    mock_run.return_value = _completed(0)
    assert server.add_firewall_rule() is True
    args, _ = mock_run.call_args
    joined = " ".join(args[0])
    assert "netsh" in joined
    assert "add" in joined
    assert str(server.PALWORLD_PORT) in joined


@patch("lvk_paluworld_server_manager.server.subprocess.run")
def test_add_firewall_rule_returns_false_on_failure(mock_run: MagicMock) -> None:
    mock_run.return_value = _completed(1)
    assert server.add_firewall_rule() is False


# ---------------------------------------------------------------------------
# check_socat_installed
# ---------------------------------------------------------------------------


@patch("lvk_paluworld_server_manager.server._run_wsl_bash_check")
def test_check_socat_installed_true(mock_check: MagicMock) -> None:
    mock_check.return_value = True
    assert server.check_socat_installed() is True
    mock_check.assert_called_once_with("command -v socat >/dev/null 2>&1")


@patch("lvk_paluworld_server_manager.server._run_wsl_bash_check")
def test_check_socat_installed_false(mock_check: MagicMock) -> None:
    mock_check.return_value = False
    assert server.check_socat_installed() is False


# ---------------------------------------------------------------------------
# NetworkSetupResult
# ---------------------------------------------------------------------------


def test_network_setup_result_needs_setup_when_no_firewall() -> None:
    r = server.NetworkSetupResult(
        mirrored_mode_supported=True,
        mirrored_mode_enabled=True,
        firewall_rule_exists=False,
        socat_installed=False,
        is_admin=True,
    )
    assert r.needs_setup is True
    assert any("防火牆" in a for a in r.pending_actions)


def test_network_setup_result_needs_setup_when_mirrored_not_enabled() -> None:
    r = server.NetworkSetupResult(
        mirrored_mode_supported=True,
        mirrored_mode_enabled=False,
        firewall_rule_exists=True,
        socat_installed=False,
        is_admin=True,
    )
    assert r.needs_setup is True
    assert any("mirrored" in a.lower() or "networkingmode" in a.lower() for a in r.pending_actions)


def test_network_setup_result_no_setup_needed_when_all_ok() -> None:
    r = server.NetworkSetupResult(
        mirrored_mode_supported=True,
        mirrored_mode_enabled=True,
        firewall_rule_exists=True,
        socat_installed=False,
        is_admin=True,
    )
    assert r.needs_setup is False
    assert r.pending_actions == []


def test_network_setup_result_socat_notice_when_unsupported_and_missing() -> None:
    r = server.NetworkSetupResult(
        mirrored_mode_supported=False,
        mirrored_mode_enabled=False,
        firewall_rule_exists=True,
        socat_installed=False,
        is_admin=True,
    )
    assert any("socat" in a.lower() for a in r.pending_actions)


# ---------------------------------------------------------------------------
# check_network_setup (integration-style, all helpers mocked)
# ---------------------------------------------------------------------------


@patch("lvk_paluworld_server_manager.server.is_admin")
@patch("lvk_paluworld_server_manager.server.check_socat_installed")
@patch("lvk_paluworld_server_manager.server.check_firewall_rule")
@patch("lvk_paluworld_server_manager.server.is_mirrored_mode_enabled")
@patch("lvk_paluworld_server_manager.server.is_mirrored_mode_supported")
def test_check_network_setup_mirrored_supported_and_enabled(
    mock_supported: MagicMock,
    mock_enabled: MagicMock,
    mock_fw: MagicMock,
    mock_socat: MagicMock,
    mock_admin: MagicMock,
) -> None:
    mock_supported.return_value = True
    mock_enabled.return_value = True
    mock_fw.return_value = True
    mock_admin.return_value = True

    result = server.check_network_setup()

    assert result.mirrored_mode_supported is True
    assert result.mirrored_mode_enabled is True
    assert result.firewall_rule_exists is True
    assert result.needs_setup is False
    # socat check skipped when mirrored mode is supported
    mock_socat.assert_not_called()


# ---------------------------------------------------------------------------
# test_external_connectivity
# ---------------------------------------------------------------------------


@patch("lvk_paluworld_server_manager.server.urllib.request.urlopen")
def test_external_connectivity_true_when_any_endpoint_reachable(
    mock_urlopen: MagicMock,
) -> None:
    mock_response = MagicMock()
    mock_response.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_response

    result = server.test_external_connectivity()
    assert result is True


@patch("lvk_paluworld_server_manager.server.urllib.request.urlopen")
def test_external_connectivity_false_when_all_endpoints_fail(
    mock_urlopen: MagicMock,
) -> None:
    mock_urlopen.side_effect = Exception("Network error")

    result = server.test_external_connectivity()
    assert result is False


# ---------------------------------------------------------------------------
# get_all_diagnostic_info
# ---------------------------------------------------------------------------


@patch("lvk_paluworld_server_manager.server.test_external_connectivity")
@patch("lvk_paluworld_server_manager.server.check_network_setup")
@patch("lvk_paluworld_server_manager.server.check_environment")
@patch("lvk_paluworld_server_manager.server.check_firewall_rule")
@patch("lvk_paluworld_server_manager.server.get_public_ip_address")
@patch("lvk_paluworld_server_manager.server.get_windows_host_ip_address")
@patch("lvk_paluworld_server_manager.server.get_wsl_ip_address")
def test_get_all_diagnostic_info_collects_all_data(
    mock_wsl_ip: MagicMock,
    mock_windows_ip: MagicMock,
    mock_public_ip: MagicMock,
    mock_firewall: MagicMock,
    mock_env: MagicMock,
    mock_network: MagicMock,
    mock_connectivity: MagicMock,
) -> None:
    mock_wsl_ip.return_value = "172.20.16.1"
    mock_windows_ip.return_value = "192.168.1.100"
    mock_public_ip.return_value = "203.0.113.42"
    mock_firewall.return_value = True
    mock_env.return_value = server.EnvironmentCheckResult(
        wsl_available=True,
        steamcmd_installed=True,
        palserver_installed=True,
    )
    mock_network.return_value = server.NetworkSetupResult(
        mirrored_mode_supported=True,
        mirrored_mode_enabled=True,
        firewall_rule_exists=True,
        socat_installed=False,
        is_admin=True,
    )
    mock_connectivity.return_value = True

    info = server.get_all_diagnostic_info()

    assert info.wsl_ip == "172.20.16.1"
    assert info.windows_ip == "192.168.1.100"
    assert info.public_ip == "203.0.113.42"
    assert info.firewall_rule_exists is True
    assert info.environment_check.wsl_available is True
    assert info.environment_check.steamcmd_installed is True
    assert info.environment_check.palserver_installed is True
    assert info.network_setup.mirrored_mode_supported is True
    assert info.network_setup.mirrored_mode_enabled is True
    assert info.external_connectivity is True


# ---------------------------------------------------------------------------
# is_server_process_running
# ---------------------------------------------------------------------------


@patch("lvk_paluworld_server_manager.server.subprocess.run")
def test_is_server_process_running_true_when_pgrep_finds_process(
    mock_run: MagicMock,
) -> None:
    mock_run.return_value = _completed(0, "1234\n")

    assert server.is_server_process_running() is True
    args, kwargs = mock_run.call_args
    assert args[0][:3] == ["wsl.exe", "-d", "Ubuntu"]
    assert "pgrep" in args[0]
    assert server.STOP_PROCESS_PATTERN in args[0]
    assert kwargs["timeout"] == 15


@patch("lvk_paluworld_server_manager.server.subprocess.run")
def test_is_server_process_running_false_when_pgrep_finds_nothing(
    mock_run: MagicMock,
) -> None:
    mock_run.return_value = _completed(1, "")

    assert server.is_server_process_running() is False


@patch("lvk_paluworld_server_manager.server.subprocess.run")
def test_is_server_process_running_true_on_error_to_be_safe(
    mock_run: MagicMock,
) -> None:
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="wsl.exe", timeout=15)

    # When the check itself fails, err on the side of caution and treat the
    # server as running so a write is never attempted blindly.
    assert server.is_server_process_running() is True


# ---------------------------------------------------------------------------
# get_save_games_windows_path
# ---------------------------------------------------------------------------


@patch("lvk_paluworld_server_manager.server._run_wsl_capture")
def test_get_save_games_windows_path_builds_unc_path(mock_capture: MagicMock) -> None:
    mock_capture.return_value = "/home/lolivk"

    result = server.get_save_games_windows_path()

    assert str(result) == (
        r"\\wsl$\Ubuntu\home\lolivk\.local\share\Steam\steamapps\common\PalServer"
        r"\Pal\Saved\SaveGames\0"
    )


@patch("lvk_paluworld_server_manager.server._run_wsl_capture")
def test_get_save_games_windows_path_raises_when_home_unresolvable(
    mock_capture: MagicMock,
) -> None:
    mock_capture.return_value = None

    with pytest.raises(OSError):
        server.get_save_games_windows_path()


@patch("lvk_paluworld_server_manager.server.os.startfile", create=True)
@patch("lvk_paluworld_server_manager.server.sys.platform", "win32")
def test_open_in_file_manager_opens_windows_path(mock_startfile: MagicMock) -> None:
    backup_folder = Path(r"\\wsl$\Ubuntu\home\lolivk\Backups")

    server.open_in_file_manager(backup_folder)

    mock_startfile.assert_called_once_with(str(backup_folder))


# ---------------------------------------------------------------------------
# _run_wsl_capture
# ---------------------------------------------------------------------------


@patch("lvk_paluworld_server_manager.server.subprocess.run")
def test_run_wsl_capture_returns_stripped_stdout(mock_run: MagicMock) -> None:
    mock_run.return_value = _completed(0, "  /home/lolivk  \n")

    assert server._run_wsl_capture(["echo", "$HOME"]) == "/home/lolivk"


@patch("lvk_paluworld_server_manager.server.subprocess.run")
def test_run_wsl_capture_returns_none_on_failure(mock_run: MagicMock) -> None:
    mock_run.return_value = _completed(1, "")

    assert server._run_wsl_capture(["echo", "$HOME"]) is None


@patch("lvk_paluworld_server_manager.server.subprocess.run")
def test_run_wsl_capture_returns_none_on_exception(mock_run: MagicMock) -> None:
    mock_run.side_effect = OSError("wsl.exe not found")

    assert server._run_wsl_capture(["echo", "$HOME"]) is None
