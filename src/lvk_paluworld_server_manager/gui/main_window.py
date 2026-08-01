"""Tkinter main window for the application."""

from __future__ import annotations

import queue
import subprocess
import sys
import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk
from typing import Any

from .. import server, world_options
from ..config import AppConfig, create_app_message

#: Sentinel placed on the output queue once the background process ends.
_OUTPUT_DONE = object()

#: Sentinel placed on the IP queue once the address lookup finishes.
_IP_DONE = object()

#: Sentinel placed on the world-option queue once a background task finishes.
_WORLD_OPTIONS_DONE = object()

#: Sentinel placed on the game-backup queue once a background task finishes.
_BACKUP_DONE = object()

#: Sentinel placed on the server-update queue once a background task finishes.
_UPDATE_DONE = object()

#: Palworld default game port shown alongside the IP address.
_PALWORLD_PORT: int = 8211


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


class MainWindow(tk.Tk):
    """The application's primary window."""

    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self.config = config or AppConfig()
        self.title(self.config.title)
        self.geometry("1060x720")
        self.minsize(900, 640)
        self.configure(background="#f3f3f3")

        self._process: subprocess.Popen[str] | None = None
        self._output_queue: queue.Queue[object] = queue.Queue()
        self._poll_job: str | None = None
        self._ip_queue: queue.Queue[object] = queue.Queue()
        self._ip_poll_job: str | None = None
        self._backup_queue: queue.Queue[object] = queue.Queue()
        self._backup_poll_job: str | None = None
        self._update_queue: queue.Queue[object] = queue.Queue()
        self._update_poll_job: str | None = None
        self._start_options_popup: tk.Toplevel | None = None

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

        self.mode_var = tk.StringVar(value="background")
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

        self.update_server_button = tk.Button(
            self,
            text="更新伺服器 / Update Server",
            width=25,
            command=self._on_update_server,
        )
        self.update_server_button.pack(pady=(0, 8))

        diagnostic_button = tk.Button(
            self,
            text="診斷資訊 / Diagnostic Info",
            width=25,
            command=self._on_show_diagnostics,
        )
        diagnostic_button.pack(pady=8)

        self.backup_worlds_button = tk.Button(
            self,
            text="備份所有世界存檔 / Backup All World Saves",
            width=25,
            command=self._on_backup_all_world_saves,
        )
        self.backup_worlds_button.pack(pady=(0, 8))

        ip_frame = tk.Frame(self)
        ip_frame.pack(pady=(4, 0))

        self.ip_label = tk.Label(
            ip_frame,
            text="",
            font=("Segoe UI", 10),
            foreground="#1a6e1a",
            anchor="center",
            justify="center",
            wraplength=420,
        )
        self.ip_label.pack()

        self.network_status_label = tk.Label(
            ip_frame,
            text="",
            font=("Segoe UI", 9),
            foreground="#333333",
            anchor="center",
            justify="center",
            wraplength=420,
        )
        self.network_status_label.pack(pady=(4, 0))

        self.output_text = scrolledtext.ScrolledText(
            self,
            width=52,
            height=10,
            state="disabled",
            font=("Consolas", 9),
        )
        self.output_text.pack(pady=(8, 0))

        # Keep the original controls and their bindings intact, then replace
        # only their visual container with the dashboard presentation.
        for widget in self.winfo_children():
            widget.destroy()
        self._build_dashboard()
        self.bind("<ButtonPress-1>", self._dismiss_start_options_on_main_click, add="+")
        self.bind("<Escape>", lambda _event: self._hide_start_options(), add="+")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._perform_environment_check)

    def _build_dashboard(self) -> None:
        """Build the high-density server dashboard without changing its behavior."""
        palette = {
            "background": "#f3f3f3",
            "card": "#ffffff",
            "border": "#bfcab8",
            "text": "#1a1c1c",
            "muted": "#40493d",
            "primary": "#005408",
            "primary_light": "#e5f4e2",
            "secondary": "#335ea1",
            "danger": "#b00000",
        }

        def card(parent: tk.Misc) -> tk.Frame:
            return tk.Frame(
                parent,
                background=palette["card"],
                highlightbackground=palette["border"],
                highlightthickness=1,
                padx=16,
                pady=16,
            )

        def section_title(parent: tk.Misc, text: str, accent: str) -> None:
            tk.Label(
                parent,
                text=text,
                background=palette["card"],
                foreground=accent,
                font=("Segoe UI", 10, "bold"),
                anchor="w",
            ).pack(fill="x", pady=(0, 12))

        content = tk.Frame(self, background=palette["background"], padx=24, pady=20)
        content.pack(fill="both", expand=True)

        header = tk.Frame(content, background=palette["background"])
        header.pack(fill="x", pady=(0, 16))
        tk.Label(
            header,
            text=self.config.title.upper(),
            background=palette["background"],
            foreground=palette["text"],
            font=("Segoe UI", 20, "bold"),
        ).pack(side="left")
        tk.Label(
            header,
            text="SYSTEM READY",
            background=palette["primary_light"],
            foreground=palette["primary"],
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=5,
        ).pack(side="right")

        hero = tk.Frame(content, background=palette["background"])
        hero.pack(fill="x", pady=(0, 16))
        hero.columnconfigure(0, weight=1)
        # Reserve a stable action column so the server status and controls
        # keep the 8:4 split shown in the dashboard reference.
        hero.columnconfigure(1, minsize=340)
        server_card = card(hero)
        server_card.grid(row=0, column=0, sticky="nsew", padx=(0, 24))
        hero_status = tk.Frame(server_card, background=palette["card"])
        hero_status.pack(fill="both", expand=True)
        self.server_status_label = tk.Label(
            hero_status,
            text="SERVER STOPPED",
            background=palette["card"],
            foreground=palette["muted"],
            font=("Segoe UI", 24, "bold"),
            anchor="w",
        )
        self.server_status_label.pack(anchor="w")
        tk.Label(
            hero_status,
            text=create_app_message(self.config),
            background=palette["card"],
            foreground=palette["muted"],
            font=("Segoe UI", 10),
            anchor="w",
        ).pack(anchor="w", pady=(4, 0))

        action_panel = tk.Frame(hero, background=palette["background"])
        action_panel.grid(row=0, column=1, sticky="new")
        self.mode_var = tk.StringVar(value="background")

        button_style = {
            "relief": "flat",
            "font": ("Segoe UI", 10, "bold"),
            "padx": 18,
            "pady": 10,
        }
        self.start_server_button = tk.Button(
            action_panel,
            text="▷  START SERVER",
            command=self._toggle_start_options,
            background=palette["primary"],
            activebackground="#003a04",
            foreground="#ffffff",
            activeforeground="#ffffff",
            **button_style,
        )
        self.start_server_button.pack(fill="x", pady=(0, 8))
        self.stop_server_button = tk.Button(
            action_panel,
            text="STOP SERVER",
            command=self._on_stop_server,
            state="disabled",
            background=palette["card"],
            activebackground="#ffdad6",
            foreground=palette["danger"],
            activeforeground=palette["danger"],
            highlightbackground=palette["danger"],
            highlightthickness=1,
            **button_style,
        )
        self.stop_server_button.pack(fill="x")

        dashboard = tk.Frame(content, background=palette["background"])
        dashboard.pack(fill="both", expand=True)
        dashboard.columnconfigure(0, weight=1)
        dashboard.columnconfigure(1, weight=1)
        dashboard.columnconfigure(2, weight=2)
        dashboard.rowconfigure(0, weight=1)

        diagnostics_card = card(dashboard)
        diagnostics_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        section_title(diagnostics_card, "SYSTEM DIAGNOSTICS", palette["primary"])
        self.environment_status_label = tk.Label(
            diagnostics_card,
            text="CHECKING ENVIRONMENT",
            background=palette["card"],
            foreground=palette["muted"],
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        )
        self.environment_status_label.pack(fill="x", pady=(0, 12))
        tk.Label(
            diagnostics_card,
            text="WSL 2 runtime\nSteamCMD installation\nPalServer executable",
            background=palette["card"],
            foreground=palette["muted"],
            justify="left",
            anchor="w",
            font=("Segoe UI", 10),
        ).pack(fill="x")
        diagnostic_button = tk.Button(
            diagnostics_card,
            text="VIEW DIAGNOSTICS",
            command=self._on_show_diagnostics,
            background=palette["secondary"],
            activebackground="#144688",
            foreground="#ffffff",
            activeforeground="#ffffff",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            pady=8,
        )
        diagnostic_button.pack(fill="x", side="bottom")

        network_card = card(dashboard)
        network_card.grid(row=0, column=1, sticky="nsew", padx=8)
        section_title(network_card, "NETWORK", palette["secondary"])
        self.ip_label = tk.Label(
            network_card,
            text="Connection addresses appear when the server starts.",
            background=palette["card"],
            foreground=palette["secondary"],
            font=("Consolas", 10),
            anchor="w",
            justify="left",
            wraplength=260,
        )
        self.ip_label.pack(fill="x", pady=(0, 12))
        self.network_status_label = tk.Label(
            network_card,
            text="Network checks will run automatically.",
            background=palette["card"],
            foreground=palette["muted"],
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=260,
        )
        self.network_status_label.pack(fill="x")
        self.update_server_button = tk.Button(
            network_card,
            text="UPDATE SERVER",
            command=self._on_update_server,
            background=palette["secondary"],
            activebackground="#144688",
            foreground="#ffffff",
            activeforeground="#ffffff",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            pady=8,
        )
        self.update_server_button.pack(fill="x", side="bottom")

        console_card = card(dashboard)
        console_card.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        section_title(console_card, "LIVE CONSOLE", palette["primary"])
        self.output_text = scrolledtext.ScrolledText(
            console_card,
            height=14,
            state="disabled",
            background="#ffffff",
            foreground="#111111",
            insertbackground="#111111",
            borderwidth=1,
            relief="solid",
            font=("Consolas", 10),
            padx=10,
            pady=8,
        )
        self.output_text.pack(fill="both", expand=True)
        self.backup_worlds_button = tk.Button(
            console_card,
            text="BACK UP ALL WORLD SAVES",
            command=self._on_backup_all_world_saves,
            background=palette["secondary"],
            activebackground="#144688",
            foreground="#ffffff",
            activeforeground="#ffffff",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            pady=8,
        )
        self.backup_worlds_button.pack(fill="x", pady=(12, 0))

    def _perform_environment_check(self) -> None:
        """Verify WSL/SteamCMD/PalServer are ready, disabling start if not."""
        result = server.check_environment()
        if not result.ok:
            self._hide_start_options()
            self.environment_status_label.config(
                text="ENVIRONMENT REQUIRES ATTENTION", foreground="#b00000"
            )
            missing = "\n".join(f"- {item}" for item in result.missing)
            messagebox.showerror(
                "缺少必要環境 / Missing Requirements",
                f"以下必要環境未偵測到，無法啟動伺服器：\n{missing}",
                parent=self,
            )
            self.start_server_button.config(state="disabled")
            self.update_server_button.config(state="disabled")
        else:
            self.environment_status_label.config(text="ENVIRONMENT READY", foreground="#005408")
            # Only proceed to network check when the core environment is ready.
            self.after(200, self._perform_network_check)

    def _perform_network_check(self) -> None:
        """Check WSL networking mode and Windows Firewall, guiding setup if needed."""
        net = server.check_network_setup()
        self._update_network_status(net)
        if not net.needs_setup:
            # Everything is already configured — don't interrupt the user.
            return
        NetworkSetupDialog(self, net, on_complete=self._perform_network_check)

    def _update_network_status(self, net: server.NetworkSetupResult) -> None:
        """Update the small network status summary shown below the IP label."""
        lines: list[str] = []
        if net.firewall_rule_exists:
            lines.append(f"防火牆：UDP {server.PALWORLD_PORT} 規則已存在")
        else:
            lines.append(f"防火牆：UDP {server.PALWORLD_PORT} 規則尚未設定")

        if net.mirrored_mode_supported:
            lines.append(
                f"WSL Mirrored 模式：{'已啟用' if net.mirrored_mode_enabled else '未啟用'}"
            )
        else:
            if net.socat_installed:
                lines.append("WSL Mirrored 模式：不支援，socat 已安裝")
            else:
                lines.append("WSL Mirrored 模式：不支援，socat 未安裝")

        if not net.is_admin:
            lines.append("管理員權限：否，若要新增防火牆規則請重新啟動為系統管理員")

        self.network_status_label.config(text="\n".join(lines))

    def _set_running_state(self, running: bool) -> None:
        """Toggle the Start/Stop buttons to reflect the server state."""
        if running:
            self._hide_start_options()
        self.start_server_button.config(state="disabled" if running else "normal")
        self.stop_server_button.config(state="normal" if running else "disabled")
        self.update_server_button.config(state="disabled" if running else "normal")
        self.server_status_label.config(
            text="SERVER ONLINE" if running else "SERVER STOPPED",
            foreground="#005408" if running else "#40493d",
        )

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

        self.ip_label.config(text="連線位址：查詢中...", foreground="#1a6e1a")
        threading.Thread(target=self._fetch_connection_info, daemon=True).start()
        self._ip_poll_job = self.after(100, self._poll_ip_queue)

    def _toggle_start_options(self) -> None:
        """Toggle the floating launch-mode menu without changing the dashboard layout."""
        if str(self.start_server_button["state"]) == "disabled":
            return
        if self._start_options_popup is not None:
            self._hide_start_options()
            return

        self.update_idletasks()
        popup = tk.Toplevel(self)
        popup.withdraw()
        popup.overrideredirect(True)
        popup.transient(self)
        popup.configure(background="#ffffff", highlightbackground="#e5e5e5", highlightthickness=1)

        for text, mode in (
            ("◉  Visible Mode", "visible"),
            ("▥  Background Execution", "background"),
        ):
            tk.Button(
                popup,
                text=text,
                command=lambda selected_mode=mode: self._start_server_in_mode(selected_mode),
                background="#ffffff",
                activebackground="#f3f3f3",
                foreground="#1a1c1c",
                relief="flat",
                anchor="w",
                font=("Segoe UI", 10),
                padx=16,
                pady=10,
            ).pack(fill="x")

        popup.bind("<Escape>", lambda _event: self._hide_start_options())
        popup.bind("<FocusOut>", self._on_start_options_focus_out, add="+")
        popup.update_idletasks()
        popup_x = self.start_server_button.winfo_rootx()
        popup_y = self.start_server_button.winfo_rooty() + self.start_server_button.winfo_height() + 8
        popup_width = max(340, self.start_server_button.winfo_width())
        popup.geometry(
            f"{popup_width}x{popup.winfo_reqheight()}+{popup_x}+{popup_y}"
        )
        self._start_options_popup = popup
        popup.deiconify()
        popup.lift()

    def _start_server_in_mode(self, mode: str) -> None:
        """Set the selected launch mode and run the existing start handler."""
        if str(self.start_server_button["state"]) == "disabled":
            return
        self.mode_var.set(mode)
        self._hide_start_options()
        self._on_start_server()

    def _hide_start_options(self) -> None:
        """Destroy the floating launch-mode menu when it is visible."""
        popup = self._start_options_popup
        self._start_options_popup = None
        if popup is not None and popup.winfo_exists():
            popup.destroy()

    def _dismiss_start_options_on_main_click(self, event: tk.Event[tk.Misc]) -> None:
        """Close the menu when the user clicks anywhere else in the main window."""
        if event.widget is not self.start_server_button:
            self._hide_start_options()

    def _on_start_options_focus_out(self, _event: tk.Event[tk.Misc]) -> None:
        """Close the menu after focus leaves the application window."""
        self.after_idle(self._hide_start_options_if_focus_left)

    def _hide_start_options_if_focus_left(self) -> None:
        """Keep the menu open while focus remains inside its floating window."""
        popup = self._start_options_popup
        if popup is None or not popup.winfo_exists():
            return
        focus = self.focus_displayof()
        if focus is None or str(focus.winfo_toplevel()) != str(popup):
            self._hide_start_options()

    def _on_close(self) -> None:
        """Close auxiliary floating UI before destroying the application window."""
        self._hide_start_options()
        self.destroy()

    def _on_stop_server(self) -> None:
        """Handle the "Stop Server" button click."""
        self._hide_start_options()
        server.stop_server()
        self._set_running_state(False)
        self.ip_label.config(text="")

    def _on_update_server(self) -> None:
        """Update Palworld Dedicated Server through SteamCMD in a worker thread."""
        self._hide_start_options()
        if server.is_server_process_running():
            messagebox.showerror(
                "伺服器仍在執行 / Server Is Running",
                "請先停止伺服器，再執行更新。\n\n"
                "Stop the server before updating it.",
                parent=self,
            )
            return

        self.start_server_button.config(state="disabled")
        self.stop_server_button.config(state="disabled")
        self.update_server_button.config(state="disabled", text="更新中... / Updating...")
        self._append_output("\n正在透過 SteamCMD 更新伺服器... / Updating server via SteamCMD...\n")
        threading.Thread(target=self._update_server, daemon=True).start()
        self._update_poll_job = self.after(100, self._poll_update_queue)

    def _update_server(self) -> None:
        """Run the server update outside Tk's event thread."""
        try:
            result = server.update_server()
            output = (result.stdout or "") + (result.stderr or "")
            self._update_queue.put(("result", result.returncode, output))
        except OSError as exc:
            self._update_queue.put(("error", str(exc)))
        self._update_queue.put(_UPDATE_DONE)

    def _poll_update_queue(self) -> None:
        """Display server-update output and completion state on the Tk thread."""
        done = False
        while True:
            try:
                item = self._update_queue.get_nowait()
            except queue.Empty:
                break

            if item is _UPDATE_DONE:
                done = True
                break

            kind, *payload = item  # type: ignore[misc]
            if kind == "result":
                returncode, output = payload
                if output:
                    self._append_output(str(output))
                    if not str(output).endswith("\n"):
                        self._append_output("\n")
                if returncode == 0:
                    messagebox.showinfo(
                        "更新完成 / Update Complete",
                        "伺服器已更新完成，現在可以啟動。\n\n"
                        "The server update completed. You can start it now.",
                        parent=self,
                    )
                else:
                    messagebox.showerror(
                        "更新失敗 / Update Failed",
                        "SteamCMD 更新失敗，請查看日誌中的詳細資訊。\n\n"
                        "SteamCMD failed to update the server. See the log for details.",
                        parent=self,
                    )
            elif kind == "error":
                messagebox.showerror(
                    "更新失敗 / Update Failed",
                    f"無法啟動 SteamCMD 更新：{payload[0]}",
                    parent=self,
                )

        if done:
            self._update_poll_job = None
            self._set_running_state(False)
            self.update_server_button.config(text="更新伺服器 / Update Server")
        else:
            self._update_poll_job = self.after(100, self._poll_update_queue)

    def _on_show_diagnostics(self) -> None:
        """Handle the "Diagnostic Info" button click."""
        DiagnosticDialog(self)

    # TODO: (Palworld 1.0) Keep the world-settings editor hidden from the main
    # window until PlM / Oodle support is complete. Re-add its button here once
    # the editor can safely read and write Palworld 1.0 save data.
    def _on_edit_world_options(self) -> None:
        """Open the retained world-settings editor when re-enabled in the UI."""
        WorldOptionEditorDialog(self)

    def _on_backup_all_world_saves(self) -> None:
        """Start a verified backup of every dedicated-server world save."""
        self.backup_worlds_button.config(state="disabled", text="備份中... / Backing up...")
        threading.Thread(target=self._backup_all_world_saves, daemon=True).start()
        self._backup_poll_job = self.after(100, self._poll_backup_queue)

    def _backup_all_world_saves(self) -> None:
        """Create the game backup in a worker thread."""
        try:
            save_games_root = server.get_save_games_windows_path()
            archive_path = world_options.backup_all_world_saves(
                save_games_root,
                save_games_root / "Backups",
                is_server_running=server.is_server_process_running,
            )
            self._backup_queue.put(("saved", archive_path))
        except world_options.WorldOptionsError as exc:
            self._backup_queue.put(("error", str(exc)))
        except Exception as exc:  # noqa: BLE001
            self._backup_queue.put(("error", f"備份失敗 / Backup failed: {exc}"))
        self._backup_queue.put(_BACKUP_DONE)

    def _poll_backup_queue(self) -> None:
        """Display completion or errors from the backup worker on the Tk thread."""
        done = False
        while True:
            try:
                item = self._backup_queue.get_nowait()
            except queue.Empty:
                break

            if item is _BACKUP_DONE:
                done = True
                break

            kind, payload = item  # type: ignore[misc]
            if kind == "saved":
                BackupCompleteDialog(self, payload)
            elif kind == "error":
                messagebox.showerror("備份失敗 / Backup Failed", str(payload), parent=self)

        if done:
            self._backup_poll_job = None
            self.backup_worlds_button.config(state="normal", text="備份所有世界存檔 / Backup All World Saves")
        else:
            self._backup_poll_job = self.after(100, self._poll_backup_queue)

    def _fetch_connection_info(self) -> None:
        """Query the WSL, host LAN, and public IP addresses in a worker thread."""
        wsl_ip = server.get_wsl_ip_address()
        host_ip = server.get_windows_host_ip_address()
        public_ip = server.get_public_ip_address()
        self._ip_queue.put((wsl_ip, host_ip, public_ip))
        self._ip_queue.put(_IP_DONE)

    def _poll_ip_queue(self) -> None:
        """Drain the IP queue and update the ip_label (main thread)."""
        done = False
        ip_info: tuple[str | None, str | None, str | None] | None = None

        while True:
            try:
                item = self._ip_queue.get_nowait()
            except queue.Empty:
                break

            if item is _IP_DONE:
                done = True
                break

            if isinstance(item, tuple):
                ip_info = item

        if done:
            self._ip_poll_job = None
            if ip_info:
                lines: list[str] = []
                wsl_ip, host_ip, public_ip = ip_info
                lines.append(f"本機 / Localhost：127.0.0.1:{_PALWORLD_PORT}")
                if wsl_ip:
                    lines.append(f"WSL IP：{wsl_ip}:{_PALWORLD_PORT}")
                if host_ip:
                    lines.append(f"本機 LAN IP：{host_ip}:{_PALWORLD_PORT}")
                if public_ip:
                    lines.append(f"公開 IP：{public_ip}:{_PALWORLD_PORT}")

                if lines:
                    self.ip_label.config(text="連線位址：\n" + "\n".join(lines), foreground="#1a6e1a")
                else:
                    self.ip_label.config(text="連線位址：無法取得", foreground="#b00000")
            else:
                self.ip_label.config(text="連線位址：無法取得", foreground="#b00000")
        else:
            self._ip_poll_job = self.after(100, self._poll_ip_queue)

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


