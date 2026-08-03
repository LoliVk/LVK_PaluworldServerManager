from __future__ import annotations

import io
import tkinter as tk
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from lvk_paluworld_server_manager.config import AppConfig
from lvk_paluworld_server_manager import server, world_options
from lvk_paluworld_server_manager.gui import MainWindow


def _widget_text(widget: tk.Misc) -> str:
    """Collect visible text from a widget tree for structural UI assertions."""
    parts: list[str] = []
    try:
        parts.append(str(widget.cget("text")))
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        parts.append(_widget_text(child))
    return "\n".join(parts)


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


@patch("lvk_paluworld_server_manager.gui.main_window.threading.Thread")
def test_navigation_switches_pages_and_moves_backup_action_to_backups_page(
    _mock_thread_cls: MagicMock,
) -> None:
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


@patch("lvk_paluworld_server_manager.gui.main_window.threading.Thread")
def test_world_navigation_creates_design_system_world_page(
    mock_thread_cls: MagicMock,
) -> None:
    from lvk_paluworld_server_manager.gui.pages import WorldPage

    window = _make_window()

    try:
        window.show_page("world")

        assert window._active_page == "world"
        assert isinstance(window.world_page, WorldPage)
        assert str(window.world_page._read_only_banner["background"]) == "#ffdad6"
        assert str(window.world_page.refresh_button["text"]) == "REFRESHING..."
        mock_thread_cls.assert_called()
    finally:
        window.destroy()


def test_world_queue_populates_selection_and_decoded_json(tmp_path: Path) -> None:
    from lvk_paluworld_server_manager.gui.main_window import _WORLD_OPERATION_DONE

    window = _make_window()

    try:
        world_dir = tmp_path / "AAAA"
        world_dir.mkdir()
        world = world_options.WorldSaveInfo(
            world_id="AAAA",
            world_option_path=world_dir / "WorldOption.sav",
            world_dir=world_dir,
        )
        window._world_scan_generation = 1
        window._world_workers_pending = 1
        window._world_queue.put(("worlds", 1, [world]))
        window._world_queue.put((_WORLD_OPERATION_DONE, 1))
        window._poll_world_queue()

        assert str(window.world_page._world_combo["state"]) == "readonly"
        assert window._worlds_by_id == {"AAAA": world}

        difficulty = next(field for field in world_options.SETTING_FIELDS if field.key == "difficulty")
        window.world_page._world_var.set("AAAA")
        window._world_decode_generation = 1
        window._world_workers_pending = 1
        decoded_gvas = MagicMock()
        window._world_queue.put(
            ("decoded", 1, "AAAA", decoded_gvas, 0x31, [(difficulty, "Normal")], '{"ok": true}')
        )
        window._world_queue.put((_WORLD_OPERATION_DONE, 1))
        window._poll_world_queue()

        assert str(window.world_page._json_text["state"]) == "disabled"
        assert '"ok": true' in window.world_page._json_text.get("1.0", tk.END)
        assert "json" in window.world_page._section_cards
        assert window._world_documents["AAAA"] == (decoded_gvas, 0x31)
    finally:
        window.destroy()


def test_world_queue_ignores_stale_decode_and_reports_current_error() -> None:
    from lvk_paluworld_server_manager.gui.main_window import _WORLD_OPERATION_DONE

    window = _make_window()

    try:
        window.world_page._world_var.set("AAAA")
        window._world_decode_generation = 2
        window._world_workers_pending = 2
        window._world_queue.put(("decoded", 1, "AAAA", MagicMock(), 0x31, [], '{"stale": true}'))
        window._world_queue.put((_WORLD_OPERATION_DONE, 1))
        window._world_queue.put(("decode_error", 2, "AAAA", "bad save"))
        window._world_queue.put((_WORLD_OPERATION_DONE, 2))
        window._poll_world_queue()

        assert not hasattr(window.world_page, "_json_text")
        assert "bad save" in str(window.world_page._details_status["text"])
    finally:
        window.destroy()


def test_world_page_protects_server_settings_and_disables_unverified_merge() -> None:
    window = _make_window()

    try:
        assert str(window.world_page.merge_button["state"]) == "disabled"
        assert str(window.world_page.import_button["text"]) == "IMPORT LOCAL WORLD"
        assert "SERVER SETTINGS PROTECTED" in _widget_text(window.world_page)
        assert "SAFE GAME SETTINGS MERGE" in _widget_text(window.world_page)
    finally:
        window.destroy()


