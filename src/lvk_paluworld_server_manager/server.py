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

import subprocess
from dataclasses import dataclass
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
    return subprocess.run(args, capture_output=True, text=True, check=False)


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
            check=False,
            timeout=15,
        )
        if status.returncode != 0:
            return False

        distros = subprocess.run(
            ["wsl.exe", "-l", "-q"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        if distros.returncode != 0:
            return False

        # ``wsl.exe -l -q`` output is UTF-16 and often padded with NUL bytes
        # when decoded as text; strip them before checking for content.
        return bool(distros.stdout.replace("\x00", "").strip())
    except (OSError, subprocess.TimeoutExpired):
        return False


def _run_wsl_bash_check(bash_command: str) -> bool:
    """Run a bash command inside WSL and report whether it succeeded."""
    try:
        result = subprocess.run(
            ["wsl.exe", "bash", "-c", bash_command],
            capture_output=True,
            text=True,
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
