"""System diagnostics dialog."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, scrolledtext, ttk

from ... import server

#: Sentinel placed on the diagnostics queue once the background task finishes.
_DIAGNOSTICS_DONE = object()

#: Palworld default game port shown alongside discovered IP addresses.
_PALWORLD_PORT: int = 8211


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

    def __init__(
        self,
        parent: tk.Tk,
        *,
        on_environment_check: Callable[[server.EnvironmentCheckResult], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._parent = parent
        self._on_environment_check = on_environment_check
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
        self._diagnostic_queue.put(_DIAGNOSTICS_DONE)

    def _poll_diagnostic_queue(self) -> None:
        """Poll the diagnostic queue and update UI labels (main thread)."""
        done = False
        diagnostic_info: server.DiagnosticInfo | None = None

        while True:
            try:
                item = self._diagnostic_queue.get_nowait()
            except queue.Empty:
                break

            if item is _DIAGNOSTICS_DONE:
                done = True
                break

            if isinstance(item, server.DiagnosticInfo):
                diagnostic_info = item

        if done and diagnostic_info:
            self._update_ui(diagnostic_info)
            if self._on_environment_check is not None:
                self._on_environment_check(diagnostic_info.environment_check)
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
