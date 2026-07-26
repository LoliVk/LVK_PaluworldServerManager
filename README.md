# LVK Palworld Server Manager 帕魯世界伺服器管理器

This project is a simplified Python application scaffold tailored for the built-in Tkinter GUI toolkit.
本專案是一個使用內建 Tkinter GUI 工具包打造的簡化 Python 應用程式範本。

## Project structure 專案結構

- `src/lvk_paluworld_server_manager/config.py`: shared app config and message helpers
  共用的應用程式設定與訊息輔助函式
- `src/lvk_paluworld_server_manager/gui/`: Tkinter GUI package (`main_window.py`)
  Tkinter GUI 套件（`main_window.py`）
- `src/lvk_paluworld_server_manager/cli.py`: command-line entry point
  命令列進入點
- `src/lvk_paluworld_server_manager/__main__.py`: enables `python -m lvk_paluworld_server_manager`
  讓專案可透過 `python -m lvk_paluworld_server_manager` 執行
- `tests/`: unit and smoke tests
  單元測試與基本功能測試
- `pyproject.toml`: package metadata and tooling
  套件中繼資料與工具設定

## Run the app 執行應用程式

```bash
python -m lvk_paluworld_server_manager
```

or, after installing the console script:
或者，安裝主控台指令後：

```bash
lvk-paluworld-server-manager
```

## Run tests 執行測試

```bash
C:/Users/User/AppData/Local/Programs/Python/Python310/python.exe -m pytest -q
```