class DiagnosticDialog(tk.Toplevel):
    """Modal dialog displaying comprehensive system diagnostics.

    Shows:
    * IP addresses (WSL, Windows LAN, Public)
    * Firewall status
    * Environment status (WSL, SteamCMD, PalServer)
    * External network connectivity

    All checks are performed in a background thread and the UI is updated
    asynchronously via queue-based communication.
    """

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self._parent = parent
        self._diagnostic_queue: queue.Queue[object] = queue.Queue()
        self._poll_job: str | None = None

        self.title("診斷資訊 / Diagnostic Info")
        self.geometry("550x600")
        self.resizable(False, False)
        self.grab_set()  # make modal
        self.configure(padx=20, pady=20)

        # ── Title ──────────────────────────────────────────────────────────
        tk.Label(
            self,
            text="系統診斷資訊\nSystem Diagnostics",
            font=("Segoe UI", 14, "bold"),
            justify="center",
        ).pack(pady=(0, 12))

        # ── IP Addresses section ──────────────────────────────────────────
        ip_frame = tk.LabelFrame(
            self, text="🌐 IP 位址 / IP Addresses", padx=10, pady=8
        )
        ip_frame.pack(fill="x", pady=(0, 8))

        self._localhost_ip_label = tk.Label(
            ip_frame,
            text=f"✅ 本機 / Localhost：127.0.0.1:{_PALWORLD_PORT}",
            anchor="w",
            foreground="#1a6e1a",
        )
        self._localhost_ip_label.pack(fill="x", pady=2)

        self._wsl_ip_label = tk.Label(
            ip_frame, text="⏳ WSL IP：查詢中...", anchor="w", foreground="#555555"
        )
        self._wsl_ip_label.pack(fill="x", pady=2)

        self._windows_ip_label = tk.Label(
            ip_frame, text="⏳ Windows LAN IP：查詢中...", anchor="w", foreground="#555555"
        )
        self._windows_ip_label.pack(fill="x", pady=2)

        self._public_ip_label = tk.Label(
            ip_frame, text="⏳ 公開 IP / Public IP：查詢中...", anchor="w", foreground="#555555"
        )
        self._public_ip_label.pack(fill="x", pady=2)

        # ── Firewall section ──────────────────────────────────────────────
        firewall_frame = tk.LabelFrame(
            self, text="🛡️ 防火牆 / Firewall", padx=10, pady=8
        )
        firewall_frame.pack(fill="x", pady=(0, 8))

        self._firewall_label = tk.Label(
            firewall_frame, text="⏳ UDP 8211 防火牆規則：查詢中...", anchor="w", foreground="#555555"
        )
        self._firewall_label.pack(fill="x", pady=2)

        # Firewall action button frame (will be shown after diagnostics complete)
        self._firewall_button_frame = tk.Frame(firewall_frame)
        self._firewall_button_frame.pack(fill="x", pady=(4, 0))

        # ── Environment section ───────────────────────────────────────────
        env_frame = tk.LabelFrame(
            self, text="⚙️ 環境狀態 / Environment Status", padx=10, pady=8
        )
        env_frame.pack(fill="x", pady=(0, 8))

        self._wsl_status_label = tk.Label(
            env_frame, text="⏳ WSL：查詢中...", anchor="w", foreground="#555555"
        )
        self._wsl_status_label.pack(fill="x", pady=2)

        self._steamcmd_label = tk.Label(
            env_frame, text="⏳ SteamCMD：查詢中...", anchor="w", foreground="#555555"
        )
        self._steamcmd_label.pack(fill="x", pady=2)

        self._palserver_label = tk.Label(
            env_frame, text="⏳ PalServer：查詢中...", anchor="w", foreground="#555555"
        )
        self._palserver_label.pack(fill="x", pady=2)

        # ── Network Connectivity section ──────────────────────────────────
        connectivity_frame = tk.LabelFrame(
            self, text="🌍 網路連線 / Network Connectivity", padx=10, pady=8
        )
        connectivity_frame.pack(fill="x", pady=(0, 8))

        self._connectivity_label = tk.Label(
            connectivity_frame, text="⏳ 外部連線：測試中...", anchor="w", foreground="#555555"
        )
        self._connectivity_label.pack(fill="x", pady=2)

        # ── WSL Network Setup section ─────────────────────────────────────
        network_frame = tk.LabelFrame(
            self, text="🔧 WSL 網路設定 / WSL Network Setup", padx=10, pady=8
        )
        network_frame.pack(fill="x", pady=(0, 8))

        self._mirrored_mode_label = tk.Label(
            network_frame, text="⏳ Mirrored 模式：查詢中...", anchor="w", foreground="#555555"
        )
        self._mirrored_mode_label.pack(fill="x", pady=2)

        self._admin_label = tk.Label(
            network_frame, text="⏳ 管理員權限：查詢中...", anchor="w", foreground="#555555"
        )
        self._admin_label.pack(fill="x", pady=2)

        # ── Copy Info button ──────────────────────────────────────────────
        button_frame = tk.Frame(self)
        button_frame.pack(pady=(8, 0))

        self._copy_button = tk.Button(
            button_frame,
            text="複製資訊 / Copy Info",
            width=20,
            state="disabled",
            command=self._copy_to_clipboard,
        )
        self._copy_button.pack(side="left", padx=4)

        tk.Button(
            button_frame,
            text="關閉 / Close",
            width=20,
            command=self.destroy,
        ).pack(side="left", padx=4)

        self.transient(parent)
        self.wait_visibility()
        self.lift()

        # Start diagnostic checks in background thread
        threading.Thread(target=self._run_diagnostics, daemon=True).start()
        self._poll_job = self.after(100, self._poll_diagnostic_queue)

    def _run_diagnostics(self) -> None:
        """Perform all diagnostic checks in a background thread."""
        info = server.get_all_diagnostic_info()
        self._diagnostic_queue.put(info)
        self._diagnostic_queue.put(_OUTPUT_DONE)

    def _poll_diagnostic_queue(self) -> None:
        """Poll the diagnostic queue and update UI labels (main thread)."""
        done = False
        diagnostic_info: server.DiagnosticInfo | None = None

        while True:
            try:
                item = self._diagnostic_queue.get_nowait()
            except queue.Empty:
                break

            if item is _OUTPUT_DONE:
                done = True
                break

            if isinstance(item, server.DiagnosticInfo):
                diagnostic_info = item

        if done and diagnostic_info:
            self._update_ui(diagnostic_info)
            self._poll_job = None
        else:
            self._poll_job = self.after(100, self._poll_diagnostic_queue)

    def _update_ui(self, info: server.DiagnosticInfo) -> None:
        """Update all labels with diagnostic results."""
        # Store for clipboard copy
        self._diagnostic_info = info
        self._copy_button.config(state="normal")

        # IP Addresses
        if info.wsl_ip:
            self._wsl_ip_label.config(
                text=f"✅ WSL IP：{info.wsl_ip}:{_PALWORLD_PORT}",
                foreground="#1a6e1a",
            )
        else:
            self._wsl_ip_label.config(
                text="❌ WSL IP：無法取得", foreground="#b00000"
            )

        if info.windows_ip:
            self._windows_ip_label.config(
                text=f"✅ Windows LAN IP：{info.windows_ip}:{_PALWORLD_PORT}",
                foreground="#1a6e1a",
            )
        else:
            self._windows_ip_label.config(
                text="❌ Windows LAN IP：無法取得", foreground="#b00000"
            )

        if info.public_ip:
            self._public_ip_label.config(
                text=f"✅ 公開 IP / Public IP：{info.public_ip}:{_PALWORLD_PORT}",
                foreground="#1a6e1a",
            )
        else:
            self._public_ip_label.config(
                text="❌ 公開 IP / Public IP：無法取得", foreground="#b00000"
            )

        # Firewall
        if info.firewall_rule_exists:
            self._firewall_label.config(
                text="✅ UDP 8211 防火牆規則：已設定", foreground="#1a6e1a"
            )
            # Hide action buttons if rule already exists
            for widget in self._firewall_button_frame.winfo_children():
                widget.destroy()
        else:
            self._firewall_label.config(
                text="❌ UDP 8211 防火牆規則：未設定", foreground="#b00000"
            )
            # Show appropriate action button based on admin rights
            self._show_firewall_action_buttons(info.network_setup.is_admin)

        # Environment
        env = info.environment_check
        if env.wsl_available:
            self._wsl_status_label.config(
                text="✅ WSL：已安裝", foreground="#1a6e1a"
            )
        else:
            self._wsl_status_label.config(
                text="❌ WSL：未安裝", foreground="#b00000"
            )

        if env.steamcmd_installed:
            self._steamcmd_label.config(
                text="✅ SteamCMD：已安裝", foreground="#1a6e1a"
            )
        else:
            self._steamcmd_label.config(
                text="❌ SteamCMD：未安裝", foreground="#b00000"
            )

        if env.palserver_installed:
            self._palserver_label.config(
                text="✅ PalServer：已安裝", foreground="#1a6e1a"
            )
        else:
            self._palserver_label.config(
                text="❌ PalServer：未安裝", foreground="#b00000"
            )

        # Connectivity
        if info.external_connectivity:
            self._connectivity_label.config(
                text="✅ 外部連線：正常", foreground="#1a6e1a"
            )
        else:
            self._connectivity_label.config(
                text="❌ 外部連線：無法連線至外部網路", foreground="#b00000"
            )

        # Network Setup
        net = info.network_setup
        if net.mirrored_mode_supported:
            if net.mirrored_mode_enabled:
                self._mirrored_mode_label.config(
                    text="✅ Mirrored 模式：已啟用", foreground="#1a6e1a"
                )
            else:
                self._mirrored_mode_label.config(
                    text="⚠️ Mirrored 模式：未啟用（建議啟用）", foreground="#b05000"
                )
        else:
            if net.socat_installed:
                self._mirrored_mode_label.config(
                    text="✅ Mirrored 模式：不支援，socat 已安裝", foreground="#1a6e1a"
                )
            else:
                self._mirrored_mode_label.config(
                    text="⚠️ Mirrored 模式：不支援，socat 未安裝", foreground="#b05000"
                )

        if net.is_admin:
            self._admin_label.config(
                text="✅ 管理員權限：是", foreground="#1a6e1a"
            )
        else:
            self._admin_label.config(
                text="⚠️ 管理員權限：否（部分功能需要管理員權限）", foreground="#b05000"
            )

    def _show_firewall_action_buttons(self, is_admin: bool) -> None:
        """Show appropriate firewall action buttons based on admin rights.
        
        Args:
            is_admin: Whether the current process has administrator rights.
        """
        # Clear existing buttons
        for widget in self._firewall_button_frame.winfo_children():
            widget.destroy()

        if is_admin:
            # Show "Add Firewall Rule" button
            add_rule_btn = tk.Button(
                self._firewall_button_frame,
                text="➕ 新增防火牆規則 / Add Firewall Rule",
                command=self._on_add_firewall_rule,
                background="#1a6e1a",
                foreground="white",
                activebackground="#145714",
                activeforeground="white",
            )
            add_rule_btn.pack(side="left", padx=(0, 4))
        else:
            # Show "Open Firewall Settings" button
            open_settings_btn = tk.Button(
                self._firewall_button_frame,
                text="⚙️ 開啟防火牆設定 / Open Firewall Settings",
                command=self._on_open_firewall_settings,
            )
            open_settings_btn.pack(side="left", padx=(0, 4))
            
            # Show helper label
            helper_label = tk.Label(
                self._firewall_button_frame,
                text="（請手動新增 UDP 8211 輸入規則）",
                foreground="#555555",
                font=("Segoe UI", 8),
            )
            helper_label.pack(side="left", padx=(4, 0))

    def _on_add_firewall_rule(self) -> None:
        """Handle the "Add Firewall Rule" button click."""
        success = server.add_firewall_rule()
        
        if success:
            messagebox.showinfo(
                "設定成功 / Success",
                f"防火牆規則已成功新增。\nFirewall rule for UDP {server.PALWORLD_PORT} added successfully.",
                parent=self,
            )
            # Refresh diagnostics
            threading.Thread(target=self._run_diagnostics, daemon=True).start()
            self._poll_job = self.after(100, self._poll_diagnostic_queue)
        else:
            messagebox.showerror(
                "設定失敗 / Failed",
                "無法新增防火牆規則。請確認您擁有管理員權限。\nFailed to add firewall rule. Please ensure you have administrator rights.",
                parent=self,
            )

    def _on_open_firewall_settings(self) -> None:
        """Handle the "Open Firewall Settings" button click."""
        server.open_windows_firewall_settings()
        
        messagebox.showinfo(
            "設定指引 / Setup Guide",
            f"Windows 防火牆設定視窗已開啟。\n\n請依照以下步驟手動新增規則：\n"
            f"1. 點選左側「輸入規則」/ 'Inbound Rules'\n"
            f"2. 點選右側「新增規則...」/ 'New Rule...'\n"
            f"3. 選擇「連接埠」/ 'Port'，按下一步\n"
            f"4. 選擇 UDP，輸入特定本機連接埠：{server.PALWORLD_PORT}\n"
            f"5. 選擇「允許連線」/ 'Allow the connection'\n"
            f"6. 套用到所有設定檔（網域、私人、公用）\n"
            f"7. 名稱輸入：{server.FIREWALL_RULE_NAME}\n\n"
            f"完成後請關閉並重新開啟診斷視窗以驗證設定。",
            parent=self,
        )

    def _copy_to_clipboard(self) -> None:
        """Copy all diagnostic information to clipboard."""
        if not hasattr(self, "_diagnostic_info"):
            return

        info = self._diagnostic_info
        lines = [
            "=" * 50,
            "Palworld Server Manager - 診斷資訊",
            "Diagnostic Information",
            "=" * 50,
            "",
            "【IP 位址 / IP Addresses】",
            f"  WSL IP: {info.wsl_ip or 'N/A'}:{_PALWORLD_PORT}",
            f"  Windows LAN IP: {info.windows_ip or 'N/A'}:{_PALWORLD_PORT}",
            f"  Public IP: {info.public_ip or 'N/A'}:{_PALWORLD_PORT}",
            "",
            "【防火牆 / Firewall】",
            f"  UDP 8211 Rule: {'已設定 (Configured)' if info.firewall_rule_exists else '未設定 (Not configured)'}",
            "",
            "【環境狀態 / Environment】",
            f"  WSL: {'已安裝 (Installed)' if info.environment_check.wsl_available else '未安裝 (Not installed)'}",
            f"  SteamCMD: {'已安裝 (Installed)' if info.environment_check.steamcmd_installed else '未安裝 (Not installed)'}",
            f"  PalServer: {'已安裝 (Installed)' if info.environment_check.palserver_installed else '未安裝 (Not installed)'}",
            "",
            "【網路連線 / Network】",
            f"  External Connectivity: {'正常 (OK)' if info.external_connectivity else '異常 (Failed)'}",
            f"  Mirrored Mode Supported: {'是 (Yes)' if info.network_setup.mirrored_mode_supported else '否 (No)'}",
            f"  Mirrored Mode Enabled: {'是 (Yes)' if info.network_setup.mirrored_mode_enabled else '否 (No)'}",
            f"  Admin Rights: {'是 (Yes)' if info.network_setup.is_admin else '否 (No)'}",
            "",
            "=" * 50,
        ]
        
        text = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(text)
        
        messagebox.showinfo(
            "複製成功 / Copied",
            "診斷資訊已複製到剪貼簿。\nDiagnostic info copied to clipboard.",
            parent=self,
        )


