"""Tkinter main window for the application."""

from __future__ import annotations

import queue
import subprocess
import sys
import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, scrolledtext

from .. import server
from ..config import AppConfig, create_app_message

#: Sentinel placed on the output queue once the background process ends.
_OUTPUT_DONE = object()

#: Sentinel placed on the IP queue once the address lookup finishes.
_IP_DONE = object()

#: Palworld default game port shown alongside the IP address.
_PALWORLD_PORT: int = 8211


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
        self._ip_queue: queue.Queue[object] = queue.Queue()
        self._ip_poll_job: str | None = None

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
        else:
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

        self.ip_label.config(text="連線位址：查詢中...", foreground="#1a6e1a")
        threading.Thread(target=self._fetch_connection_info, daemon=True).start()
        self._ip_poll_job = self.after(100, self._poll_ip_queue)

    def _on_stop_server(self) -> None:
        """Handle the "Stop Server" button click."""
        server.stop_server()
        self._set_running_state(False)
        self.ip_label.config(text="")

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


def main() -> None:
    """Launch the Tkinter application."""
    app = MainWindow()
    app.mainloop()