def test_world_inspection_worker_backs_up_all_worlds_before_launching_pst(tmp_path: Path) -> None:
    from lvk_paluworld_server_manager.gui.main_window import _WORLD_OPERATION_DONE

    window = _make_window()
    world_dir = tmp_path / "AAAA"
    world_dir.mkdir()
    world = world_options.WorldSaveInfo(
        world_id="AAAA",
        world_option_path=world_dir / "WorldOption.sav",
        world_dir=world_dir,
    )
    backup_path = tmp_path / "Backups" / "savegames_20260802_010203.zip"

    try:
        with (
            patch(
                "lvk_paluworld_server_manager.gui.main_window.server.is_server_process_running",
                return_value=False,
            ),
            patch(
                "lvk_paluworld_server_manager.gui.main_window.server.get_save_games_windows_path",
                return_value=tmp_path,
            ),
            patch(
                "lvk_paluworld_server_manager.gui.main_window.world_options.backup_all_world_saves",
                return_value=backup_path,
            ) as mock_backup,
            patch(
                "lvk_paluworld_server_manager.gui.main_window.server.launch_pst"
            ) as mock_launch,
        ):
            window._backup_and_launch_pst(1, world)

        mock_backup.assert_called_once_with(
            tmp_path,
            tmp_path / "Backups",
            is_server_running=server.is_server_process_running,
        )
        mock_launch.assert_called_once_with(
            f"{server.SAVE_GAMES_PATH}/AAAA/WorldOption.sav"
        )
        items = [window._world_queue.get_nowait() for _ in range(5)]
        assert items[-2] == ("pst_closed", 1, "AAAA", backup_path)
        assert items[-1] == (_WORLD_OPERATION_DONE, 1)
    finally:
        window.destroy()


def test_world_inspection_does_not_launch_pst_when_backup_fails(tmp_path: Path) -> None:
    from lvk_paluworld_server_manager.gui.main_window import _WORLD_OPERATION_DONE

    window = _make_window()
    world_dir = tmp_path / "AAAA"
    world_dir.mkdir()
    world = world_options.WorldSaveInfo("AAAA", world_dir / "WorldOption.sav", world_dir)

    try:
        with (
            patch(
                "lvk_paluworld_server_manager.gui.main_window.server.is_server_process_running",
                return_value=False,
            ),
            patch(
                "lvk_paluworld_server_manager.gui.main_window.server.get_save_games_windows_path",
                return_value=tmp_path,
            ),
            patch(
                "lvk_paluworld_server_manager.gui.main_window.world_options.backup_all_world_saves",
                side_effect=world_options.BackupError("archive failed"),
            ),
            patch(
                "lvk_paluworld_server_manager.gui.main_window.server.launch_pst"
            ) as mock_launch,
        ):
            window._backup_and_launch_pst(1, world)

        mock_launch.assert_not_called()
        assert window._world_queue.get_nowait()[0] == "world_status"
        assert window._world_queue.get_nowait()[0] == "pst_error"
        assert window._world_queue.get_nowait() == (_WORLD_OPERATION_DONE, 1)
    finally:
        window.destroy()


def test_world_inspection_pst_close_prompts_before_restarting(tmp_path: Path) -> None:
    from lvk_paluworld_server_manager.gui.main_window import _WORLD_OPERATION_DONE

    window = _make_window()
    world_dir = tmp_path / "AAAA"
    world_dir.mkdir()
    world = world_options.WorldSaveInfo("AAAA", world_dir / "WorldOption.sav", world_dir)

    try:
        window.world_page.set_worlds([world])
        window.world_page._world_var.set("AAAA")
        window._world_decode_generation = 1
        window._world_workers_pending = 1
        window._world_queue.put(("pst_closed", 1, "AAAA", tmp_path / "backup.zip"))
        window._world_queue.put((_WORLD_OPERATION_DONE, 1))
        with (
            patch(
                "lvk_paluworld_server_manager.gui.main_window.messagebox.askyesno",
                return_value=False,
            ) as mock_prompt,
            patch.object(window, "_start_server_in_mode") as mock_start,
        ):
            window._poll_world_queue()

        mock_prompt.assert_called_once()
        mock_start.assert_not_called()
        assert str(window.world_page._world_combo["state"]) == "readonly"
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