class NetworkSetupDialog(tk.Toplevel):
    """Modal dialog that guides the user through WSL network configuration.

    The dialog shows the current state of:

    * WSL Mirrored networking mode (``~/.wslconfig``)
    * Windows Firewall inbound rule for Palworld UDP 8211

    and offers a single "立即自動設定 / Auto-Configure" button that applies all
    pending actions in one click.  If administrator rights are missing the
    button is replaced by a notice asking the user to restart as admin.
    """

    def __init__(
        self,
        parent: tk.Tk,
        net: server.NetworkSetupResult,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._net = net
        self._parent = parent
        self._on_complete = on_complete

        self.title("網路設定 / Network Setup")
        self.geometry("500x420")
        self.resizable(False, False)
        self.grab_set()  # make modal
        self.configure(padx=20, pady=20)

        # ── Title ──────────────────────────────────────────────────────────
        tk.Label(
            self,
            text="WSL 網路設定精靈\nNetwork Setup Wizard",
            font=("Segoe UI", 14, "bold"),
            justify="center",
        ).pack(pady=(0, 12))

        # ── Status grid ───────────────────────────────────────────────────
        status_frame = tk.LabelFrame(
            self, text="目前狀態 / Current Status", padx=10, pady=8
        )
        status_frame.pack(fill="x", pady=(0, 10))

        def _row(label: str, ok: bool) -> None:
            icon = "✅" if ok else "❌"
            colour = "#1a6e1a" if ok else "#b00000"
            tk.Label(status_frame, text=f"{icon}  {label}", foreground=colour,
                     anchor="w").pack(fill="x")

        # Networking mode row
        if net.mirrored_mode_supported:
            _row(
                "Mirrored 網路模式（已在 ~/.wslconfig 設定）",
                net.mirrored_mode_enabled,
            )
        else:
            _row(
                "Mirrored 模式（此系統版本不支援，需使用 socat 備用）",
                net.socat_installed,
            )

        _row(f"Windows 防火牆規則 UDP {server.PALWORLD_PORT}", net.firewall_rule_exists)

        # ── Pending actions ───────────────────────────────────────────────
        actions_frame = tk.LabelFrame(
            self, text="將執行的動作 / Pending Actions", padx=10, pady=8
        )
        actions_frame.pack(fill="x", pady=(0, 10))

        if net.pending_actions:
            for action in net.pending_actions:
                tk.Label(
                    actions_frame,
                    text=f"• {action}",
                    wraplength=440,
                    justify="left",
                    anchor="w",
                ).pack(fill="x", pady=1)
        else:
            tk.Label(
                actions_frame,
                text="（無需執行任何動作）",
                foreground="#555555",
            ).pack()

        # ── Firewall disclaimer ───────────────────────────────────────────
        if net.pending_actions and not net.firewall_rule_exists:
            disclaimer_frame = tk.LabelFrame(
                self,
                text="⚠️  風險免責聲明 / Disclaimer",
                padx=10,
                pady=8,
                foreground="#b05000",
            )
            disclaimer_frame.pack(fill="x", pady=(0, 10))
            tk.Label(
                disclaimer_frame,
                text=(
                    "本程式將透過 netsh 在 Windows Defender 防火牆中新增「輸入規則」，"
                    "允許外部裝置連線至本機 UDP 連接埠 8211（Palworld 遊戲伺服器）。\n\n"
                    "請注意以下風險：\n"
                    "• 開放防火牆連接埠將允許網路上的裝置直接連線至您的伺服器。\n"
                    "• 若您位於公共網路（咖啡廳、學校等），請謹慎評估是否執行。\n"
                    "• 本程式不對因開放連接埠所造成的任何安全問題負責。\n"
                    "• 您可隨時前往 Windows Defender 防火牆手動移除此規則。"
                ),
                wraplength=440,
                justify="left",
                foreground="#7a3000",
                anchor="w",
            ).pack(fill="x")

        # ── Admin notice / action button ──────────────────────────────────
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=(4, 0))

        if net.pending_actions:
            if not net.is_admin:
                tk.Label(
                    btn_frame,
                    text=(
                        "⚠️  新增防火牆規則需要系統管理員權限。\n"
                        "請以「系統管理員身份執行」重新啟動本程式。"
                    ),
                    foreground="#b05000",
                    wraplength=440,
                    justify="center",
                ).pack(pady=(0, 8))

                tk.Button(
                    btn_frame,
                    text="以系統管理員重新啟動 / Restart as Admin",
                    width=34,
                    command=self._restart_as_admin,
                ).pack(pady=(0, 4))
            else:
                self._progress_label = tk.Label(
                    btn_frame,
                    text="",
                    font=("Segoe UI", 9),
                    foreground="#555555",
                    wraplength=440,
                    justify="center",
                )
                self._progress_label.pack(pady=(0, 4))

                self._apply_btn = tk.Button(
                    btn_frame,
                    text="立即自動設定 / Auto-Configure Now",
                    width=34,
                    background="#1a6e1a",
                    foreground="white",
                    activebackground="#145714",
                    activeforeground="white",
                    command=self._apply_setup,
                )
                self._apply_btn.pack(pady=(0, 4))

        tk.Button(
            btn_frame,
            text="稍後設定 / Skip for Now",
            width=20,
            command=self.destroy,
        ).pack()

        self.transient(parent)
        self.wait_visibility()
        self.lift()

    # ── Private helpers ────────────────────────────────────────────────────

    def _apply_setup(self) -> None:
        """Ask for final confirmation, then apply all pending actions in a background thread."""
        # Build a confirmation message that includes the disclaimer.
        confirm_lines = ["即將執行以下操作，請確認後繼續：\n"]
        for action in self._net.pending_actions:
            confirm_lines.append(f"• {action}")
        if not self._net.firewall_rule_exists:
            confirm_lines.append(
                "\n【風險提醒】開放 UDP 8211 防火牆連接埠將允許外部裝置連線至本機伺服器。"
                "\n本程式不對因此產生的安全風險負責，請確認您了解並同意上述風險後再繼續。"
            )
        confirmed = messagebox.askyesno(
            "確認執行 / Confirm",
            "\n".join(confirm_lines),
            icon="warning",
            parent=self,
        )
        if not confirmed:
            return

        # Disable the button and show initial progress so the user sees feedback
        # immediately.  The heavy work runs in a daemon thread so the Tkinter
        # event loop (and therefore the window) stays responsive.
        self._apply_btn.config(state="disabled", text="設定中，請稍候...")
        self._progress_label.config(text="正在準備設定...")
        threading.Thread(target=self._do_apply, daemon=True).start()

    def _do_apply(self) -> None:
        """Background thread: run each setup action and collect any errors."""
        errors: list[str] = []

        # 1. Enable Mirrored Mode (Win 11 22H2+)
        if self._net.mirrored_mode_supported and not self._net.mirrored_mode_enabled:
            self.after(
                0,
                lambda: self._progress_label.config(
                    text="正在設定 WSL Mirrored 網路模式（wsl --shutdown）..."
                ),
            )
            try:
                server.enable_mirrored_mode()
            except Exception as exc:  # noqa: BLE001
                errors.append(f"無法啟用 Mirrored Mode：{exc}")

        # 2. Add firewall rule
        if not self._net.firewall_rule_exists:
            self.after(
                0,
                lambda: self._progress_label.config(
                    text="正在新增 Windows 防火牆輸入規則..."
                ),
            )
            ok = server.add_firewall_rule()
            if not ok:
                errors.append(
                    f"無法新增防火牆規則「{server.FIREWALL_RULE_NAME}」。\n"
                    "請確認程式以系統管理員身份執行。"
                )

        # Hand results back to the main thread via after()
        self.after(0, lambda: self._on_apply_done(errors))

    def _on_apply_done(self, errors: list[str]) -> None:
        """Main-thread callback invoked once _do_apply() finishes."""
        if errors:
            self._progress_label.config(text="")
            self._apply_btn.config(
                state="normal", text="立即自動設定 / Auto-Configure Now"
            )
            messagebox.showerror(
                "設定失敗 / Setup Failed",
                "部分設定未能完成：\n\n" + "\n\n".join(errors),
                parent=self,
            )
        else:
            msg = "網路設定完成！\n"
            if self._net.mirrored_mode_supported and not self._net.mirrored_mode_enabled:
                msg += "WSL 已切換為 Mirrored 網路模式並重新啟動。\n"
            if not self._net.firewall_rule_exists:
                msg += f"防火牆規則 UDP {server.PALWORLD_PORT} 已新增。\n"
            messagebox.showinfo("設定完成 / Setup Complete", msg.strip(), parent=self)
            self.destroy()
            if self._on_complete is not None:
                self._on_complete()

    def _restart_as_admin(self) -> None:
        """Re-launch the application with administrator privileges."""
        server.restart_as_admin()
        self._parent.destroy()
        sys.exit(0)


