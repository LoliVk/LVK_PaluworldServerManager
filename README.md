# LVK Palworld Server Manager / 帕魯世界伺服器管理器

LVK Palworld Server Manager is a Python application for launching and managing a Palworld dedicated server inside WSL (Windows Subsystem for Linux). It performs environment validation for WSL, SteamCMD, and PalServer, and provides both visible and background server launch modes with built-in diagnostics and network setup guidance.

LVK Palworld Server Manager 是一款 Python 應用程式，用於在 WSL（Windows Subsystem for Linux）內啟動與管理帕魯世界專用伺服器。它會檢查 WSL、SteamCMD 與 PalServer 的環境狀態，並支援顯示終端機視窗與背景執行兩種啟動方式，同時提供診斷與網路設定輔助功能。

## Overview / 概述

This project provides lightweight Windows-based management for a Palworld server while keeping the server process inside WSL. Its current GUI uses a multi-page dashboard with clear status feedback and safe server lifecycle management through PowerShell/WSL commands.

本專案提供輕量的 Windows 管理工具，讓使用者可以控制位於 WSL 內的帕魯世界伺服器。目前的 GUI 採多頁式 Dashboard，設計重點在於狀態清楚、並透過 PowerShell/WSL 指令安全管理伺服器生命週期。

## Features / 功能特色

- Multi-page responsive interface / 多頁式響應式介面
  - The desktop layout provides a sidebar for Dashboard, Backups, World, and Stats. When the window is narrower than the desktop layout, it switches to bottom navigation.
  - 桌面版提供 Dashboard、Backups、World 與 Stats 側欄導覽；視窗寬度不足桌面配置時，會切換為底部導覽列。

- Dashboard and live console / Dashboard 與即時主控台
  - The Dashboard combines server status, environment checks, connection information, diagnostics, server updates, and a live console. Console output can be cleared and automatic scrolling can be resumed after reviewing earlier output.
  - Dashboard 集中顯示伺服器狀態、環境檢查、連線資訊、診斷、伺服器更新與即時主控台。主控台可清除內容，並可在檢視舊訊息後恢復自動捲動。

- Environment validation on startup / 啟動時進行環境檢查
  - Verifies that WSL is available, SteamCMD is installed in WSL, and the Palworld server installation exists before allowing the server to start.
  - 於啟動前檢查 WSL 是否可用、WSL 內是否安裝 SteamCMD，以及 Palworld 專用伺服器是否已安裝。

- Two launch modes / 兩種啟動模式
  - The Dashboard's **Start Server** button opens a menu for visible and background launch modes. Visible mode opens a dedicated PowerShell/WSL console window; background mode streams output into the live console.
  - Dashboard 的 **Start Server** 按鈕會開啟選單，可選擇顯示終端機視窗或背景執行模式。背景模式會將輸出串流至即時主控台。

- Server start/stop control / 伺服器啟動與停止
  - Starts the server with WSL bash commands and stops it using `pkill -f PalServer.sh` inside WSL.
  - 透過 WSL bash 指令啟動伺服器，並使用 `pkill -f PalServer.sh` 在 WSL 內停止伺服器。

- One-click server updates / 一鍵更新伺服器
  - The **Update Server** button stops accidental updates while PalServer is running, then uses SteamCMD to run `app_update 2394010 validate` inside WSL and displays the result in the application log.
  - **更新伺服器 / Update Server** 按鈕會在 PalServer 執行時拒絕更新；停止後，會在 WSL 內透過 SteamCMD 執行 `app_update 2394010 validate`，並將結果顯示於程式日誌。

- Verified world-save backups / 已驗證的世界存檔備份
  - The dedicated **Backups** page creates a ZIP backup of every dedicated-server world save, excluding existing backups, and verifies that the archive contains each world's `WorldOption.sav`.
  - It refuses to create a backup while PalServer is running, helping avoid inconsistent save data.
  - Shows the completed archive path and provides an **Open Backup Folder** button to open its `Backups` folder in File Explorer.
  - 專用的 **Backups** 頁面可建立所有專用伺服器世界存檔的 ZIP 備份，排除既有備份檔，並驗證封存檔包含各世界的 `WorldOption.sav`。
  - PalServer 執行期間會拒絕建立備份，以避免產生不一致的存檔資料。
  - 備份完成後會顯示封存檔路徑，並提供 **開啟備份資料夾 / Open Backup Folder** 按鈕，可在檔案總管開啟 `Backups` 資料夾。

- Comprehensive diagnostics / 完整診斷資訊
  - One-click diagnostic panel shows localhost, WSL, LAN, and public IP addresses, firewall rule status, environment checks, network connectivity, and WSL networking mode.
  - Background checks run without blocking the UI, and diagnostic results can be copied to the clipboard.
  - 一鍵診斷面板顯示本機、WSL、區域網路及公開 IP、Windows 防火牆規則狀態、環境檢查結果、網路連線測試，以及 WSL 網路模式狀態。

