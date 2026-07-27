from __future__ import annotations

import io
import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

from lvk_paluworld_server_manager.config import AppConfig
from lvk_paluworld_server_manager.gui import MainWindow


def _make_window(title: str = "Demo App") -> MainWindow:
    try:
        window = MainWindow(AppConfig(title=title))
    except tk.TclError as exc:
        pytest.skip(f"Tk/Tcl is not usable in this environment: {exc}")
        raise
    return window


def test_main_window_uses_config_title() -> None:
    window = _make_window()

    try:
        assert window.title() == "Demo App"
    finally:
        window.destroy()


@patch("lvk_paluworld_server_manager.gui.main_window.server.start_server_visible")
def test_start_server_visible_mode_updates_buttons(mock_start: MagicMock) -> None:
    window = _make_window()

    try:
        window.mode_var.set("visible")
        window._on_start_server()

        mock_start.assert_called_once()
        assert str(window.start_server_button["state"]) == "disabled"
        assert str(window.stop_server_button["state"]) == "normal"
    finally:
        window.destroy()


@patch("lvk_paluworld_server_manager.gui.main_window.server.stop_server")
def test_stop_server_resets_buttons(mock_stop: MagicMock) -> None:
    window = _make_window()

    try:
        window._set_running_state(True)
        window._on_stop_server()

        mock_stop.assert_called_once()
        assert str(window.start_server_button["state"]) == "normal"
        assert str(window.stop_server_button["state"]) == "disabled"
    finally:
        window.destroy()


def test_read_output_and_poll_queue_streams_process_stdout() -> None:
    window = _make_window()

    try:
        fake_process = MagicMock()
        fake_process.stdout = io.StringIO("line1\nline2\n")
        window._process = fake_process

        # Run synchronously (in the test thread) instead of spawning a real
        # background thread, so the assertions below are deterministic.
        window._read_output()
        window._poll_output_queue()

        content = window.output_text.get("1.0", tk.END)
        assert "line1" in content
        assert "line2" in content
        assert window._poll_job is None
        assert str(window.start_server_button["state"]) == "normal"
        assert str(window.stop_server_button["state"]) == "disabled"
    finally:
        window.destroy()


@patch("lvk_paluworld_server_manager.gui.main_window.messagebox.showerror")
@patch("lvk_paluworld_server_manager.gui.main_window.server.check_environment")
def test_environment_check_disables_start_when_requirements_missing(
    mock_check: MagicMock, mock_showerror: MagicMock
) -> None:
    from lvk_paluworld_server_manager.server import EnvironmentCheckResult

    mock_check.return_value = EnvironmentCheckResult(
        wsl_available=False,
        steamcmd_installed=False,
        palserver_installed=False,
    )
    window = _make_window()

    try:
        window._perform_environment_check()

        mock_showerror.assert_called_once()
        assert str(window.start_server_button["state"]) == "disabled"
    finally:
        window.destroy()


@patch("lvk_paluworld_server_manager.gui.main_window.messagebox.showerror")
@patch("lvk_paluworld_server_manager.gui.main_window.server.check_environment")
def test_environment_check_keeps_start_enabled_when_requirements_met(
    mock_check: MagicMock, mock_showerror: MagicMock
) -> None:
    from lvk_paluworld_server_manager.server import EnvironmentCheckResult

    mock_check.return_value = EnvironmentCheckResult(
        wsl_available=True,
        steamcmd_installed=True,
        palserver_installed=True,
    )
    window = _make_window()

    try:
        window._perform_environment_check()

        mock_showerror.assert_not_called()
        assert str(window.start_server_button["state"]) == "normal"
    finally:
        window.destroy()


@patch("lvk_paluworld_server_manager.gui.main_window.threading.Thread")
@patch("lvk_paluworld_server_manager.gui.main_window.server.start_server_background")
def test_start_server_background_mode_dispatches_reader_thread(
    mock_start: MagicMock, mock_thread_cls: MagicMock
) -> None:
    window = _make_window()

    try:
        fake_process = MagicMock()
        fake_process.stdout = io.StringIO("")
        mock_start.return_value = fake_process

        window.mode_var.set("background")
        window._on_start_server()

        mock_start.assert_called_once()
        # Two threads are created: one for output reading, one for IP lookup.
        assert mock_thread_cls.call_count >= 1
        first_call_kwargs = mock_thread_cls.call_args_list[0][1]
        assert first_call_kwargs["target"] == window._read_output
        assert first_call_kwargs["daemon"] is True
        assert str(window.start_server_button["state"]) == "disabled"
        assert str(window.stop_server_button["state"]) == "normal"
    finally:
        if window._poll_job is not None:
            window.after_cancel(window._poll_job)
        window.destroy()


@patch("lvk_paluworld_server_manager.gui.main_window.server.get_wsl_ip_address")
@patch("lvk_paluworld_server_manager.gui.main_window.server.start_server_visible")
def test_start_server_fetches_and_displays_ip_address(
    mock_start: MagicMock, mock_get_ip: MagicMock
) -> None:
    mock_get_ip.return_value = "172.20.16.1"
    window = _make_window()

    try:
        window.mode_var.set("visible")
        # Run _fetch_connection_info synchronously in the test thread
        window._on_start_server()
        if window._ip_poll_job is not None:
            window.after_cancel(window._ip_poll_job)
        window._fetch_connection_info()
        window._poll_ip_queue()

        assert "172.20.16.1" in window.ip_label["text"]
        assert "8211" in window.ip_label["text"]
    finally:
        window.destroy()


@patch("lvk_paluworld_server_manager.gui.main_window.server.stop_server")
def test_stop_server_clears_ip_label(mock_stop: MagicMock) -> None:
    window = _make_window()

    try:
        window.ip_label.config(text="連線位址：172.20.16.1:8211")
        window._set_running_state(True)
        window._on_stop_server()

        assert window.ip_label["text"] == ""
    finally:
        window.destroy()