class WorldOptionEditorDialog(tk.Toplevel):
    """Modal dialog for discovering, viewing, and editing ``WorldOption.sav``.

    Follows the same worker-thread + :class:`queue.Queue` + :meth:`after`
    pattern as :class:`DiagnosticDialog`/:class:`NetworkSetupDialog` so all
    GVAS decode/encode/backup work happens off the Tk main thread.

    The dialog never guesses which world to edit: it scans the dedicated
    server's ``SaveGames/0`` directory and lets the user choose. Saving is
    refused whenever the server appears to be running, and every successful
    save first creates a verified, timestamped ZIP backup of the *entire*
    selected world directory.
    """

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self._parent = parent
        self._queue: queue.Queue[object] = queue.Queue()
        self._poll_job: str | None = None

        self._worlds: list[world_options.WorldSaveInfo] = []
        self._gvas_file: Any | None = None  # GvasFile once decoded
        self._save_type: int | None = None
        self._field_vars: dict[str, tk.Variable] = {}

        self.title("編輯世界設定 / Edit World Settings")
        self.geometry("640x640")
        self.resizable(False, False)
        self.grab_set()
        self.configure(padx=16, pady=16)

        tk.Label(
            self,
            text="世界設定編輯器\nWorld Settings Editor",
            font=("Segoe UI", 14, "bold"),
            justify="center",
        ).pack(pady=(0, 10))

        selector_frame = tk.Frame(self)
        selector_frame.pack(fill="x", pady=(0, 8))

        tk.Label(selector_frame, text="選擇世界 / World:").pack(side="left")
        self._world_var = tk.StringVar(value="")
        self._world_combo = ttk.Combobox(
            selector_frame, textvariable=self._world_var, state="disabled", width=40
        )
        self._world_combo.pack(side="left", padx=(6, 6))
        self._world_combo.bind("<<ComboboxSelected>>", self._on_world_selected)

        self._status_label = tk.Label(
            self, text="正在掃描世界存檔... / Scanning for worlds...", foreground="#555555"
        )
        self._status_label.pack(fill="x", pady=(0, 8))

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        self._settings_frame = tk.Frame(notebook)
        notebook.add(self._settings_frame, text="設定 / Settings")

        json_frame = tk.Frame(notebook)
        notebook.add(json_frame, text="完整 JSON / Full JSON")
        self._build_json_tab(json_frame)

        warning_label = tk.Label(
            self,
            text="⚠️ 儲存前請先停止伺服器，否則將拒絕寫入。 / Server must be stopped before saving.",
            foreground="#b05000",
            font=("Segoe UI", 9),
        )
        warning_label.pack(fill="x", pady=(8, 0))

        button_frame = tk.Frame(self)
        button_frame.pack(pady=(8, 0))

        self._save_button = tk.Button(
            button_frame,
            text="儲存 / Save",
            width=18,
            state="disabled",
            command=self._on_save,
        )
        self._save_button.pack(side="left", padx=4)

        tk.Button(
            button_frame,
            text="關閉 / Close",
            width=18,
            command=self.destroy,
        ).pack(side="left", padx=4)

        self.transient(parent)
        self.wait_visibility()
        self.lift()

        threading.Thread(target=self._discover_worlds, daemon=True).start()
        self._ensure_queue_polling()

    # ── Queue polling ──────────────────────────────────────────────────────

    def _ensure_queue_polling(self) -> None:
        """Start the background-queue poll loop if it is not already running.

        ``_poll_queue`` sets ``self._poll_job`` back to ``None`` once the
        queue is drained and a ``_WORLD_OPTIONS_DONE`` sentinel is seen.
        Every call site that starts a new background thread must call this
        first, otherwise results placed on ``self._queue`` are never read
        and the UI gets stuck showing its "in progress" status text.
        """
        if self._poll_job is None:
            self._poll_job = self.after(100, self._poll_queue)

    # ── Full JSON tab ──────────────────────────────────────────────────────

    def _build_json_tab(self, parent: tk.Frame) -> None:
        """Build the read-only, searchable full-JSON browser tab."""
        search_frame = tk.Frame(parent)
        search_frame.pack(fill="x", pady=(4, 4))

        tk.Label(search_frame, text="搜尋 / Find:").pack(side="left")
        self._json_search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=self._json_search_var, width=30)
        search_entry.pack(side="left", padx=(4, 4))
        search_entry.bind("<Return>", lambda _event: self._on_json_search())
        tk.Button(search_frame, text="下一個 / Next", command=self._on_json_search).pack(
            side="left"
        )

        self._json_text = scrolledtext.ScrolledText(
            parent, width=70, height=24, state="disabled", font=("Consolas", 9), wrap="none"
        )
        self._json_text.pack(fill="both", expand=True)
        self._json_text.tag_configure("search_hit", background="#fff59d")

    def _on_json_search(self) -> None:
        """Find and highlight the next occurrence of the search text."""
        query = self._json_search_var.get()
        if not query:
            return
        self._json_text.tag_remove("search_hit", "1.0", tk.END)
        start = self._json_text.index(tk.INSERT)
        found = self._json_text.search(query, start, stopindex=tk.END, nocase=True)
        if not found:
            found = self._json_text.search(query, "1.0", stopindex=tk.END, nocase=True)
        if not found:
            return
        end = f"{found}+{len(query)}c"
        self._json_text.tag_add("search_hit", found, end)
        self._json_text.mark_set(tk.INSERT, end)
        self._json_text.see(found)

    def _set_json_content(self, text: str) -> None:
        self._json_text.config(state="normal")
        self._json_text.delete("1.0", tk.END)
        self._json_text.insert("1.0", text)
        self._json_text.config(state="disabled")

    # ── Discovery ───────────────────────────────────────────────────────────

    def _discover_worlds(self) -> None:
        """Background thread: scan the WSL save directory for worlds."""
        try:
            save_games_root = server.get_save_games_windows_path()
            worlds = world_options.find_world_saves(save_games_root)
            self._queue.put(("worlds", worlds))
        except Exception as exc:  # noqa: BLE001
            self._queue.put(("error", f"無法掃描世界存檔 / Failed to scan worlds: {exc}"))
        self._queue.put(_WORLD_OPTIONS_DONE)

    def _poll_queue(self) -> None:
        """Drain the background-task queue and update the UI (main thread)."""
        done = False
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break
            if item is _WORLD_OPTIONS_DONE:
                done = True
                break
            kind: str
            payload: Any
            kind, payload = item  # type: ignore[misc]
            if kind == "worlds":
                self._on_worlds_discovered(payload)
            elif kind == "error":
                self._status_label.config(text=payload, foreground="#b00000")
                if str(self._save_button["text"]).startswith("儲存中"):
                    self._save_button.config(state="normal", text="儲存 / Save")
            elif kind == "decoded":
                self._on_decoded(payload)
            elif kind == "saved":
                self._on_saved(payload)

        if done:
            self._poll_job = None
        else:
            self._poll_job = self.after(100, self._poll_queue)

    def _on_worlds_discovered(self, worlds: list[world_options.WorldSaveInfo]) -> None:
        self._worlds = worlds
        if not worlds:
            self._status_label.config(
                text="找不到任何世界存檔 / No world saves found", foreground="#b00000"
            )
            return
        self._world_combo.config(state="readonly", values=[w.world_id for w in worlds])
        self._status_label.config(text="請選擇要編輯的世界 / Select a world to edit")

    def _on_world_selected(self, _event: object = None) -> None:
        world_id = self._world_var.get()
        world = next((w for w in self._worlds if w.world_id == world_id), None)
        if world is None:
            return
        self._save_button.config(state="disabled")
        self._status_label.config(text="正在讀取存檔... / Loading save...", foreground="#555555")
        self._ensure_queue_polling()
        threading.Thread(target=self._decode_world, args=(world,), daemon=True).start()

    def _decode_world(self, world: world_options.WorldSaveInfo) -> None:
        """Background thread: decode the selected world's WorldOption.sav."""
        try:
            data = world.world_option_path.read_bytes()
            gvas_file, save_type = world_options.decode_sav_bytes(data)
            self._queue.put(("decoded", (world, gvas_file, save_type)))
        except Exception as exc:  # noqa: BLE001
            self._queue.put(("error", f"無法讀取存檔 / Failed to load save: {exc}"))
        self._queue.put(_WORLD_OPTIONS_DONE)

    def _on_decoded(self, payload: tuple[Any, Any, int]) -> None:
        world, gvas_file, save_type = payload
        self._selected_world = world
        self._gvas_file = gvas_file
        self._save_type = save_type
        self._render_settings_form(gvas_file.properties)
        self._set_json_content(world_options.dump_gvas_json(gvas_file))
        self._save_button.config(state="normal")
        self._status_label.config(text="讀取成功 / Loaded successfully", foreground="#1a6e1a")

    def _render_settings_form(self, properties: dict[str, Any]) -> None:
        """(Re)build the grouped settings form from the decoded properties."""
        for child in self._settings_frame.winfo_children():
            child.destroy()
        self._field_vars.clear()

        canvas_frame = tk.Frame(self._settings_frame)
        canvas_frame.pack(fill="both", expand=True)

        groups: dict[str, list[tuple[world_options.SettingField, object]]] = {}
        for field, value in world_options.get_available_settings(properties):
            groups.setdefault(field.group, []).append((field, value))

        for group_name, fields in groups.items():
            group_frame = tk.LabelFrame(canvas_frame, text=group_name, padx=8, pady=6)
            group_frame.pack(fill="x", pady=(0, 6))
            for field, value in fields:
                row = tk.Frame(group_frame)
                row.pack(fill="x", pady=2)
                tk.Label(row, text=field.label, width=32, anchor="w").pack(side="left")

                if value is None:
                    tk.Label(row, text="（不支援 / unavailable）", foreground="#888888").pack(
                        side="left"
                    )
                    continue

                if field.kind == "bool":
                    var: tk.Variable = tk.BooleanVar(value=bool(value))
                    tk.Checkbutton(row, variable=var).pack(side="left")
                elif field.kind == "enum":
                    var = tk.StringVar(value=str(value))
                    ttk.Combobox(
                        row,
                        textvariable=var,
                        values=list(field.enum_choices),
                        state="readonly",
                        width=20,
                    ).pack(side="left")
                else:
                    var = tk.StringVar(value=str(value))
                    tk.Entry(row, textvariable=var, width=20).pack(side="left")

                self._field_vars[field.key] = var

    # ── Save ────────────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        if self._gvas_file is None or self._save_type is None:
            return
        world = getattr(self, "_selected_world", None)
        if world is None:
            return

        confirmed = messagebox.askyesno(
            "確認儲存 / Confirm Save",
            "儲存前將建立完整世界備份，並拒絕在伺服器執行中寫入。\n是否繼續？\n\n"
            "A full world backup will be created before saving, and saving will be "
            "refused while the server is running. Continue?",
            parent=self,
        )
        if not confirmed:
            return

        changes: dict[str, object] = {}
        for key, var in self._field_vars.items():
            changes[key] = var.get()

        self._save_button.config(state="disabled", text="儲存中... / Saving...")
        self._ensure_queue_polling()
        threading.Thread(
            target=self._do_save, args=(world, changes), daemon=True
        ).start()

    def _do_save(self, world: world_options.WorldSaveInfo, changes: dict[str, object]) -> None:
        """Background thread: validate, back up, and write the save file."""
        try:
            backups_root = world.world_dir.parent.parent / "Backups"
            assert self._gvas_file is not None
            assert self._save_type is not None
            result = world_options.save_world_options(
                world,
                self._gvas_file,
                self._save_type,
                changes,
                backups_root,
                is_server_running=server.is_server_process_running,
            )
            self._queue.put(("saved", result))
        except world_options.WorldOptionsError as exc:
            self._queue.put(("error", str(exc)))
            self._queue.put(_WORLD_OPTIONS_DONE)
            return
        except Exception as exc:  # noqa: BLE001
            self._queue.put(("error", f"儲存失敗 / Save failed: {exc}"))
        self._queue.put(_WORLD_OPTIONS_DONE)

    def _on_saved(self, result: world_options.SaveWorldOptionsResult) -> None:
        self._save_button.config(state="normal", text="儲存 / Save")
        self._status_label.config(text="儲存成功 / Saved successfully", foreground="#1a6e1a")
        messagebox.showinfo(
            "儲存成功 / Save Successful",
            f"世界設定已儲存。\n備份位置：{result.backup_path}\n\n"
            f"World settings saved.\nBackup: {result.backup_path}",
            parent=self,
        )
        world = getattr(self, "_selected_world", None)
        if world is not None:
            self._ensure_queue_polling()
            threading.Thread(target=self._decode_world, args=(world,), daemon=True).start()


def main() -> None:
    """Launch the Tkinter application."""
    app = MainWindow()
    app.mainloop()
