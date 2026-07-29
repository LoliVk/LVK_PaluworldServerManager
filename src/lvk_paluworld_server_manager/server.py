"""Helpers for launching and stopping the Palworld dedicated server via WSL.

The Palworld dedicated server is assumed to be installed inside a WSL
distribution (Linux) via SteamCMD, following the workflow::

    wsl
    cd ~/.local/share/Steam/steamapps/common/PalServer
    ./PalServer.sh

Since the GUI runs on Windows, these commands are issued through
``powershell.exe`` which in turn invokes ``wsl``. This module intentionally
has no GUI dependencies so it can be unit tested by mocking
:func:`subprocess.Popen` / :func:`subprocess.run`.
"""

from __future__ import annotations

import configparser
import ctypes
import os
import platform
import socket
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Final

#: Path to the PalServer installation inside the WSL filesystem.
PALSERVER_PATH: Final[str] = "~/.local/share/Steam/steamapps/common/PalServer"

#: Command used to start the dedicated server once inside PALSERVER_PATH.
START_COMMAND: Final[str] = "./PalServer.sh"

#: Pattern used to find the running server process so it can be stopped.
STOP_PROCESS_PATTERN: Final[str] = "PalServer.sh"

#: Windows-only flag that opens the child process in its own console window.
#: Defined defensively so importing this module on non-Windows platforms
#: (e.g. during CI on Linux/macOS) does not raise an ``AttributeError``.
_CREATE_NEW_CONSOLE: Final[int] = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)


def build_start_bash_command() -> str:
    """Build the bash command that changes into PALSERVER_PATH and starts it."""
    return f"cd {PALSERVER_PATH} && {START_COMMAND}"


def build_powershell_args(bash_command: str) -> list[str]:
    """Build the PowerShell argument list that opens a visible console.

    ``-NoExit`` keeps the PowerShell window open after the command finishes
    (or fails) so the user can read the server output or any error message.
    """
    return [
        "powershell.exe",
        "-NoExit",
        "-Command",
        f'wsl bash -c "{bash_command}"',
    ]


def build_background_args(bash_command: str) -> list[str]:
    """Build the PowerShell argument list used for background execution."""
    return [
        "powershell.exe",
        "-Command",
        f'wsl bash -c "{bash_command}"',
    ]


def start_server_visible() -> subprocess.Popen[bytes]:
    """Start the server in a new, visible PowerShell console window."""
    args = build_powershell_args(build_start_bash_command())
    return subprocess.Popen(args, creationflags=_CREATE_NEW_CONSOLE)


def start_server_background() -> subprocess.Popen[str]:
    """Start the server in the background, exposing a readable stdout pipe."""
    args = build_background_args(build_start_bash_command())
    return subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",  # 處理無法解碼的字元，避免崩潰
        bufsize=1,
    )


def stop_server() -> subprocess.CompletedProcess[str]:
    """Stop the running Palworld server inside WSL.

    Uses ``pkill`` inside WSL to find and terminate the server process by
    name. This works regardless of whether the server was started in
    "visible" or "background" mode, since it does not rely on tracking the
    launcher process tree (which in visible mode is just ``powershell.exe``).
    """
    args = [
        "powershell.exe",
        "-Command",
        f'wsl bash -c "pkill -f {STOP_PROCESS_PATTERN}"',
    ]
    return subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )


#: Path (within WSL) to the dedicated-server's world save directory.
SAVE_GAMES_PATH: Final[str] = f"{PALSERVER_PATH}/Pal/Saved/SaveGames/0"

#: Windows-visible UNC prefix used to reach files inside a WSL distribution.
_WSL_UNC_TEMPLATE: Final[str] = r"\\wsl$\{distro}"