def test_backups_stats_use_available_width_and_stack_when_needed() -> None:
    window = _make_window()

    try:
        page = window.backups_page
        assert [card.grid_info()["column"] for card in page._stat_cards] == [0, 1, 2]

        page._on_resize(SimpleNamespace(widget=page, width=480))
        assert [card.grid_info()["row"] for card in page._stat_cards] == [0, 1, 2]
        assert [card.grid_info()["column"] for card in page._stat_cards] == [0, 0, 0]

        page._on_resize(SimpleNamespace(widget=page, width=900))
        assert [card.grid_info()["row"] for card in page._stat_cards] == [0, 0, 0]
        assert [card.grid_info()["column"] for card in page._stat_cards] == [0, 1, 2]
    finally:
        window.destroy()


def test_backup_ledger_rows_share_the_header_column_widths() -> None:
    window = _make_window()
    archive = world_options.BackupArchive(
        path=Path("savegames_20260801_012417.zip"),
        created_at=datetime(2026, 8, 1, 1, 24),
        size_bytes=28_500_000,
        verified=True,
    )

    try:
        page = window.backups_page
        page.set_backup_archives([archive])

        for index in range(5):
            expected = page._ledger_header_row.grid_columnconfigure(index)["minsize"]
            assert page._archive_rows[0].grid_columnconfigure(index)["minsize"] == expected
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
        assert "+  CREATE SNAPSHOT" in button_texts
        assert "編輯世界設定 / Edit World Settings" not in button_texts
    finally:
        window.destroy()


@patch("lvk_paluworld_server_manager.gui.main_window.threading.Thread")
@patch("lvk_paluworld_server_manager.gui.main_window.world_options.list_backup_worlds")
@patch("lvk_paluworld_server_manager.gui.main_window.server.get_save_games_windows_path")
def test_backup_button_dispatches_background_worker_for_one_world(
    mock_save_path: MagicMock, mock_list_worlds: MagicMock, mock_thread_cls: MagicMock
) -> None:
    window = _make_window()
    world_path = Path("SaveGames/0/AAAA")
    mock_save_path.return_value = Path("SaveGames/0")
    mock_list_worlds.return_value = [
        world_options.BackupWorldInfo(
            world_id="AAAA", path=world_path, modified_at=datetime(2026, 1, 2, 3, 4, 5), size_bytes=1024
        )
    ]

    try:
        window._on_backup_all_world_saves()

        kwargs = mock_thread_cls.call_args.kwargs
        assert kwargs["target"] == window._backup_all_world_saves
        assert kwargs["args"] == ([world_path],)
        assert kwargs["daemon"] is True
        assert str(window.backup_worlds_button["state"]) == "disabled"
    finally:
        if window._backup_poll_job is not None:
            window.after_cancel(window._backup_poll_job)
        window.destroy()


def test_backup_world_selection_dialog_defaults_to_all_and_allows_partial_selection() -> None:
    from lvk_paluworld_server_manager.gui.dialogs import BackupWorldSelectionDialog

    window = _make_window()
    first_path = Path("SaveGames/0/AAAA")
    second_path = Path("SaveGames/0/BBBB")
    worlds = [
        world_options.BackupWorldInfo("AAAA", first_path, datetime(2026, 1, 2, 3, 4, 5), 1024),
        world_options.BackupWorldInfo("BBBB", second_path, datetime(2026, 1, 3, 4, 5, 6), 2048),
    ]

    try:
        dialog = BackupWorldSelectionDialog(window, worlds)
        try:
            assert all(selected.get() for selected in dialog._selected)
            dialog._clear_all()
            assert str(dialog._confirm_button["state"]) == "disabled"
            dialog._selected[0].set(True)
            dialog._update_confirm_state()
            dialog._confirm()
            assert dialog.selected_worlds == [first_path]
        finally:
            if dialog.winfo_exists():
                dialog.destroy()
    finally:
        window.destroy()


def test_diagnostic_environment_check_synchronizes_dashboard_badges() -> None:
    from lvk_paluworld_server_manager.server import EnvironmentCheckResult

    window = _make_window()

    try:
        window._apply_diagnostic_environment_check(
            EnvironmentCheckResult(
                wsl_available=True,
                steamcmd_installed=True,
                palserver_installed=True,
            )
        )

        assert window.environment_status_label["text"] == "ENVIRONMENT READY"
        assert window._environment_badges["steamcmd"]._text == "READY"
    finally:
        window.destroy()


