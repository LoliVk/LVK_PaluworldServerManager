# Design Document

## 1. Purpose

LVK Palworld Server Manager is a Windows desktop application for operating a
Palworld dedicated server that runs inside WSL.  It keeps the game-server
process in Linux while providing a local Tkinter interface for the Windows
administrator.

The design priorities are:

- Keep WSL, SteamCMD, and PalServer interactions behind a testable service
  layer.
- Keep the Tkinter event loop responsive while commands, network checks, and
  save-file work are in progress.
- Refuse save-affecting actions when PalServer is running.
- Surface enough diagnostics for a user to configure LAN or Internet access
  without manually collecting system information.

## 2. Runtime Architecture

```text
+--------------------------- Windows ----------------------------+
|                                                                 |
|  python -m ... / console script                                 |
|               |                                                 |
|               v                                                 |
|  cli.py -> gui.main_window.MainWindow (Tkinter)                 |
|               |                                                 |
|               +--> server.py ----> PowerShell / wsl.exe         |
|               |                         |                       |
|               |                         v                       |
|               |                    WSL Linux                   |
|               |                 SteamCMD / PalServer.sh        |
|               |                                                 |
|               +--> world_options.py --> \\wsl$ UNC save files   |
|                                                                 |
+-----------------------------------------------------------------+
```

The package uses a `src/` layout.  `cli.py` is the console-script entry point;
`__main__.py` allows `python -m lvk_paluworld_server_manager`; both end at
`gui.main_window.main()`.

## 3. Components and Responsibilities

| Component | Responsibility |
| --- | --- |
| `config.py` | Small immutable `AppConfig` object and shared ready-state message helper. |
| `server.py` | Builds and runs PowerShell/WSL commands, checks prerequisites, controls the process, gathers diagnostics, and manages networking/firewall setup.  It has no GUI dependency. |
| `world_options.py` | Finds world saves, creates verified ZIP backups, decodes/encodes `WorldOption.sav`, validates editable values, and writes changed data safely. |
| `gui/main_window.py` | Tkinter presentation layer.  It owns controls, dialogs, user-facing state, background-worker coordination, and output display. |
| `tests/` | Unit tests for command construction, error-safe behavior, world-save mutations, and GUI state transitions. |

## 4. Server Lifecycle

### Start

1. `MainWindow` performs `server.check_environment()` at startup.
2. Start remains unavailable unless WSL, SteamCMD, and the PalServer
   installation are all detected.
3. The user selects one of two modes:
   - **Visible:** a new PowerShell window runs `wsl bash -c` with `-NoExit` so
     server output remains visible.
   - **Background:** PowerShell output is piped to the GUI log panel.
4. The GUI disables Start, enables Stop, and obtains connection information in
   a worker thread.

The server command changes to
`~/.local/share/Steam/steamapps/common/PalServer` and runs `./PalServer.sh`.

### Stop and update

- Stopping uses `pkill -f PalServer.sh` within WSL.  This intentionally does
  not depend on the GUI's launcher process, so it can also stop a server that
  was launched in another terminal.
- Updating is blocked while a server process is detected.  It runs SteamCMD
  app ID `2394010` with `app_update ... validate`; either `steamcmd` on PATH
  or `~/Steam/steamcmd.sh` is supported.

## 5. UI Concurrency Model

Tkinter widgets are updated only on the main thread.  Operations that can
block run in daemon threads: background-server output reading, environment and
IP checks, updates, diagnostics, backups, and world-option decoding/writing.

Workers place results in `queue.Queue` instances.  The UI periodically drains
each queue with `after()` callbacks, updates the corresponding widgets, and
restores controls when the worker reports completion.  This avoids a frozen
window while retaining a simple standard-library design.

## 6. Diagnostics and Network Setup

`server.py` collects data for a diagnostic dialog:

- WSL, Windows LAN, and public IP addresses.
- WSL/SteamCMD/PalServer readiness.
- External network reachability.
- Windows build and WSL mirrored-networking state.
- UDP `8211` firewall-rule status and `socat` availability.

For supported Windows 11 builds, the application can set
`networkingMode=mirrored` in the user's `.wslconfig` and shut down WSL so the
setting can take effect.  It can also add the `Palworld UDP 8211` inbound
firewall rule.  Older or unsupported mirrored-mode environments receive a
`socat`-based forwarding path instead.

Administrative privileges are required for firewall changes and some network
setup actions; the GUI can relaunch itself elevated when needed.

## 7. Save Data and World Options

World saves are reached through a Windows UNC path derived from the WSL
distribution, under PalServer's `Pal/Saved/SaveGames/0` directory.

### Backup policy

`backup_all_world_saves()` creates a timestamped ZIP archive in `Backups/`.
It excludes pre-existing backup archives and verifies that every discovered
world contributes its `WorldOption.sav` to the resulting archive.  The action
is rejected if PalServer is running or no valid worlds are found.

### Editing policy

The retained `WorldOptionEditorDialog` can discover worlds and edit supported
`WorldOption.sav` settings using `palworld-save-tools`.  Before any write it:

1. Treats an unknown process state as running, preventing a risky write.
2. Validates all requested values before applying any of them.
3. Creates a verified backup of the selected world.
4. Encodes to a temporary file, validates the encoded result by decoding it,
   then replaces the save.
5. Restores the in-memory properties if encoding fails.

The main window currently exposes backup but deliberately hides the editor
entry point.  The implementation is retained for future save-format support.

## 8. Failure Handling and Safety Boundaries

- Subprocess and network failures generally return a clear false/empty result
  for diagnostics instead of crashing the GUI.
- `is_server_process_running()` is conservative: command failure or timeout
  is treated as **running**, which blocks save writes.
- Update and backup actions are disabled while their worker is active to avoid
  duplicate operations.
- Each world-save failure category has an explicit exception type, including
  decode, encode, backup, validation, and running-server errors.

## 9. Testing Strategy

The automated tests use `pytest` and mocks rather than a real WSL server.

- `test_server.py` validates WSL/PowerShell command construction, lifecycle
  commands, prerequisite checks, diagnostics, networking, and failure paths.
- `test_world_options.py` verifies backup contents, validation, atomic save
  behavior, and property restoration after an encode failure.
- `test_gui.py` verifies button states, queued background results, and that
  risky actions remain guarded.  Tests skip GUI cases when Tk/Tcl is not
  available in the test environment.

Run the suite with `pytest -q`.  The development configuration also supports
`python -m ruff check src tests` and `python -m mypy src`.

## 10. Extension Guidelines

- Add new WSL or PowerShell operations to `server.py`, then expose them from
  the GUI; do not embed shell-command construction in widget callbacks.
- Use the existing worker-thread, queue, and `after()` pattern for new
  potentially blocking UI actions.
- Preserve the server-stopped guard before adding any save-data write action.
- Extend `SettingField` metadata and validation in `world_options.py` when
  supporting another editable world option, so unknown save properties remain
  untouched.
