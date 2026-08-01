"""WSL networking setup dialog."""

from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from ... import server


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