- Network setup guidance / 網路設定輔助
  - Detects whether Windows 11 Mirrored mode is supported and whether `socat` is available in WSL when Mirrored mode is not supported.
  - Helps enable `networkingMode=mirrored` in `~/.wslconfig`, restart WSL, and add the Palworld UDP firewall rule for port 8211.
  - 偵測是否支援 Windows 11 Mirrored mode，以及在不支援 Mirrored mode 時檢查 WSL 中是否安裝 `socat`。
  - 協助設定 `~/.wslconfig` 中的 `networkingMode=mirrored`、重新啟動 WSL，並新增 8211 埠的 Windows 防火牆規則。

- Live UI state updates / 即時 UI 狀態更新
  - Start/Stop button state is updated automatically based on the current server status.
  - 啟動/停止按鈕會根據伺服器目前狀態自動切換。

- Planned pages / 準備中的頁面
  - **World** and **Stats** are visible in the navigation but currently show a "feature is being prepared" placeholder. They do not yet provide world management or telemetry features.
  - **World** 與 **Stats** 已顯示在導覽列中，但目前僅顯示「功能準備中」頁面，尚未提供世界管理或遙測功能。

## Installation / 安裝

Install the package from the project root:

從專案根目錄安裝套件：

```bash
python -m pip install -e .
```

Install development dependencies for testing and linting:

安裝開發依賴套件以進行測試與格式檢查：

```bash
python -m pip install -e .[dev]
```

## Project Structure / 專案結構

- `src/lvk_paluworld_server_manager/config.py`
  - Shared application configuration and UI message helpers.
  - 共用應用程式設定與 UI 訊息輔助函式。

- `src/lvk_paluworld_server_manager/server.py`
  - WSL and PowerShell helpers for launching, stopping, and validating the Palworld server.
  - Contains diagnostics, network setup checks, and firewall/socat helpers.
  - 負責透過 WSL 與 PowerShell 啟動、停止與驗證 Palworld 伺服器。
  - 包含診斷、網路設定檢查，以及防火牆/`socat` 輔助函式。

- `src/lvk_paluworld_server_manager/gui/main_window.py`
  - Coordinates the multi-page GUI, navigation, worker queues, server controls, backups, and diagnostic information.
  - 協調多頁式 GUI、導覽、背景工作佇列、伺服器控制、備份與診斷資訊。

- `src/lvk_paluworld_server_manager/gui/pages.py`
  - Defines the Dashboard, Backups, and reusable placeholder page layouts.
  - 定義 Dashboard、Backups 與可重用的準備中頁面版面。

- `src/lvk_paluworld_server_manager/gui/widgets.py`
  - Provides custom Tkinter UI components used by the page layouts and navigation.
  - 提供頁面版面與導覽列使用的自訂 Tkinter 元件。

- `src/lvk_paluworld_server_manager/gui/dialogs/`
  - Contains the backup-complete, diagnostics, network-setup, and retained world-settings dialog implementations.
  - 包含備份完成、診斷、網路設定，以及保留中的世界設定對話框實作。

- `src/lvk_paluworld_server_manager/world_options.py`
  - World-save discovery, backup validation, and retained world-settings editing support.
  - 世界存檔探索、備份驗證，以及保留中的世界設定編輯支援。

- `src/lvk_paluworld_server_manager/cli.py`
  - Command-line entry point for launching the GUI.
  - 啟動 GUI 的命令列入口。

- `tests/`
  - Unit tests covering configuration, server behavior, environment and network validation, backup and world-save safety, and GUI interactions.
  - 單元測試涵蓋設定、伺服器行為、環境與網路驗證、備份與世界存檔安全機制，以及 GUI 互動。

## Requirements / 系統需求

- Windows operating system with WSL installed and configured.
- Windows 作業系統，並已安裝與設定 WSL。

- At least one Linux distribution available inside WSL.
- WSL 中至少已設定一個 Linux 發行版。

- SteamCMD installed inside WSL.
- WSL 內已安裝 SteamCMD。

- Palworld dedicated server files installed inside WSL, including `PalServer.sh`.
- WSL 內已安裝帕魯世界專用伺服器檔案，包含 `PalServer.sh`。

- Python 3.10 or later.
- Python 3.10 或更新版本。

- `palworld-save-tools` version 0.24.0.
- `palworld-save-tools` 0.24.0 版。

