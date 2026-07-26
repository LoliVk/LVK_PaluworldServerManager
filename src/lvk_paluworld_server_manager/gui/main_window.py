"""Tkinter main window for the application."""

from __future__ import annotations

import queue
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext

from .. import server
from ..config import AppConfig, create_app_message

#: Sentinel placed on the output queue once the background process ends.
_OUTPUT_DONE = object()


class MainWindow(tk.Tk):
    """The application's primary window."""

    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self.config = config or AppConfig()
        self.title(self.config.title)
        self.geometry("480x520")
        self.resizable(False, False)

        self.configure(padx=24, pady=24)

        self._process: subprocess.Popen[str] | None = None
        self._output_queue: queue.Queue[object] = queue.Queue()
        self._poll_job: str | None = None

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

        self.mode_var = tk.StringVar(value="visible")
        mode_frame = tk.Frame(self)
        mode_frame.pack(pady=(8, 4))

        tk.Radiobutton(
            mode_frame,
            text="顯示終端機視窗",
            variable=self.mode_var,
            value="visible",
        ).pack(side="left", padx=4)

        tk.Radiobutton(
            mode_frame,
            text="背景執行",
            variable=self.mode_var,
            value="background",
        ).pack(side="left", padx=4)

        server_button_frame = tk.Frame(self)
        server_button_frame.pack(pady=8)

        self.start_server_button = tk.Button(
            server_button_frame,
            text="啟動伺服器 / Start Server",
            width=20,
            command=self._on_start_server,
        )
        self.start_server_button.pack(side="left", padx=8)

        self.stop_server_button = tk.Button(
            server_button_frame,
            text="停止伺服器 / Stop Server",
            width=20,
            command=self._on_stop_server,
            state="disabled",
        )
        self.stop_server_button.pack(side="left", padx=8)

        self.output_text = scrolledtext.ScrolledText(
            self,
            width=52,
            height=10,
            state="disabled",
            font=("Consolas", 9),
        )
        self.output_text.pack(pady=(8, 0))

        self.after(100, self._perform_environment_check)

    def _perform_environment_check(self) -> None:
        """Verify WSL/SteamCMD/PalServer are ready, disabling start if not."""
        result = server.check_environment()
        if not result.ok:
            missing = "\n".join(f"- {item}" for item in result.missing)
            messagebox.showerror(
                "缺少必要環境 / Missing Requirements",
                f"以下必要環境未偵測到，無法啟動伺服器：\n{missing}",
                parent=self,
            )
            self.start_server_button.config(state="disabled")

    def _set_running_state(self, running: bool) -> None:
        """Toggle the Start/Stop buttons to reflect the server state."""
        self.start_server_button.config(state="disabled" if running else "normal")
        self.stop_server_button.config(state="normal" if running else "disabled")

    def _append_output(self, text: str) -> None:
        """Append a line of text to the scrollable output box."""
        self.output_text.config(state="normal")
        self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END)
        self.output_text.config(state="disabled")

    def _on_start_server(self) -> None:
        """Handle the "Start Server" button click."""
        if self.mode_var.get() == "visible":
            server.start_server_visible()
            self._set_running_state(True)
        else:
            self._process = server.start_server_background()
            self._set_running_state(True)
            threading.Thread(target=self._read_output, daemon=True).start()
            self._poll_job = self.after(100, self._poll_output_queue)

    def _on_stop_server(self) -> None:
        """Handle the "Stop Server" button click."""
        server.stop_server()
        self._set_running_state(False)

    def _read_output(self) -> None:
        """Read the background process' stdout line by line (worker thread)."""
        process = self._process
        if process is None or process.stdout is None:
            self._output_queue.put(_OUTPUT_DONE)
            return

        for line in process.stdout:
            self._output_queue.put(line)
        self._output_queue.put(_OUTPUT_DONE)

    def _poll_output_queue(self) -> None:
        """Drain the output queue into the Text widget (main thread)."""
        done = False
        while True:
            try:
                item = self._output_queue.get_nowait()
            except queue.Empty:
                break

            if item is _OUTPUT_DONE:
                done = True
                break

            self._append_output(str(item))

        if done:
            self._poll_job = None
            self._set_running_state(False)
        else:
            self._poll_job = self.after(100, self._poll_output_queue)


def main() -> None:
    """Launch the Tkinter application."""
    app = MainWindow()
    app.mainloop()
