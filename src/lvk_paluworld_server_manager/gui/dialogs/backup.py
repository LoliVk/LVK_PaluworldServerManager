"""Backup completion dialog."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox

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
                "所有世界存檔已備份。\n"
                f"位置：{archive_path}\n\n"
                "All world saves were backed up.\n"
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