- Windows 11 22H2 or later for WSL Mirrored Mode support; on older Windows versions, `socat` is required inside WSL for UDP forwarding.
- 若要支援 WSL Mirrored Mode，建議使用 Windows 11 22H2 或更新版本；若為舊版本，則需要在 WSL 中安裝 `socat` 以支援 UDP 轉發。

## Getting Started / 開始使用

Run the application from the project root with the following command:

從專案根目錄執行以下指令：

```bash
python -m lvk_paluworld_server_manager
```

If the console script is installed, this command is also available:

若已安裝主控台指令，亦可使用下列指令：

```bash
lvk-paluworld-server-manager
```

### Navigating the Application / 使用應用程式導覽

The application opens on the **Dashboard**. On desktop-sized windows, use the sidebar to select **Dashboard**, **Backups**, **World**, or **Stats**. On narrower windows, the same destinations appear in a bottom navigation bar.

應用程式會開啟在 **Dashboard**。桌面尺寸的視窗可使用側欄選擇 **Dashboard**、**Backups**、**World** 或 **Stats**；較窄的視窗會在底部顯示相同的導覽項目。

Use **Start Server** to choose either visible mode or background execution. In background mode, server output appears in the Dashboard's **Live Console**. Use **Stop Server** before updating the server or creating a world-save backup.

使用 **Start Server** 選擇顯示終端機視窗或背景執行模式。背景模式的伺服器輸出會顯示於 Dashboard 的 **Live Console**。更新伺服器或建立世界存檔備份前，請先使用 **Stop Server** 停止伺服器。

### Using the Diagnostic Tool / 使用診斷工具

Click the "診斷資訊 / Diagnostic Info" button to view comprehensive system diagnostics:

點擊「診斷資訊 / Diagnostic Info」按鈕以查看完整的系統診斷資訊：

- **IP Addresses** / **IP 位址**: Localhost (`127.0.0.1:8211`), WSL IP, Windows LAN IP, and Public IP with port information
- **Firewall Status** / **防火牆狀態**: UDP 8211 rule configuration status
- **Environment** / **環境狀態**: WSL, SteamCMD, and PalServer installation status
- **Network Connectivity** / **網路連線**: External internet connectivity verification
- **WSL Network Setup** / **WSL 網路設定**: Mirrored mode support and administrator rights status

Use the "複製資訊 / Copy Info" button to copy all diagnostic data to the clipboard for troubleshooting or sharing.

使用「複製資訊 / Copy Info」按鈕將所有診斷資料複製到剪貼簿，方便疑難排解或分享給技術支援人員。

### Choosing a Connection Address / 選擇連線位址

Use the displayed address that matches where the player is connecting from:

請依玩家所在位置選擇對應的顯示位址：

| Player location / 玩家位置 | Connection address / 連線位址 |
| --- | --- |
| The same Windows computer hosting the server / 同一台執行伺服器的 Windows 電腦 | `127.0.0.1:8211` |
| Another device on the same local network / 同一區域網路的其他裝置 | `Windows LAN IP:8211` |
| A player connecting from the Internet / 從網際網路連線的玩家 | `Public IP:8211` |

For Internet players, configure the router to forward **UDP 8211** to the Windows host and allow the same port through Windows Defender Firewall.

外網玩家連線時，請將路由器的 **UDP 8211** 轉發至 Windows 主機，並在 Windows Defender 防火牆中放行相同連接埠。

### Backing Up World Saves / 備份世界存檔

Open the **Backups** page and click **「備份所有世界存檔 / Backup All World Saves」** to create a timestamped ZIP archive in the dedicated-server save directory's `Backups` folder. When the backup completes, use **「開啟備份資料夾 / Open Backup Folder」** to open that folder in File Explorer. Stop PalServer before starting the backup; the application refuses the operation while the server is running.

開啟 **Backups** 頁面後，點擊 **「備份所有世界存檔 / Backup All World Saves」**，即可在專用伺服器存檔目錄的 `Backups` 資料夾建立含時間戳記的 ZIP 封存檔。備份完成後，可使用 **「開啟備份資料夾 / Open Backup Folder」** 在檔案總管開啟該資料夾。開始備份前請先停止 PalServer；伺服器執行時，應用程式會拒絕此操作。

### World and Stats Status / World 與 Stats 狀態

The **World** and **Stats** navigation pages are placeholders while their features are being prepared. The world-settings editor implementation is retained internally, but it is not exposed through the current main-window navigation.

**World** 與 **Stats** 導覽頁面目前為功能準備中的預留頁面。世界設定編輯器的實作仍保留於內部程式碼中，但目前主視窗導覽不會提供入口。

## Testing / 測試

Run the test suite with:

執行測試套件：

```bash
pytest -q
```

For linting and static checks, run:

若要進行格式與靜態檢查，請執行：

```bash
python -m ruff check src tests
python -m mypy src
```