@patch("lvk_paluworld_server_manager.gui.main_window.MainWindow._refresh_backup_inventory")
@patch("lvk_paluworld_server_manager.gui.main_window.BackupCompleteDialog")
def test_backup_queue_shows_completion_dialog_with_archive_path(
    mock_dialog: MagicMock,
    mock_refresh: MagicMock,
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
        mock_refresh.assert_called_once()
        assert str(window.backup_worlds_button["state"]) == "normal"
        assert window.backup_worlds_button["text"] == "+  CREATE SNAPSHOT"
    finally:
        window.destroy()


def test_backup_inventory_queue_updates_backups_page() -> None:
    window = _make_window()
    archive = world_options.BackupArchive(
        path=Path("savegames_20260102_030405.zip"),
        created_at=datetime(2026, 1, 2, 3, 4, 5),
        size_bytes=1024,
        verified=True,
    )

    try:
        window._backup_inventory_queue.put(("loaded", [archive]))
        window._backup_inventory_queue.put(__import__(
            "lvk_paluworld_server_manager.gui.main_window", fromlist=["_BACKUP_INVENTORY_DONE"]
        )._BACKUP_INVENTORY_DONE)
        window._poll_backup_inventory_queue()

        assert window.backups_page._total_value["text"] == "1"
        assert window.backups_page._inventory_status["text"] == "1 archive"
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


def test_world_option_editor_decodes_selected_world_in_background(tmp_path: object) -> None:
    from lvk_paluworld_server_manager.gui.dialogs.world_options import _WORLD_OPTIONS_DONE
    from lvk_paluworld_server_manager.gui.main_window import WorldOptionEditorDialog

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

            decoded_gvas = MagicMock()
            with patch.object(
                world_options, "decode_sav_bytes", return_value=(decoded_gvas, 0x31)
            ) as mock_decode:
                WorldOptionEditorDialog._decode_world(dialog, world)

            item = dialog._queue.get_nowait()
            assert item == ("decoded", (world, decoded_gvas, 0x31))
            assert dialog._queue.get_nowait() is _WORLD_OPTIONS_DONE
            mock_decode.assert_called_once_with(b"original")
        finally:
            dialog.destroy()
    finally:
        window.destroy()


def test_world_option_editor_reports_decode_failure(tmp_path: object) -> None:
    from lvk_paluworld_server_manager.gui.dialogs.world_options import _WORLD_OPTIONS_DONE
    from lvk_paluworld_server_manager.gui.main_window import WorldOptionEditorDialog

    window = _make_window()

    try:
        dialog = _make_world_option_dialog(window)
        try:
            world_dir = tmp_path / "AAAA"  # type: ignore[operator]
            world_dir.mkdir()
            world_option_path = world_dir / "WorldOption.sav"
            world_option_path.write_bytes(b"invalid")
            world = world_options.WorldSaveInfo(
                world_id="AAAA", world_option_path=world_option_path, world_dir=world_dir
            )

            with patch.object(
                world_options,
                "decode_sav_bytes",
                side_effect=world_options.SaveDecodeError("invalid save"),
            ):
                WorldOptionEditorDialog._decode_world(dialog, world)

            kind, message = dialog._queue.get_nowait()
            assert kind == "error"
            assert "invalid save" in message
            assert dialog._queue.get_nowait() is _WORLD_OPTIONS_DONE
        finally:
            dialog.destroy()
    finally:
        window.destroy()


def test_world_option_editor_displays_decoded_world() -> None:
    from lvk_paluworld_server_manager.gui.main_window import WorldOptionEditorDialog

    window = _make_window()

    try:
        dialog = _make_world_option_dialog(window)
        try:
            dialog._status_label = tk.Label(dialog)
            dialog._render_settings_form = MagicMock()
            dialog._set_json_content = MagicMock()
            decoded_gvas = MagicMock()
            decoded_gvas.properties = {"OptionWorldData": {}}

            with patch.object(world_options, "dump_gvas_json", return_value='{"parsed": true}'):
                WorldOptionEditorDialog._on_decoded(
                    dialog,
                    (MagicMock(), decoded_gvas, 0x31),
                )

            assert dialog._gvas_file is decoded_gvas
            dialog._render_settings_form.assert_called_once_with(decoded_gvas.properties)
            dialog._set_json_content.assert_called_once_with('{"parsed": true}')
            assert "Loaded successfully" in str(dialog._status_label["text"])
        finally:
            dialog.destroy()
    finally:
        window.destroy()


def test_world_option_editor_is_read_only() -> None:
    from lvk_paluworld_server_manager.gui.main_window import WorldOptionEditorDialog

    assert not hasattr(WorldOptionEditorDialog, "_on_save")
    assert not hasattr(WorldOptionEditorDialog, "_do_save")
    assert not hasattr(WorldOptionEditorDialog, "_on_saved")


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
