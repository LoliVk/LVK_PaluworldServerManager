from __future__ import annotations

import io
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace
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


def test_navigation_switches_pages_and_moves_backup_action_to_backups_page() -> None:
    window = _make_window()

    try:
        window.show_page("backups")

        assert window._active_page == "backups"
        assert window.backup_worlds_button is window.backups_page.backup_worlds_button
        assert window.backup_worlds_button.winfo_toplevel() is window
        assert window.backup_worlds_button.master is not window.dashboard_page.console_card.content
        assert all(window._navigation_icons[key] for key in window._pages)
    finally:
        window.destroy()


def test_dashboard_breakpoints_switch_between_single_and_two_column_layouts() -> None:
    window = _make_window()

    try:
        page = window.dashboard_page
        page._on_resize(SimpleNamespace(widget=page, width=520))
        assert page.console_card.grid_info()["row"] == 3
        assert page.console_card.grid_info()["column"] == 0

        page._on_resize(SimpleNamespace(widget=page, width=900))
        assert page.console_card.grid_info()["row"] == 1
        assert page.console_card.grid_info()["column"] == 0
        assert page.diagnostics_card.grid_info()["column"] == 1
    finally:
        window.destroy()


def test_navigation_uses_bottom_bar_below_compact_breakpoint() -> None:
    window = _make_window()

    try:
        window._on_window_resize(SimpleNamespace(widget=window, width=520))
        assert not window._sidebar.winfo_manager()
        assert window._bottom_navigation.winfo_manager() == "pack"

        window._on_window_resize(SimpleNamespace(widget=window, width=900))
        assert window._sidebar.winfo_manager() == "pack"
        assert not window._bottom_navigation.winfo_manager()
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


def test_console_controls_clear_output_and_resume_auto_scroll() -> None:
    window = _make_window()

    try:
        assert window.clear_console_button.winfo_toplevel() is window
        assert window.scroll_console_button.winfo_toplevel() is window
        window._append_output("line1\n")
        window.clear_console_button.invoke()
        assert window.output_text.get("1.0", tk.END).strip() == ""
        assert str(window.output_text["state"]) == "disabled"

        window._pause_console_auto_scroll()
        with patch.object(window.output_text, "see") as mock_see:
            window._append_output("line2\n")
            mock_see.assert_not_called()
            window.scroll_console_button.invoke()
            mock_see.assert_called_once_with(tk.END)
        assert window._console_auto_scroll is True
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

        assert "127.0.0.1:8211" in window.ip_label["text"]
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


@patch("lvk_paluworld_server_manager.gui.main_window.threading.Thread")
@patch("lvk_paluworld_server_manager.gui.main_window.server.is_server_process_running")
def test_update_button_dispatches_worker_when_server_is_stopped(
    mock_running: MagicMock, mock_thread_cls: MagicMock
) -> None:
    mock_running.return_value = False
    window = _make_window()

    try:
        window._on_update_server()

        mock_thread_cls.assert_called_once_with(target=window._update_server, daemon=True)
        assert str(window.update_server_button["state"]) == "disabled"
        assert "更新中" in str(window.update_server_button["text"])
    finally:
        if window._update_poll_job is not None:
            window.after_cancel(window._update_poll_job)
        window.destroy()


@patch("lvk_paluworld_server_manager.gui.main_window.messagebox.showerror")
@patch("lvk_paluworld_server_manager.gui.main_window.server.is_server_process_running")
def test_update_button_requires_stopped_server(
    mock_running: MagicMock, mock_showerror: MagicMock
) -> None:
    mock_running.return_value = True
    window = _make_window()

    try:
        window._on_update_server()

        mock_showerror.assert_called_once()
        assert str(window.update_server_button["state"]) == "normal"
    finally:
        window.destroy()


# ---------------------------------------------------------------------------
# Backup entry point / retained world-options editor
# ---------------------------------------------------------------------------


def test_main_window_shows_backup_button_without_editor_button() -> None:
    window = _make_window()

    try:
        def iter_widgets(widget: tk.Misc) -> object:
            for child in widget.winfo_children():
                yield child
                yield from iter_widgets(child)

        button_texts = [
            str(widget.cget("text")) for widget in iter_widgets(window) if isinstance(widget, tk.Button)
        ]
        assert "BACK UP ALL WORLD SAVES" in button_texts
        assert "編輯世界設定 / Edit World Settings" not in button_texts
    finally:
        window.destroy()


@patch("lvk_paluworld_server_manager.gui.main_window.threading.Thread")
def test_backup_button_dispatches_background_worker(mock_thread_cls: MagicMock) -> None:
    window = _make_window()

    try:
        window._on_backup_all_world_saves()

        kwargs = mock_thread_cls.call_args.kwargs
        assert kwargs["target"] == window._backup_all_world_saves
        assert kwargs["daemon"] is True
        assert str(window.backup_worlds_button["state"]) == "disabled"
    finally:
        if window._backup_poll_job is not None:
            window.after_cancel(window._backup_poll_job)
        window.destroy()


