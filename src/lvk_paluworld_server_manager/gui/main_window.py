"""Tkinter main window for the application."""

from __future__ import annotations

import tkinter as tk

from ..config import AppConfig, create_app_message


class MainWindow(tk.Tk):
    """The application's primary window."""

    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self.config = config or AppConfig()
        self.title(self.config.title)
        self.geometry("480x320")
        self.resizable(False, False)

        self.configure(padx=24, pady=24)

        title_label = tk.Label(
            self,
            text=f"帕魯世界伺服器管理器\n{self.config.title}",
            font=("Segoe UI", 16, "bold"),
            anchor="center",
            justify="center",
        )
        title_label.pack(pady=(0, 8))

        subtitle_label = tk.Label(
            self,
            text=f"{create_app_message(self.config)}\n{self.config.title} 已準備就緒。",
            font=("Segoe UI", 11),
            wraplength=420,
            justify="center",
        )
        subtitle_label.pack(pady=(0, 16))

        button_frame = tk.Frame(self)
        button_frame.pack(pady=8)

        start_button = tk.Button(button_frame, text="開始使用 / Start", width=18)
        start_button.pack(side="left", padx=8)

        info_button = tk.Button(button_frame, text="關於 / About", width=18)
        info_button.pack(side="left", padx=8)


def main() -> None:
    """Launch the Tkinter application."""
    app = MainWindow()
    app.mainloop()
