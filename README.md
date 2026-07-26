# LVK Palworld Server Manager 帕魯世界伺服器管理器

A Tkinter GUI application that starts and stops a Palworld dedicated server running inside WSL (Windows Subsystem for Linux), with a built-in environment check for WSL / SteamCMD / PalServer.

> 這是一個 Tkinter GUI 應用程式，用於啟動與停止安裝在 WSL（Windows Subsystem for Linux）內的帕魯世界（Palworld）專用伺服器，並內建 WSL / SteamCMD / PalServer 的環境偵測功能。

## Table of Contents 目錄

- [Features 功能](#features-功能)
- [Project Structure 專案結構](#project-structure-專案結構)
- [Requirements 需求](#requirements-需求)
- [Run the App 執行應用程式](#run-the-app-執行應用程式)
- [Run Tests 執行測試](#run-tests-執行測試)

## Features 功能

| Feature | 功能說明 |
| --- | --- |
| **Environment check on startup** — verifies WSL, SteamCMD and the PalServer installation (`~/.local/share/Steam/steamapps/common/PalServer`) are ready, disabling the start button with an error dialog if anything is missing. | 啟動時自動檢查環境：確認 WSL、SteamCMD 及 PalServer 安裝路徑是否就緒，若缺少任何項目會彈出錯誤訊息並停用啟動按鈕。 |
| **Two start modes** — "visible" (opens a separate PowerShell/WSL console window) or "background" (output is streamed into the app's log box). | 可選擇「顯示終端機視窗」模式啟動伺服器，或「背景執行」模式（輸出會顯示在應用程式內的紀錄框中）。 |
| **Stop server** — terminates the server via `pkill` inside WSL, regardless of which mode it was started in. | 可透過 WSL 內的 `pkill` 停止伺服器，不論啟動時使用哪種模式。 |
| **Live button state** — Start/Stop buttons automatically toggle to reflect whether the server is running. | 啟動／停止按鈕會自動切換狀態以反映伺服器目前是否正在執行。 |

## Project Structure 專案結構

| Path 路徑 | Description 說明 |
| --- | --- |
| `src/lvk_paluworld_server_manager/config.py` | Shared app config and message helpers.<br>共用的應用程式設定與訊息輔助函式。 |
| `src/lvk_paluworld_server_manager/server.py` | WSL/PowerShell helpers to start, stop and check the Palworld dedicated server environment.<br>透過 WSL/PowerShell 啟動、停止並檢查帕魯世界專用伺服器環境的輔助函式。 |
| `src/lvk_paluworld_server_manager/gui/main_window.py` | Tkinter GUI package with the main window and server controls.<br>包含主視窗與伺服器控制項的 Tkinter GUI 套件。 |
| `src/lvk_paluworld_server_manager/cli.py` | Command-line entry point.<br>命令列進入點。 |
| `src/lvk_paluworld_server_manager/__main__.py` | Enables `python -m lvk_paluworld_server_manager`.<br>讓專案可透過 `python -m lvk_paluworld_server_manager` 執行。 |
| `tests/` | Unit and smoke tests (`test_config.py`, `test_server.py`, `test_gui.py`).<br>單元測試與基本功能測試（`test_config.py`、`test_server.py`、`test_gui.py`）。 |
| `pyproject.toml` | Package metadata and tooling.<br>套件中繼資料與工具設定。 |

## Requirements 需求

- ✅ Windows with WSL installed and at least one Linux distribution set up.
  已安裝 WSL 的 Windows，並設定好至少一個 Linux 發行版。
- ✅ SteamCMD and the Palworld dedicated server (`PalServer.sh`) installed inside WSL. See `docs/reference/` for setup guides.
  在 WSL 內安裝 SteamCMD 及帕魯世界專用伺服器（`PalServer.sh`）。安裝步驟可參考 `docs/reference/` 內的說明文件。

## Run the App 執行應用程式

```bash
python -m lvk_paluworld_server_manager
```

Or, after installing the console script 或者，安裝主控台指令後：

```bash
lvk-paluworld-server-manager
```

## Run Tests 執行測試

```bash
C:/Users/User/AppData/Local/Programs/Python/Python310/python.exe -m pytest -q
```
