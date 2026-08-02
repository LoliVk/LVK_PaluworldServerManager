"""Backup completion dialog."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from ...world_options import BackupWorldInfo

from ... import server


class BackupCompleteDialog(tk.Toplevel):
    """Modal confirmation with an action to reveal the completed backup."""

    def __init__(self, parent: tk.Misc, archive_path: Path) -> None:
        super().__init__(parent)
        self._archive_path = archive_path
        self.title("備份完成 / Backup Complete")
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.configure(padx=24, pady=20)

        tk.Label(
            self,
            text=(
                "世界存檔已備份。\n"
                f"位置：{archive_path}\n\n"
                "World saves were backed up.\n"
                f"Location: {archive_path}"
            ),
            justify="left",
            wraplength=460,
        ).pack(fill="x")

        button_frame = tk.Frame(self)
        button_frame.pack(pady=(18, 0))
        tk.Button(
            button_frame,
            text="開啟備份資料夾 / Open Backup Folder",
            command=self._open_backup_folder,
        ).pack(side="left", padx=(0, 8))
        tk.Button(button_frame, text="確定 / Close", width=14, command=self.destroy).pack(
            side="left"
        )

        self.grab_set()
        self.focus_set()

    def _open_backup_folder(self) -> None:
        """Open the folder containing the completed ZIP archive."""
        try:
            server.open_in_file_manager(self._archive_path.parent)
        except OSError as exc:
            messagebox.showerror(
                "無法開啟資料夾 / Unable to Open Folder",
                f"無法開啟備份資料夾：{self._archive_path.parent}\n\n"
                f"Could not open backup folder: {exc}",
                parent=self,
            )
            return
        self.destroy()


class BackupWorldSelectionDialog(tk.Toplevel):
    """Modal multi-select dialog for manual world-save snapshots."""

    def __init__(self, parent: tk.Misc, worlds: list[BackupWorldInfo]) -> None:
        super().__init__(parent)
        self.selected_worlds: list[Path] | None = None
        self._worlds = worlds
        self._selected = [tk.BooleanVar(value=True) for _world in worlds]
        self.title("選擇世界存檔 / Select World Saves")
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.configure(padx=24, pady=20)

        tk.Label(
            self,
            text="選擇要納入完整 ZIP 快照的世界。\nSelect worlds to include in the complete ZIP snapshot.",
            justify="left",
        ).pack(anchor="w")
        rows = tk.Frame(self)
        rows.pack(fill="x", pady=(14, 10))
        for world, selected in zip(worlds, self._selected, strict=True):
            tk.Checkbutton(
                rows,
                text=(
                    f"{world.world_id}    {world.modified_at:%Y-%m-%d %H:%M}"
                    f"    {self._format_size(world.size_bytes)}"
                ),
                variable=selected,
                anchor="w",
                command=self._update_confirm_state,
            ).pack(fill="x", anchor="w")

        actions = tk.Frame(self)
        actions.pack(fill="x", pady=(8, 0))
        tk.Button(actions, text="全選 / Select All", command=self._select_all).pack(side="left")
        tk.Button(actions, text="取消全選 / Clear All", command=self._clear_all).pack(
            side="left", padx=(8, 0)
        )
        self._confirm_button = tk.Button(
            actions, text="建立快照 / Create Snapshot", command=self._confirm
        )
        self._confirm_button.pack(side="right")
        tk.Button(actions, text="取消 / Cancel", command=self._cancel).pack(side="right", padx=(0, 8))
        self._update_confirm_state()
        self.grab_set()
        self.focus_set()

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        if size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

    def _select_all(self) -> None:
        for selected in self._selected:
            selected.set(True)
        self._update_confirm_state()

    def _clear_all(self) -> None:
        for selected in self._selected:
            selected.set(False)
        self._update_confirm_state()

    def _update_confirm_state(self) -> None:
        self._confirm_button.config(state="normal" if any(item.get() for item in self._selected) else "disabled")

    def _confirm(self) -> None:
        self.selected_worlds = [
            world.path for world, selected in zip(self._worlds, self._selected, strict=True) if selected.get()
        ]
        self.destroy()

    def _cancel(self) -> None:
        self.destroy()