@patch("lvk_paluworld_server_manager.gui.main_window.BackupCompleteDialog")
def test_backup_queue_shows_completion_dialog_with_archive_path(
    mock_dialog: MagicMock,
) -> None:
    window = _make_window()
    archive_path = Path(r"\\wsl$\Ubuntu\home\lolivk\Backups\savegames_20260729_173724.zip")

    try:
        window._backup_queue.put(("saved", archive_path))
        window._backup_queue.put(__import__(
            "lvk_paluworld_server_manager.gui.main_window", fromlist=["_BACKUP_DONE"]
        )._BACKUP_DONE)
        window._poll_backup_queue()

        mock_dialog.assert_called_once_with(window, archive_path)
        assert str(window.backup_worlds_button["state"]) == "normal"
        assert window.backup_worlds_button["text"] == "備份所有世界存檔 / Backup All World Saves"
    finally:
        window.destroy()


@patch("lvk_paluworld_server_manager.gui.main_window.server.open_in_file_manager")
def test_backup_complete_dialog_opens_archive_parent_folder(mock_open: MagicMock) -> None:
    window = _make_window()
    archive_path = Path(r"\\wsl$\Ubuntu\home\lolivk\Backups\savegames_20260729_173724.zip")

    try:
        from lvk_paluworld_server_manager.gui.main_window import BackupCompleteDialog

        dialog = BackupCompleteDialog(window, archive_path)
        dialog._open_backup_folder()

        mock_open.assert_called_once_with(archive_path.parent)
        assert not dialog.winfo_exists()
    finally:
        window.destroy()


def _make_world_option_dialog(parent: MainWindow) -> object:
    from lvk_paluworld_server_manager.gui.main_window import WorldOptionEditorDialog

    dialog = WorldOptionEditorDialog.__new__(WorldOptionEditorDialog)
    tk.Toplevel.__init__(dialog, parent)
    dialog._parent = parent
    dialog._queue = __import__("queue").Queue()
    dialog._poll_job = None
    dialog._worlds = []
    dialog._gvas_file = None
    dialog._save_type = None
    dialog._field_vars = {}
    return dialog


def test_world_option_editor_reports_no_worlds_found() -> None:
    window = _make_window()

    try:
        dialog = _make_world_option_dialog(window)
        try:
            from lvk_paluworld_server_manager.gui.main_window import (
                WorldOptionEditorDialog,
            )

            dialog._status_label = tk.Label(dialog)
            dialog._world_combo = __import__("tkinter.ttk", fromlist=["Combobox"]).Combobox(
                dialog
            )
            WorldOptionEditorDialog._on_worlds_discovered(dialog, [])

            assert "找不到" in str(dialog._status_label["text"])
        finally:
            dialog.destroy()
    finally:
        window.destroy()


@patch("lvk_paluworld_server_manager.gui.main_window.server.is_server_process_running")
def test_world_option_editor_save_blocked_when_server_running(
    mock_running: MagicMock, tmp_path: object
) -> None:
    from lvk_paluworld_server_manager import world_options

    mock_running.return_value = True
    window = _make_window()

    try:
        dialog = _make_world_option_dialog(window)
        try:
            world_dir = tmp_path / "AAAA"  # type: ignore[operator]
            world_dir.mkdir()
            world_option_path = world_dir / "WorldOption.sav"
            world_option_path.write_bytes(b"original")
            world = world_options.WorldSaveInfo(
                world_id="AAAA", world_option_path=world_option_path, world_dir=world_dir
            )

            dialog._selected_world = world
            dialog._gvas_file = MagicMock()
            dialog._gvas_file.properties = {}
            dialog._save_type = 0x31

            dialog._do_save(world, {})

            item = dialog._queue.get_nowait()
            assert item[0] == "error"
            assert "PalServer" in item[1]
            assert world_option_path.read_bytes() == b"original"
        finally:
            dialog.destroy()
    finally:
        window.destroy()


def test_world_option_editor_json_tab_is_read_only() -> None:
    window = _make_window()

    try:
        dialog = _make_world_option_dialog(window)
        try:
            from lvk_paluworld_server_manager.gui.main_window import (
                WorldOptionEditorDialog,
            )

            json_frame = tk.Frame(dialog)
            WorldOptionEditorDialog._build_json_tab(dialog, json_frame)
            WorldOptionEditorDialog._set_json_content(dialog, '{"hello": "world"}')

            assert str(dialog._json_text["state"]) == "disabled"
            content = dialog._json_text.get("1.0", tk.END)
            assert "hello" in content
        finally:
            dialog.destroy()
    finally:
        window.destroy()
