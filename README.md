# LVK Palworld Server Manager / 帕魯世界伺服器管理器

LVK Palworld Server Manager is a Python-based Tkinter application designed to help users launch and manage a Palworld dedicated server running inside WSL (Windows Subsystem for Linux). The application includes built-in environment validation for WSL, SteamCMD, and the PalServer installation, and provides both visible and background server launch modes.

LVK Palworld Server Manager 是一款基於 Python 與 Tkinter 的應用程式，旨在協助使用者在 WSL（Windows Subsystem for Linux）中啟動與管理帕魯世界專用伺服器。此應用程式內建 WSL、SteamCMD 與 PalServer 的環境檢查功能，並支援「顯示終端機視窗」與「背景執行」兩種啟動模式。

## Overview / 概述

This project provides a lightweight desktop interface for managing a Palworld server from Windows while keeping the actual server execution inside WSL. It focuses on ease of use, clear status feedback, and simplified server lifecycle control.

本專案提供一個輕量化的桌面介面，讓使用者可從 Windows 環境中管理位於 WSL 內的帕魯世界伺服器。其設計重點在於操作簡單、狀態清楚，以及提供方便的伺服器啟動與停止流程。

## Features / 功能特色

- Environment validation on startup / 啟動時進行環境檢查
  - Verifies that WSL, SteamCMD, and PalServer are available before allowing the server to start.
  - 於伺服器啟動前檢查 WSL、SteamCMD 與 PalServer 是否已就緒。

- Two launch modes / 兩種啟動模式
  - Visible mode opens a dedicated PowerShell/WSL console window.
  - Background mode runs the server silently in the background and streams output into the application log panel.
  - 可選擇顯示終端機視窗模式，或背景執行模式，並將輸出顯示於應用程式內的日誌區域。

- Server control operations / 伺服器控制功能
  - Supports starting and stopping the server through WSL-based commands.
  - 支援透過 WSL 指令啟動與停止伺服器。

- Live UI state updates / 即時 UI 狀態更新
  - Start and Stop buttons automatically reflect the current server state.
  - 啟動與停止按鈕會根據伺服器目前狀態自動切換。

## Project Structure / 專案結構

- src/lvk_paluworld_server_manager/config.py
  - Shared application configuration and message helpers.
  - 共用的應用程式設定與訊息輔助函式。

- src/lvk_paluworld_server_manager/server.py
  - WSL and PowerShell helpers for launching, stopping, and validating the server environment.
  - 負責透過 WSL 與 PowerShell 啟動、停止伺服器，並檢查其執行環境。

- src/lvk_paluworld_server_manager/gui/main_window.py
  - Tkinter-based main window and server control interface.
  - 主要的 Tkinter 使用者介面與伺服器控制介面。

- tests/
  - Unit tests covering server behavior, GUI interactions, and environment checks.
  - 涵蓋伺服器行為、GUI 互動與環境檢查的單元測試。

## Requirements / 系統需求

- Windows operating system with WSL installed and configured.
- Windows 作業系統，並已安裝與設定 WSL。

- At least one Linux distribution available inside WSL.
- WSL 中至少已設定一個 Linux 發行版。

- SteamCMD installed inside WSL.
- WSL 內已安裝 SteamCMD。

- Palworld dedicated server files, including PalServer.sh, installed inside WSL.
- WSL 內已安裝帕魯世界專用伺服器檔案，包含 PalServer.sh。

## Getting Started / 開始使用

Run the application from the project root with the following command:

從專案根目錄執行以下指令：

```bash
python -m lvk_paluworld_server_manager
```

If the console script has been installed, the following command is also available:

若已安裝主控台指令，亦可使用下列指令：

```bash
lvk-paluworld-server-manager
```

## Testing / 測試

Run the test suite with:

執行測試套件：

```bash
pytest -q
```
