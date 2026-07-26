from __future__ import annotations

import tkinter as tk

import pytest

from lvk_paluworld_server_manager.config import AppConfig
from lvk_paluworld_server_manager.gui import MainWindow


def test_main_window_uses_config_title() -> None:
    try:
        window = MainWindow(AppConfig(title="Demo App"))
    except tk.TclError as exc:
        pytest.skip(f"Tk/Tcl is not usable in this environment: {exc}")
        return

    try:
        assert window.title() == "Demo App"
    finally:
        window.destroy()