def open_in_file_manager(path: Path) -> None:
    """Open *path* in the platform's file manager.

    The GUI ordinarily runs on Windows, where ``path`` may be a ``\\\\wsl$``
    UNC path. ``os.startfile`` hands that path directly to Explorer.
    """
    if sys.platform == "win32":
        os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def is_server_process_running(distro: str = "Ubuntu") -> bool:
    """Return ``True`` if a ``PalServer.sh`` process is currently alive in WSL.

    This is the authoritative check used before writing any save file, so it
    detects servers started outside this GUI (e.g. manually via a terminal).
    """
    try:
        result = subprocess.run(
            ["wsl.exe", "-d", distro, "pgrep", "-f", STOP_PROCESS_PATTERN],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=15,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        # If we cannot determine the state, err on the side of caution and
        # treat the server as running so a write is not attempted.
        return True


def get_save_games_windows_path(distro: str = "Ubuntu") -> Path:
    """Return the Windows-visible (``\\\\wsl$``) path to the world save directory."""
    unc_root = _WSL_UNC_TEMPLATE.format(distro=distro)
    # PALSERVER_PATH begins with "~", which expands to the distro's default
    # user home directory when accessed through the \\wsl$ UNC path as
    # "home/<user>". We resolve the actual home directory via WSL itself so
    # this does not depend on assuming a particular Linux username.
    home_result = _run_wsl_capture(["echo", "$HOME"], distro=distro)
    home = home_result.strip() if home_result else None
    if not home:
        raise OSError(f"無法取得 WSL 使用者家目錄 / Failed to resolve WSL home directory ({distro})")
    relative = SAVE_GAMES_PATH.replace("~/", "", 1)
    home_relative = home.lstrip("/")
    return Path(unc_root) / home_relative.replace("/", "\\") / relative.replace("/", "\\")


def _run_wsl_capture(args: list[str], distro: str = "Ubuntu") -> str | None:
    """Run *args* inside WSL and return stripped stdout, or ``None`` on failure."""
    try:
        result = subprocess.run(
            ["wsl.exe", "-d", distro, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=15,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None


@dataclass(frozen=True)
class EnvironmentCheckResult:
    """Result of checking that the required runtime environment is ready."""

    wsl_available: bool
    steamcmd_installed: bool
    palserver_installed: bool

    @property
    def missing(self) -> list[str]:
        """Human-readable names of the requirements that are not met."""
        missing: list[str] = []
        if not self.wsl_available:
            missing.append("WSL")
        if not self.steamcmd_installed:
            missing.append("SteamCMD")
        if not self.palserver_installed:
            missing.append("Palworld Dedicated Server (PalServer.sh)")
        return missing

    @property
    def ok(self) -> bool:
        """Whether every requirement is satisfied."""
        return not self.missing


def check_wsl_available() -> bool:
    """Check whether WSL is installed and has at least one distribution."""
    try:
        status = subprocess.run(
            ["wsl.exe", "--status"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",  # 處理無法解碼的字元
            check=False,
            timeout=15,
        )
        if status.returncode != 0:
            return False

        # wsl.exe -l -q 輸出是 UTF-16，但有時沒有 BOM，所以用 bytes 模式處理
        distros = subprocess.run(
            ["wsl.exe", "-l", "-q"],
            capture_output=True,
            text=False,  # 使用 bytes 模式來手動處理編碼
            check=False,
            timeout=15,
        )
        if distros.returncode != 0:
            return False

        # 嘗試多種 UTF-16 解碼方式
        output = None
        try:
            # 先嘗試 UTF-16-LE（小端序，Windows 常用）
            output = distros.stdout.decode("utf-16-le")
        except (UnicodeDecodeError, AttributeError):
            try:
                # 再嘗試帶 BOM 的 UTF-16
                output = distros.stdout.decode("utf-16")
            except (UnicodeDecodeError, AttributeError):
                try:
                    # 最後嘗試 UTF-8
                    output = distros.stdout.decode("utf-8", errors="replace")
                except (UnicodeDecodeError, AttributeError):
                    return False

        # 檢查是否成功解碼並移除 NUL 字元
        if output is None:
            return False
        return bool(output.replace("\x00", "").strip())
    except (OSError, subprocess.TimeoutExpired):
        return False


def _run_wsl_bash_check(bash_command: str) -> bool:
    """Run a bash command inside WSL and report whether it succeeded."""
    try:
        result = subprocess.run(
            ["wsl.exe", "bash", "-c", bash_command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",  # 處理無法解碼的字元
            check=False,
            timeout=15,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def check_steamcmd_installed() -> bool:
    """Check whether SteamCMD is installed inside WSL."""
    return _run_wsl_bash_check(
        "command -v steamcmd >/dev/null 2>&1 || test -f ~/Steam/steamcmd.sh"
    )


def check_palserver_installed() -> bool:
    """Check whether the Palworld dedicated server is installed inside WSL."""
    return _run_wsl_bash_check(f"test -x {PALSERVER_PATH}/PalServer.sh")


def get_wsl_ip_address(distro: str = "Ubuntu") -> str | None:
    """Return the IP address of a running WSL distribution.

    Executes ``wsl -d <distro> hostname -I`` and returns the first IP address
    reported.  Returns ``None`` if the command fails, times out, or produces
    no output.

    Args:
        distro: The WSL distribution name to query (default ``"Ubuntu"``).

    Returns:
        The first IP address as a string, or ``None`` on any error.
    """
    try:
        result = subprocess.run(
            ["wsl.exe", "-d", distro, "hostname", "-I"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",  # 處理無法解碼的字元
            check=False,
            timeout=15,
        )
        if result.returncode != 0:
            return None
        parts = result.stdout.strip().split()
        return parts[0] if parts else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def get_windows_host_ip_address() -> str | None:
    """Return the Windows host LAN IP address.

    This is the address that other devices on the same network should use
    to connect to the host when WSL is running in Mirrored mode.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return None


def get_public_ip_address(timeout: int = 10) -> str | None:
    """Return the public IPv4 address of the local machine, if available."""
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=timeout) as response:
            ip = response.read().decode("utf-8").strip()
            return ip if ip else None
    except Exception:
        return None


def check_environment() -> EnvironmentCheckResult:
    """Check that WSL, SteamCMD and the Palworld server are all available."""
    wsl_available = check_wsl_available()
    if not wsl_available:
        return EnvironmentCheckResult(
            wsl_available=False,
            steamcmd_installed=False,
            palserver_installed=False,
        )

    return EnvironmentCheckResult(
        wsl_available=True,
        steamcmd_installed=check_steamcmd_installed(),
        palserver_installed=check_palserver_installed(),
    )


# ---------------------------------------------------------------------------
# Network setup — WSL networking mode & Windows Firewall
# ---------------------------------------------------------------------------

#: Windows Build Number for Windows 11 22H2 (first release with WSL Mirrored
#: networking mode support).
_WIN11_22H2_BUILD: Final[int] = 22621

#: Name used for the Windows Firewall inbound rule that allows Palworld traffic.
FIREWALL_RULE_NAME: Final[str] = "Palworld UDP 8211"

#: Palworld default game / server port.
PALWORLD_PORT: Final[int] = 8211

#: Path to the user-level WSL configuration file.
_WSLCONFIG_PATH: Final[Path] = Path.home() / ".wslconfig"


def detect_windows_build() -> int:
    """Return the current Windows build number (e.g. 22621 for Win 11 22H2).

    Falls back to 0 on non-Windows platforms or when the registry is
    unavailable, so all ``>= _WIN11_22H2_BUILD`` comparisons safely return
    ``False``.
    """
    if sys.platform != "win32":
        return 0
    try:
        import winreg  # only available on Windows

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        )
        build, _ = winreg.QueryValueEx(key, "CurrentBuildNumber")
        winreg.CloseKey(key)
        return int(build)
    except Exception:  # noqa: BLE001
        try:
            return int(platform.version().split(".")[-1])
        except Exception:  # noqa: BLE001
            return 0


def is_mirrored_mode_supported() -> bool:
    """Return ``True`` if the OS is Windows 11 22H2 or later."""
    return detect_windows_build() >= _WIN11_22H2_BUILD


def read_wslconfig() -> configparser.ConfigParser:
    """Parse ``~/.wslconfig`` and return a :class:`configparser.ConfigParser`.

    If the file does not exist an empty parser is returned so callers can
    treat it uniformly via ``parser.get(..., fallback=...)``.
    """
    parser = configparser.ConfigParser()
    if _WSLCONFIG_PATH.exists():
        parser.read(_WSLCONFIG_PATH, encoding="utf-8")
    return parser


def is_mirrored_mode_enabled() -> bool:
    """Return ``True`` if ``~/.wslconfig`` has ``networkingMode=mirrored``."""
    parser = read_wslconfig()
    value = parser.get("wsl2", "networkingMode", fallback="").strip().lower()
    return value == "mirrored"


def enable_mirrored_mode() -> None:
    """Write ``networkingMode=mirrored`` to ``~/.wslconfig`` and restart WSL.

    If the ``[wsl2]`` section already exists it is updated in place;
    otherwise it is appended.  After writing, ``wsl.exe --shutdown`` is
    executed so the new setting takes effect immediately.

    Raises:
        OSError: If the file cannot be written.
        subprocess.SubprocessError: If ``wsl.exe --shutdown`` fails.
    """
    parser = read_wslconfig()
    if not parser.has_section("wsl2"):
        parser.add_section("wsl2")
    parser.set("wsl2", "networkingMode", "mirrored")

    with _WSLCONFIG_PATH.open("w", encoding="utf-8") as fh:
        parser.write(fh)

    subprocess.run(
        ["wsl.exe", "--shutdown"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",  # 處理無法解碼的字元
        check=False,
        timeout=30,
    )


def is_admin() -> bool:
    """Return ``True`` if the current process has Windows administrator rights."""
    if sys.platform != "win32":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False


def restart_as_admin() -> None:
    """Re-launch this process with administrator privileges via UAC.

    This function does **not** return; the calling code should exit after
    invoking it so the original (non-elevated) process terminates cleanly.
    """
    script = sys.argv[0]
    params = " ".join(sys.argv[1:])
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, f'"{script}" {params}', None, 1
    )


def check_firewall_rule(port: int = PALWORLD_PORT) -> bool:
    """Return ``True`` if the Palworld inbound firewall rule already exists.

    Queries ``netsh advfirewall firewall show rule`` by name.  A non-zero
    exit code means the rule is absent.
    """
    try:
        result = subprocess.run(
            [
                "netsh",
                "advfirewall",
                "firewall",
                "show",
                "rule",
                f"name={FIREWALL_RULE_NAME}",
            ],
            capture_output=True,
            text=True,
            encoding="cp950",  # netsh 輸出為 cp950
            errors="replace",  # 萬一有無法解碼的字元也不會崩潰
            check=False,
            timeout=15,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def add_firewall_rule(port: int = PALWORLD_PORT) -> bool:
    """Add a Windows Firewall inbound rule allowing UDP traffic on *port*.

    Requires administrator privileges.  Returns ``True`` if the rule was
    added successfully, ``False`` otherwise.
    """
    try:
        result = subprocess.run(
            [
                "netsh",
                "advfirewall",
                "firewall",
                "add",
                "rule",
                f"name={FIREWALL_RULE_NAME}",
                "protocol=UDP",
                "dir=in",
                f"localport={port}",
                "action=allow",
            ],
            capture_output=True,
            text=True,
            encoding="cp950",  # netsh 輸出為 cp950
            errors="replace",  # 萬一有無法解碼的字元也不會崩潰
            check=False,
            timeout=15,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def open_windows_firewall_settings() -> None:
    """Open Windows Defender Firewall with Advanced Security.

    Launches the Windows Firewall advanced settings control panel where
    users can manually add inbound rules.  This is useful when the
    application does not have administrator rights to add rules
    automatically.
    """
    try:
        subprocess.Popen(
            ["wf.msc"],
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError:
        # Fallback: try control panel firewall settings
        try:
            subprocess.Popen(
                ["control", "firewall.cpl"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError:
            pass  # Silently fail if neither method works


def check_socat_installed() -> bool:
    """Return ``True`` if ``socat`` is available inside WSL."""
    return _run_wsl_bash_check("command -v socat >/dev/null 2>&1")


def start_socat_forward(
    wsl_ip: str, port: int = PALWORLD_PORT
) -> subprocess.Popen[bytes]:
    """Start a ``socat`` UDP relay from the Windows host port to *wsl_ip*.

    The relay is spawned inside WSL and runs in the background.  The returned
    :class:`~subprocess.Popen` object can be used to terminate the relay when
    the server is stopped.

    Args:
        wsl_ip: The WSL IP address returned by :func:`get_wsl_ip_address`.
        port:   The UDP port to forward (default ``8211``).
    """
    bash_cmd = f"socat UDP4-LISTEN:{port},fork UDP4:{wsl_ip}:{port}"
    args = ["wsl.exe", "bash", "-c", bash_cmd]
    return subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


@dataclass
class NetworkSetupResult:
    """Result of checking the WSL network and Windows Firewall configuration."""

    mirrored_mode_supported: bool
    """Whether the OS supports WSL Mirrored networking (Win 11 22H2+)."""

    mirrored_mode_enabled: bool
    """Whether ``networkingMode=mirrored`` is already set in ``~/.wslconfig``."""

    firewall_rule_exists: bool
    """Whether the Palworld UDP inbound firewall rule already exists."""

    socat_installed: bool
    """Whether ``socat`` is available inside WSL (only relevant in NAT mode)."""

    is_admin: bool
    """Whether the current process has administrator rights."""

    @property
    def needs_setup(self) -> bool:
        """Return ``True`` if any network configuration action is required."""
        return not self.firewall_rule_exists or (
            self.mirrored_mode_supported and not self.mirrored_mode_enabled
        )

    @property
    def pending_actions(self) -> list[str]:
        """Human-readable list of actions that will be taken during setup."""
        actions: list[str] = []
        if self.mirrored_mode_supported and not self.mirrored_mode_enabled:
            actions.append(
                "在 ~/.wslconfig 中設定 networkingMode=mirrored（Mirrored 網路模式）"
            )
            actions.append("執行 wsl --shutdown 重啟 WSL 使設定生效")
        elif not self.mirrored_mode_supported and not self.socat_installed:
            actions.append(
                "系統不支援 Mirrored Mode，且 WSL 中未偵測到 socat。\n"
                "請在 WSL 中執行：sudo apt install socat"
            )
        if not self.firewall_rule_exists:
            actions.append(
                f'新增 Windows 防火牆輸入規則："{FIREWALL_RULE_NAME}"（UDP {PALWORLD_PORT}）'
            )
        return actions


def check_network_setup() -> NetworkSetupResult:
    """Inspect WSL networking mode and Windows Firewall state.

    This is the single entry point the GUI calls to decide whether the
    :class:`~lvk_paluworld_server_manager.gui.main_window.NetworkSetupDialog`
    should be shown.
    """
    supported = is_mirrored_mode_supported()
    return NetworkSetupResult(
        mirrored_mode_supported=supported,
        mirrored_mode_enabled=is_mirrored_mode_enabled(),
        firewall_rule_exists=check_firewall_rule(),
        socat_installed=check_socat_installed() if not supported else False,
        is_admin=is_admin(),
    )


# ---------------------------------------------------------------------------
# Diagnostic Information — Network connectivity testing & aggregated status
# ---------------------------------------------------------------------------


def test_external_connectivity(timeout: int = 5) -> bool:
    """Test external network connectivity by attempting to reach known endpoints.

    Tries multiple reliable endpoints to reduce false negatives from
    individual service outages.

    Args:
        timeout: Maximum seconds to wait for each endpoint test.

    Returns:
        ``True`` if at least one endpoint is reachable, ``False`` otherwise.
    """
    endpoints = [
        ("https://dns.google", "Google DNS"),
        ("https://1.1.1.1", "Cloudflare DNS"),
        ("https://www.cloudflare.com", "Cloudflare"),
    ]

    for url, _name in endpoints:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                if response.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            continue

    return False


@dataclass(frozen=True)
class DiagnosticInfo:
    """Comprehensive diagnostic information about the server environment."""

    wsl_ip: str | None
    """WSL distribution IP address, or None if unavailable."""

    windows_ip: str | None
    """Windows host LAN IP address, or None if unavailable."""

    public_ip: str | None
    """Public internet IP address, or None if unavailable."""

    firewall_rule_exists: bool
    """Whether the Palworld UDP firewall rule is configured."""

    environment_check: EnvironmentCheckResult
    """Status of WSL, SteamCMD, and PalServer installation."""

    network_setup: NetworkSetupResult
    """WSL networking mode and firewall configuration status."""

    external_connectivity: bool
    """Whether external internet connectivity is available."""


def get_all_diagnostic_info() -> DiagnosticInfo:
    """Gather all diagnostic information in a single function call.

    This is the main entry point for the diagnostic dialog. It queries
    IP addresses, environment status, network setup, and connectivity.

    Returns:
        A :class:`DiagnosticInfo` instance with all collected information.
    """
    return DiagnosticInfo(
        wsl_ip=get_wsl_ip_address(),
        windows_ip=get_windows_host_ip_address(),
        public_ip=get_public_ip_address(),
        firewall_rule_exists=check_firewall_rule(),
        environment_check=check_environment(),
        network_setup=check_network_setup(),
        external_connectivity=test_external_connectivity(),
    )
