"""Tkinter main window for the application."""

from __future__ import annotations

import queue
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import Any

from .. import server, world_options
from ..config import AppConfig, create_app_message
from .dialogs import (
    BackupCompleteDialog,
    DiagnosticDialog,
    NetworkSetupDialog,
    WorldOptionEditorDialog,
)
from .pages import BackupsPage, DashboardPage, PlaceholderPage
from .widgets import CanvasIconButton, RoundedPanel, StatusPill

#: Sentinel placed on the output queue once the background process ends.
_OUTPUT_DONE = object()

#: Sentinel placed on the IP queue once the address lookup finishes.
_IP_DONE = object()

#: Sentinel placed on the game-backup queue once a background task finishes.
_BACKUP_DONE = object()

#: Sentinel placed on the read-only backup inventory queue once it finishes.
_BACKUP_INVENTORY_DONE = object()

#: Sentinel placed on the server-update queue once a background task finishes.
_UPDATE_DONE = object()

#: Palworld default game port shown alongside the IP address.
_PALWORLD_PORT: int = 8211


class MainWindow(tk.Tk):
    """The application's primary window."""

    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self.config = config or AppConfig()
        self.title(self.config.title)
        self.geometry("1280x800")
        self.minsize(520, 640)
        self.configure(background="#f9f9f9")

        self._process: subprocess.Popen[str] | None = None
        self._output_queue: queue.Queue[object] = queue.Queue()
        self._poll_job: str | None = None
        self._ip_queue: queue.Queue[object] = queue.Queue()
        self._ip_poll_job: str | None = None
        self._backup_queue: queue.Queue[object] = queue.Queue()
        self._backup_poll_job: str | None = None
        self._backup_inventory_queue: queue.Queue[object] = queue.Queue()
        self._backup_inventory_poll_job: str | None = None
        self._backup_inventory_refresh_pending = False
        self._update_queue: queue.Queue[object] = queue.Queue()
        self._update_poll_job: str | None = None
        self._start_options_popup: tk.Toplevel | None = None
        self._console_auto_scroll = True

        self._build_navigation()
        self.bind("<ButtonPress-1>", self._dismiss_start_options_on_main_click, add="+")
        self.bind("<Escape>", lambda _event: self._hide_start_options(), add="+")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._perform_environment_check)

    def _build_navigation(self) -> None:
        """Create the fixed page container and its desktop/mobile navigation."""
        palette = {"background": "#f9f9f9", "sidebar": "#f4f3f3", "card": "#ffffff", "primary": "#1a6e1a", "muted": "#40493d", "border": "#c0c9b9"}
        self._app_shell = tk.Frame(self, background=palette["background"])
        self._app_shell.pack(fill="both", expand=True)
        self._sidebar = tk.Frame(self._app_shell, background=palette["sidebar"], width=288, highlightbackground=palette["border"], highlightthickness=1)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)
        tk.Label(self._sidebar, text=self.config.title.upper(), background=palette["sidebar"], foreground=palette["primary"], font=("Segoe UI", 14, "bold"), justify="left", wraplength=238).pack(anchor="w", padx=20, pady=(22, 28))
        tk.Label(self._sidebar, text="OPERATIONS", background=palette["sidebar"], foreground=palette["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=20, pady=(0, 8))
        self._workspace = tk.Frame(self._app_shell, background=palette["background"])
        self._workspace.pack(side="left", fill="both", expand=True)
        self._top_header = tk.Frame(self._workspace, background=palette["card"], height=64, highlightbackground=palette["border"], highlightthickness=1)
        self._top_header.pack(fill="x", side="top")
        self._top_header.pack_propagate(False)
        tk.Label(self._top_header, text="●  SYSTEM STATUS", background=palette["card"], foreground=palette["primary"], font=("Segoe UI", 9, "bold")).pack(side="left", padx=24, pady=20)
        tk.Label(self._top_header, text="Palworld Server Manager", background=palette["card"], foreground=palette["muted"], font=("Segoe UI", 9)).pack(side="left", pady=20)
        self._page_container = tk.Frame(self._workspace, background=palette["background"])
        self._page_container.pack(fill="both", expand=True)
        self._bottom_navigation = tk.Frame(self, background=palette["card"], height=64)

        self.dashboard_page = DashboardPage(
            self._page_container,
            self.config,
            on_start=self._toggle_start_options,
            on_stop=self._on_stop_server,
            on_update=self._on_update_server,
            on_diagnostics=self._on_show_diagnostics,
            on_clear_console=self._clear_console,
            on_scroll_console=self._resume_console_auto_scroll,
            on_console_manual_scroll=self._pause_console_auto_scroll,
        )
        self.backups_page = BackupsPage(
            self._page_container,
            on_backup=self._on_backup_all_world_saves,
        )
        self.world_page = PlaceholderPage(self._page_container, "World")
        self.stats_page = PlaceholderPage(self._page_container, "Stats")
        self._pages = {
            "dashboard": self.dashboard_page,
            "backups": self.backups_page,
            "world": self.world_page,
            "stats": self.stats_page,
        }
        for page in self._pages.values():
            page.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Keep existing worker/event handlers unchanged while page views own layout.
        self.mode_var = self.dashboard_page.mode_var
        self.start_server_button = self.dashboard_page.start_server_button
        self.stop_server_button = self.dashboard_page.stop_server_button
        self.update_server_button = self.dashboard_page.update_server_button
        self.server_status_label = self.dashboard_page.server_status_label
        self.server_system_label = self.dashboard_page.server_system_label
        self.environment_status_label = self.dashboard_page.environment_status_label
        self._environment_badges = self.dashboard_page.environment_badges
        self._network_value_labels = self.dashboard_page.network_value_labels
        self._network_port_pill = self.dashboard_page.network_port_pill
        self.ip_label = self.dashboard_page.ip_label
        self.network_status_label = self.dashboard_page.network_status_label
        self.output_text = self.dashboard_page.output_text
        self.clear_console_button = self.dashboard_page.clear_console_button
        self.scroll_console_button = self.dashboard_page.scroll_console_button
        self.backup_worlds_button = self.backups_page.backup_worlds_button

        self._navigation_buttons: dict[str, list[tk.Button]] = {key: [] for key in self._pages}
        self._navigation_icons: dict[str, list[CanvasIconButton]] = {
            key: [] for key in self._pages
        }
        self._navigation_rows: dict[str, list[tk.Frame]] = {key: [] for key in self._pages}
        for container, compact in ((self._sidebar, False), (self._bottom_navigation, True)):
            for key, label, icon in (
                ("dashboard", "DASHBOARD", "dashboard"),
                ("backups", "BACKUPS", "backup"),
                ("world", "WORLD", "public"),
                ("stats", "STATS", "query_stats"),
            ):
                command = lambda selected=key: self.show_page(selected)
                if compact:
                    button = tk.Button(container, text=label, command=command, relief="flat", borderwidth=0, anchor="center", background=palette["card"], foreground=palette["muted"], activebackground="#e5f4e2", activeforeground=palette["primary"], font=("Segoe UI", 8, "bold"), padx=18, pady=18)
                    button.pack(side="left", expand=True, fill="x", padx=4)
                else:
                    row = tk.Frame(container, background=palette["sidebar"])
                    row.pack(fill="x", padx=12, pady=2)
                    icon_button = CanvasIconButton(row, icon=icon, tooltip=label.title(), command=command, foreground=palette["muted"], hover_background="#e2e2e2")
                    icon_button.pack(side="left", padx=(10, 4), pady=4)
                    self._navigation_icons[key].append(icon_button)
                    self._navigation_rows[key].append(row)
                    button = tk.Button(row, text=label, command=command, relief="flat", borderwidth=0, anchor="w", background=palette["sidebar"], foreground=palette["muted"], activebackground="#e5f4e2", activeforeground=palette["primary"], font=("Segoe UI", 9, "bold"), padx=4, pady=12)
                    button.pack(side="left", fill="x", expand=True)
                self._navigation_buttons[key].append(button)
        self.show_page("dashboard")
        self.bind("<Configure>", self._on_window_resize, add="+")

    def show_page(self, page_name: str) -> None:
        """Raise one named page and synchronize both navigation variants."""
        self._active_page = page_name
        self._pages[page_name].tkraise()
        if page_name == "backups":
            self._refresh_backup_inventory()
        for key, buttons in self._navigation_buttons.items():
            selected = key == page_name
            for button in buttons:
                compact = button.master is self._bottom_navigation
                button.configure(foreground="#1a6e1a" if selected else "#40493d", background="#e5f4e2" if selected else ("#ffffff" if compact else "#f4f3f3"))
            sidebar_background = "#e5f4e2" if selected else "#f4f3f3"
            sidebar_foreground = "#1a6e1a" if selected else "#40493d"
            for row in self._navigation_rows[key]:
                row.configure(background=sidebar_background)
            for icon in self._navigation_icons[key]:
                icon.set_colors(background=sidebar_background, foreground=sidebar_foreground)

    def _on_window_resize(self, event: tk.Event[tk.Misc]) -> None:
        """Show the reference sidebar on desktop and compact navigation on mobile."""
        if event.widget is not self:
            return
        if event.width < 768:
            self._sidebar.pack_forget()
            self._top_header.pack_forget()
            if not self._bottom_navigation.winfo_manager():
                self._bottom_navigation.pack(fill="x", side="bottom")
        else:
            self._bottom_navigation.pack_forget()
            if not self._sidebar.winfo_manager():
                self._sidebar.pack(side="left", fill="y", before=self._workspace)
            if not self._top_header.winfo_manager():
                self._top_header.pack(fill="x", side="top", before=self._page_container)

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

        def card(parent: tk.Misc, **kwargs: Any) -> RoundedPanel:
            return RoundedPanel(
                parent,
                background=palette["card"],
                border="#e5e5e5",
                radius=12,
                **kwargs,
            )

        def section_header(
            parent: tk.Misc, icon: str, text: str, accent: str, trailing: tk.Widget | None = None
        ) -> None:
            header = tk.Frame(parent, background=palette["card"])
            header.pack(fill="x", padx=20, pady=(18, 14))
            tk.Label(header, text=icon, background=palette["card"], foreground=accent, font=("Segoe UI Symbol", 14)).pack(side="left", padx=(0, 8))
            tk.Label(header, text=text, background=palette["card"], foreground=palette["text"], font=("Segoe UI", 9, "bold")).pack(side="left")
            if trailing is not None:
                trailing.pack(side="right")

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
        self.server_system_label = tk.Label(
            header,
            text="SYSTEM READY",
            background=palette["primary_light"],
            foreground=palette["primary"],
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=5,
        )
        self.server_system_label.pack(side="right")

        hero = tk.Frame(content, background=palette["background"])
        hero.pack(fill="x", pady=(0, 16))
        hero.columnconfigure(0, weight=1)
        # Reserve a stable action column so the server status and controls
        # keep the 8:4 split shown in the dashboard reference.
        hero.columnconfigure(1, minsize=340)
        server_card = card(hero, height=108)
        server_card.grid(row=0, column=0, sticky="nsew", padx=(0, 24))
        hero_status = tk.Frame(server_card.content, background=palette["card"])
        hero_status.pack(fill="both", expand=True, padx=20, pady=18)
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
        dashboard.pack(fill="x")
        dashboard.columnconfigure(0, weight=1)
        dashboard.columnconfigure(1, weight=1)
        dashboard.columnconfigure(2, weight=1)

        diagnostics_card = card(dashboard, height=254)
        diagnostics_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.environment_status_label = tk.Label(
            diagnostics_card.content,
            text="REFRESHING...",
            background=palette["card"],
            foreground=palette["muted"],
            font=("Segoe UI", 8, "bold"),
        )
        section_header(diagnostics_card.content, "◇", "DIAGNOSTICS", palette["primary"], self.environment_status_label)
        self._environment_badges: dict[str, StatusPill] = {}
        rows = tk.Frame(diagnostics_card.content, background=palette["card"])
        rows.pack(fill="x", padx=20)
        for icon, label, key in (("▹", "WSL 2 Runtime", "wsl"), ("↓", "SteamCMD", "steamcmd"), ("↻", "PalServer.exe", "palserver")):
            row = tk.Frame(rows, background=palette["card"])
            row.pack(fill="x", pady=4)
            tk.Label(row, text=icon, width=2, background=palette["card"], foreground=palette["primary"], font=("Segoe UI Symbol", 11)).pack(side="left")
            tk.Label(row, text=label, background=palette["card"], foreground=palette["text"], font=("Segoe UI", 10)).pack(side="left", padx=(8, 0))
            badge = StatusPill(row, "CHECKING", foreground=palette["muted"], background="#f5f5f4")
            badge.pack(side="right")
            self._environment_badges[key] = badge
        diagnostic_button = tk.Button(
            diagnostics_card.content,
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
        diagnostic_button.pack(fill="x", side="bottom", padx=20, pady=(12, 18))

        network_card = card(dashboard, height=254)
        network_card.grid(row=0, column=1, sticky="nsew", padx=5)
        section_header(network_card.content, "⌘", "NETWORK", palette["secondary"])
        self._network_value_labels: dict[str, tk.Label] = {}
        network_rows = tk.Frame(network_card.content, background=palette["card"])
        network_rows.pack(fill="x", padx=20)
        for title, key in (("LAN IP (WSL)", "lan"), ("PUBLIC IP", "public")):
            row = tk.Frame(network_rows, background="#faf9f8", highlightbackground="#eeeeee", highlightthickness=1)
            row.pack(fill="x", pady=(0, 8))
            tk.Label(row, text=title, background="#faf9f8", foreground=palette["muted"], font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=10, pady=(7, 0))
            value = tk.Label(row, text="WAITING FOR SERVER", background="#faf9f8", foreground=palette["secondary"], font=("Consolas", 9), anchor="w")
            value.pack(fill="x", padx=10, pady=(1, 7))
            self._network_value_labels[key] = value
        port_row = tk.Frame(network_rows, background=palette["card"])
        port_row.pack(fill="x", pady=(2, 0))
        tk.Label(port_row, text=f"Port {_PALWORLD_PORT} (UDP)", background=palette["card"], foreground=palette["muted"], font=("Segoe UI", 9)).pack(side="left")
        self._network_port_pill = StatusPill(port_row, "CHECKING", foreground=palette["muted"], background="#f5f5f4")
        self._network_port_pill.pack(side="right")
        self.ip_label = tk.Label(
            network_card.content,
            text="",
            background=palette["card"],
            foreground=palette["secondary"],
        )
        self.network_status_label = tk.Label(
            network_card.content,
            text="Network checks will run automatically.",
            background=palette["card"],
            foreground=palette["muted"],
            font=("Segoe UI", 8),
            anchor="w",
            justify="left",
            wraplength=260,
        )
        self.network_status_label.pack(fill="x", padx=20, pady=(8, 0))
        self.update_server_button = tk.Button(
            network_card.content,
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
        self.update_server_button.pack(fill="x", side="bottom", padx=20, pady=(8, 18))

        console_card = card(dashboard, height=254)
        console_card.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
        scrolling_pill = StatusPill(console_card.content, "● SCROLLING", foreground=palette["primary"], background=palette["primary_light"])
        section_header(console_card.content, "▤", "LIVE CONSOLE", palette["primary"], scrolling_pill)
        self.output_text = scrolledtext.ScrolledText(
            console_card.content,
            height=8,
            state="disabled",
            background="#fafaf9",
            foreground="#4f534f",
            insertbackground="#4f534f",
            borderwidth=1,
            relief="solid",
            font=("Consolas", 8),
            padx=9,
            pady=7,
        )
        self.output_text.pack(fill="both", expand=True, padx=20)
        self.backup_worlds_button = tk.Button(
            console_card.content,
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
        self.backup_worlds_button.pack(fill="x", padx=20, pady=(10, 18))

        self._dashboard_cards = (diagnostics_card, network_card, console_card)
        self.bind("<Configure>", self._on_dashboard_resize, add="+")

    def _on_dashboard_resize(self, event: tk.Event[tk.Misc]) -> None:
        """Keep the cards legible when the desktop window becomes narrow."""
        if event.widget is not self or not hasattr(self, "_dashboard_cards"):
            return
        diagnostics_card, network_card, console_card = self._dashboard_cards
        if event.width < 1000:
            diagnostics_card.grid_configure(row=0, column=0, columnspan=1, padx=(0, 10))
            network_card.grid_configure(row=0, column=1, columnspan=1, padx=(10, 0))
            console_card.grid_configure(row=1, column=0, columnspan=2, padx=0, pady=(16, 0))
        else:
            diagnostics_card.grid_configure(row=0, column=0, columnspan=1, padx=(0, 10), pady=0)
            network_card.grid_configure(row=0, column=1, columnspan=1, padx=5, pady=0)
            console_card.grid_configure(row=0, column=2, columnspan=1, padx=(10, 0), pady=0)

    def _set_environment_badges(self, result: server.EnvironmentCheckResult) -> None:
        """Map the existing environment check to the dashboard status rows."""
        for key, available in {
            "wsl": result.wsl_available,
            "steamcmd": result.steamcmd_installed,
            "palserver": result.palserver_installed,
        }.items():
            badge = self._environment_badges[key]
            if available:
                badge.set("READY", foreground="#005408", background="#e5f4e2")
            else:
                badge.set("ACTION REQ", foreground="#9b5a00", background="#fff0dc")

    def _set_connection_summary(self, text: str, foreground: str) -> None:
        """Retain the legacy label while projecting addresses into network rows."""
        self.ip_label.config(text=text, foreground=foreground)
        lan_value = "WAITING FOR SERVER"
        public_value = "WAITING FOR SERVER"
        if "查詢中" in text:
            lan_value = "LOOKING UP ADDRESS..."
            public_value = "LOOKING UP ADDRESS..."
        elif "無法取得" in text:
            lan_value = "UNAVAILABLE"
            public_value = "UNAVAILABLE"
        elif text:
            for line in text.splitlines():
                if line.startswith(("WSL IP：", "本機 LAN IP：")):
                    lan_value = line.split("：", 1)[1]
                elif line.startswith("公開 IP："):
                    public_value = line.split("：", 1)[1]
        self._network_value_labels["lan"].config(text=lan_value)
        self._network_value_labels["public"].config(text=public_value)

    def _perform_environment_check(self) -> None:
        """Verify WSL/SteamCMD/PalServer are ready, disabling start if not."""
        result = server.check_environment()
        self._set_environment_badges(result)
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
        if self._network_port_pill is not None:
            if net.firewall_rule_exists:
                self._network_port_pill.set("● OPEN", foreground="#005408", background="#e5f4e2")
            else:
                self._network_port_pill.set("ACTION REQ", foreground="#9b5a00", background="#fff0dc")

    def _set_running_state(self, running: bool) -> None:
        """Toggle the Start/Stop buttons to reflect the server state."""
        if running:
            self._hide_start_options()
        self.start_server_button.config(state="disabled" if running else "normal")
        self.stop_server_button.config(state="normal" if running else "disabled")
        self.update_server_button.config(state="disabled" if running else "normal")
        state_text = "SERVER ONLINE" if running else "SERVER STOPPED"
        state_color = "#005408" if running else "#40493d"
        self.server_status_label.config(text=state_text, foreground=state_color)
        self.server_system_label.config(
            text="SYSTEM ONLINE" if running else "SYSTEM READY",
            foreground=state_color,
            background="#e5f4e2" if running else "#f5f5f4",
        )

    def _append_output(self, text: str) -> None:
        """Append a line of text to the scrollable output box."""
        self.output_text.config(state="normal")
        self.output_text.insert(tk.END, text)
        if self._console_auto_scroll:
            self.output_text.see(tk.END)
        self.output_text.config(state="disabled")

    def _clear_console(self) -> None:
        """Clear only the log text currently displayed in the live console."""
        self.output_text.config(state="normal")
        self.output_text.delete("1.0", tk.END)
        self.output_text.config(state="disabled")

    def _resume_console_auto_scroll(self) -> None:
        """Return the console to the newest line and resume automatic following."""
        self._console_auto_scroll = True
        self.output_text.see(tk.END)

    def _pause_console_auto_scroll(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        """Pause console following after the user starts navigating its history."""
        self._console_auto_scroll = False

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

        self._set_connection_summary("連線位址：查詢中...", "#1a6e1a")
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
        if self._backup_inventory_poll_job is not None:
            self.after_cancel(self._backup_inventory_poll_job)
        self.destroy()

    def _on_stop_server(self) -> None:
        """Handle the "Stop Server" button click."""
        self._hide_start_options()
        server.stop_server()
        self._set_running_state(False)
        self._set_connection_summary("", "#335ea1")

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
        self.backup_worlds_button.config(state="disabled", text="BACKING UP...")
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
                self._refresh_backup_inventory()
            elif kind == "error":
                messagebox.showerror("備份失敗 / Backup Failed", str(payload), parent=self)

        if done:
            self._backup_poll_job = None
            self.backup_worlds_button.config(state="normal", text="+  CREATE SNAPSHOT")
        else:
            self._backup_poll_job = self.after(100, self._poll_backup_queue)

    def _refresh_backup_inventory(self) -> None:
        """Start a background refresh of the read-only archive inventory."""
        if self._backup_inventory_poll_job is not None:
            self._backup_inventory_refresh_pending = True
            return
        self._backup_inventory_refresh_pending = False
        self.backups_page.set_inventory_loading()
        threading.Thread(target=self._load_backup_inventory, daemon=True).start()
        self._backup_inventory_poll_job = self.after(100, self._poll_backup_inventory_queue)

    def _load_backup_inventory(self) -> None:
        """Read and verify archives outside the Tk event loop."""
        try:
            archives = world_options.list_backup_archives(server.get_save_games_windows_path())
            self._backup_inventory_queue.put(("loaded", archives))
        except world_options.WorldOptionsError as exc:
            self._backup_inventory_queue.put(("error", str(exc)))
        except Exception as exc:  # noqa: BLE001
            self._backup_inventory_queue.put(("error", f"Unable to load backup inventory: {exc}"))
        self._backup_inventory_queue.put(_BACKUP_INVENTORY_DONE)

    def _poll_backup_inventory_queue(self) -> None:
        """Apply backup inventory results on the Tk thread."""
        done = False
        while True:
            try:
                item = self._backup_inventory_queue.get_nowait()
            except queue.Empty:
                break
            if item is _BACKUP_INVENTORY_DONE:
                done = True
                break
            kind, payload = item  # type: ignore[misc]
            if kind == "loaded":
                self.backups_page.set_backup_archives(payload)
            elif kind == "error":
                self.backups_page.set_inventory_error(str(payload))
        if done:
            self._backup_inventory_poll_job = None
            if self._backup_inventory_refresh_pending:
                self._refresh_backup_inventory()
        else:
            self._backup_inventory_poll_job = self.after(100, self._poll_backup_inventory_queue)

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
                    self._set_connection_summary("連線位址：\n" + "\n".join(lines), "#1a6e1a")
                else:
                    self._set_connection_summary("連線位址：無法取得", "#b00000")
            else:
                self._set_connection_summary("連線位址：無法取得", "#b00000")
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


def main() -> None:
    """Launch the Tkinter application."""
    app = MainWindow()
    app.mainloop()
