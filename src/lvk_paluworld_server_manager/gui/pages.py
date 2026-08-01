"""Page views for the main application navigation."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import scrolledtext

from ..config import AppConfig, create_app_message
from .widgets import RoundedPanel, StatusPill

PALETTE = {
    "background": "#f3f3f3",
    "card": "#ffffff",
    "text": "#1a1c1c",
    "muted": "#40493d",
    "primary": "#005408",
    "primary_light": "#e5f4e2",
    "secondary": "#335ea1",
    "danger": "#b00000",
}


class DashboardPage(tk.Frame):
    """The server dashboard, with its layout independent from the main window."""

    def __init__(
        self,
        parent: tk.Misc,
        config: AppConfig,
        *,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_update: Callable[[], None],
        on_diagnostics: Callable[[], None],
    ) -> None:
        super().__init__(parent, background=PALETTE["background"])
        self.config = config
        self._scroll_canvas = tk.Canvas(self, background=PALETTE["background"], highlightthickness=0)
        self._scrollbar = tk.Scrollbar(self, orient="vertical", command=self._scroll_canvas.yview)
        self._scroll_canvas.configure(yscrollcommand=self._scrollbar.set)
        self._scrollbar.pack(side="right", fill="y")
        self._scroll_canvas.pack(side="left", fill="both", expand=True)
        self.content = tk.Frame(self._scroll_canvas, background=PALETTE["background"], padx=24, pady=20)
        self._content_window = self._scroll_canvas.create_window(0, 0, anchor="nw", window=self.content)
        self.content.bind("<Configure>", self._update_scroll_region, add="+")
        self._scroll_canvas.bind("<Configure>", self._resize_content, add="+")
        self.bind("<Configure>", self._on_resize, add="+")
        self._build(on_start, on_stop, on_update, on_diagnostics)

    @staticmethod
    def _card(parent: tk.Misc, **kwargs: object) -> RoundedPanel:
        return RoundedPanel(parent, background=PALETTE["card"], border="#e5e5e5", radius=12, **kwargs)

    @staticmethod
    def _section_header(parent: tk.Misc, icon: str, text: str, accent: str, trailing: tk.Widget | None = None) -> None:
        header = tk.Frame(parent, background=PALETTE["card"])
        header.pack(fill="x", padx=20, pady=(18, 14))
        tk.Label(header, text=icon, background=PALETTE["card"], foreground=accent, font=("Segoe UI Symbol", 14)).pack(side="left", padx=(0, 8))
        tk.Label(header, text=text, background=PALETTE["card"], foreground=PALETTE["text"], font=("Segoe UI", 9, "bold")).pack(side="left")
        if trailing is not None:
            trailing.pack(side="right")

    def _build(self, on_start: Callable[[], None], on_stop: Callable[[], None], on_update: Callable[[], None], on_diagnostics: Callable[[], None]) -> None:
        header = tk.Frame(self.content, background=PALETTE["background"])
        header.pack(fill="x", pady=(0, 16))
        tk.Label(header, text=self.config.title.upper(), background=PALETTE["background"], foreground=PALETTE["text"], font=("Segoe UI", 20, "bold")).pack(side="left")
        self.server_system_label = tk.Label(header, text="SYSTEM READY", background=PALETTE["primary_light"], foreground=PALETTE["primary"], font=("Segoe UI", 9, "bold"), padx=10, pady=5)
        self.server_system_label.pack(side="right")

        self.hero = tk.Frame(self.content, background=PALETTE["background"])
        self.hero.pack(fill="x", pady=(0, 16))
        self.hero.columnconfigure(0, weight=1)
        self.hero.columnconfigure(1, minsize=340)
        self.server_card = self._card(self.hero, height=108)
        self.server_card.grid(row=0, column=0, sticky="nsew", padx=(0, 24))
        hero_status = tk.Frame(self.server_card.content, background=PALETTE["card"])
        hero_status.pack(fill="both", expand=True, padx=20, pady=18)
        self.server_status_label = tk.Label(hero_status, text="SERVER STOPPED", background=PALETTE["card"], foreground=PALETTE["muted"], font=("Segoe UI", 24, "bold"), anchor="w")
        self.server_status_label.pack(anchor="w")
        tk.Label(hero_status, text=create_app_message(self.config), background=PALETTE["card"], foreground=PALETTE["muted"], font=("Segoe UI", 10), anchor="w").pack(anchor="w", pady=(4, 0))
        self.action_panel = tk.Frame(self.hero, background=PALETTE["background"])
        self.action_panel.grid(row=0, column=1, sticky="new")
        self.mode_var = tk.StringVar(value="background")
        button_style = {"relief": "flat", "font": ("Segoe UI", 10, "bold"), "padx": 18, "pady": 10}
        self.start_server_button = tk.Button(self.action_panel, text="▷  START SERVER", command=on_start, background=PALETTE["primary"], activebackground="#003a04", foreground="#ffffff", activeforeground="#ffffff", **button_style)
        self.start_server_button.pack(fill="x", pady=(0, 8))
        self.stop_server_button = tk.Button(self.action_panel, text="STOP SERVER", command=on_stop, state="disabled", background=PALETTE["card"], activebackground="#ffdad6", foreground=PALETTE["danger"], activeforeground=PALETTE["danger"], highlightbackground=PALETTE["danger"], highlightthickness=1, **button_style)
        self.stop_server_button.pack(fill="x")

        self.dashboard = tk.Frame(self.content, background=PALETTE["background"])
        self.dashboard.pack(fill="x")
        for column in range(3):
            self.dashboard.columnconfigure(column, weight=1)
        self.diagnostics_card = self._card(self.dashboard, height=254)
        self.diagnostics_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.environment_status_label = tk.Label(self.diagnostics_card.content, text="REFRESHING...", background=PALETTE["card"], foreground=PALETTE["muted"], font=("Segoe UI", 8, "bold"))
        self._section_header(self.diagnostics_card.content, "◇", "DIAGNOSTICS", PALETTE["primary"], self.environment_status_label)
        self.environment_badges: dict[str, StatusPill] = {}
        rows = tk.Frame(self.diagnostics_card.content, background=PALETTE["card"])
        rows.pack(fill="x", padx=20)
        for icon, label, key in (("▹", "WSL 2 Runtime", "wsl"), ("↓", "SteamCMD", "steamcmd"), ("↻", "PalServer.exe", "palserver")):
            row = tk.Frame(rows, background=PALETTE["card"])
            row.pack(fill="x", pady=4)
            tk.Label(row, text=icon, width=2, background=PALETTE["card"], foreground=PALETTE["primary"], font=("Segoe UI Symbol", 11)).pack(side="left")
            tk.Label(row, text=label, background=PALETTE["card"], foreground=PALETTE["text"], font=("Segoe UI", 10)).pack(side="left", padx=(8, 0))
            badge = StatusPill(row, "CHECKING", foreground=PALETTE["muted"], background="#f5f5f4")
            badge.pack(side="right")
            self.environment_badges[key] = badge
        tk.Button(self.diagnostics_card.content, text="VIEW DIAGNOSTICS", command=on_diagnostics, background=PALETTE["secondary"], activebackground="#144688", foreground="#ffffff", activeforeground="#ffffff", relief="flat", font=("Segoe UI", 9, "bold"), pady=8).pack(fill="x", side="bottom", padx=20, pady=(12, 18))

        self.network_card = self._card(self.dashboard, height=254)
        self.network_card.grid(row=0, column=1, sticky="nsew", padx=5)
        self._section_header(self.network_card.content, "⌘", "NETWORK", PALETTE["secondary"])
        self.network_value_labels: dict[str, tk.Label] = {}
        network_rows = tk.Frame(self.network_card.content, background=PALETTE["card"])
        network_rows.pack(fill="x", padx=20)
        for title, key in (("LAN IP (WSL)", "lan"), ("PUBLIC IP", "public")):
            row = tk.Frame(network_rows, background="#faf9f8", highlightbackground="#eeeeee", highlightthickness=1)
            row.pack(fill="x", pady=(0, 8))
            tk.Label(row, text=title, background="#faf9f8", foreground=PALETTE["muted"], font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=10, pady=(7, 0))
            value = tk.Label(row, text="WAITING FOR SERVER", background="#faf9f8", foreground=PALETTE["secondary"], font=("Consolas", 9), anchor="w")
            value.pack(fill="x", padx=10, pady=(1, 7))
            self.network_value_labels[key] = value
        port_row = tk.Frame(network_rows, background=PALETTE["card"])
        port_row.pack(fill="x", pady=(2, 0))
        tk.Label(port_row, text="Port 8211 (UDP)", background=PALETTE["card"], foreground=PALETTE["muted"], font=("Segoe UI", 9)).pack(side="left")
        self.network_port_pill = StatusPill(port_row, "CHECKING", foreground=PALETTE["muted"], background="#f5f5f4")
        self.network_port_pill.pack(side="right")
        self.ip_label = tk.Label(self.network_card.content, text="", background=PALETTE["card"], foreground=PALETTE["secondary"])
        self.network_status_label = tk.Label(self.network_card.content, text="Network checks will run automatically.", background=PALETTE["card"], foreground=PALETTE["muted"], font=("Segoe UI", 8), anchor="w", justify="left", wraplength=260)
        self.network_status_label.pack(fill="x", padx=20, pady=(8, 0))
        self.update_server_button = tk.Button(self.network_card.content, text="UPDATE SERVER", command=on_update, background=PALETTE["secondary"], activebackground="#144688", foreground="#ffffff", activeforeground="#ffffff", relief="flat", font=("Segoe UI", 9, "bold"), pady=8)
        self.update_server_button.pack(fill="x", side="bottom", padx=20, pady=(8, 18))

        self.console_card = self._card(self.dashboard, height=254)
        self.console_card.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
        scrolling_pill = StatusPill(self.console_card.content, "● SCROLLING", foreground=PALETTE["primary"], background=PALETTE["primary_light"])
        self._section_header(self.console_card.content, "▤", "LIVE CONSOLE", PALETTE["primary"], scrolling_pill)
        self.output_text = scrolledtext.ScrolledText(self.console_card.content, height=8, state="disabled", background="#fafaf9", foreground="#4f534f", insertbackground="#4f534f", borderwidth=1, relief="solid", font=("Consolas", 8), padx=9, pady=7)
        self.output_text.pack(fill="both", expand=True, padx=20, pady=(0, 18))

    def _update_scroll_region(self, _event: tk.Event[tk.Misc]) -> None:
        self._scroll_canvas.configure(scrollregion=self._scroll_canvas.bbox("all"))

    def _resize_content(self, event: tk.Event[tk.Misc]) -> None:
        self._scroll_canvas.itemconfigure(self._content_window, width=event.width)

    def _on_resize(self, event: tk.Event[tk.Misc]) -> None:
        if event.widget is not self:
            return
        width = event.width
        if width < 768:
            self.hero.columnconfigure(1, minsize=0)
            self.hero.grid_columnconfigure(0, weight=1)
            self.hero.grid_columnconfigure(1, weight=0)
            self.server_card.grid_configure(row=0, column=0, columnspan=1, padx=0, pady=(0, 12))
            self.action_panel.grid_configure(row=1, column=0, columnspan=1, sticky="ew")
            self.dashboard.columnconfigure(0, weight=1)
            self.dashboard.columnconfigure(1, weight=0)
            self.dashboard.columnconfigure(2, weight=0)
            self.diagnostics_card.grid_configure(row=0, column=0, columnspan=1, padx=0, pady=0)
            self.network_card.grid_configure(row=1, column=0, columnspan=1, padx=0, pady=(16, 0))
            self.console_card.grid_configure(row=2, column=0, columnspan=1, padx=0, pady=(16, 0))
        elif width < 1000:
            self.hero.columnconfigure(1, minsize=260)
            self.server_card.grid_configure(row=0, column=0, columnspan=1, padx=(0, 16), pady=0)
            self.action_panel.grid_configure(row=0, column=1, columnspan=1, sticky="new")
            self.dashboard.columnconfigure(0, weight=1)
            self.dashboard.columnconfigure(1, weight=1)
            self.dashboard.columnconfigure(2, weight=0)
            self.diagnostics_card.grid_configure(row=0, column=0, columnspan=1, padx=(0, 8), pady=0)
            self.network_card.grid_configure(row=0, column=1, columnspan=1, padx=(8, 0), pady=0)
            self.console_card.grid_configure(row=1, column=0, columnspan=2, padx=0, pady=(16, 0))
        else:
            self.hero.columnconfigure(1, minsize=340)
            self.server_card.grid_configure(row=0, column=0, columnspan=1, padx=(0, 24), pady=0)
            self.action_panel.grid_configure(row=0, column=1, columnspan=1, sticky="new")
            for column in range(3):
                self.dashboard.columnconfigure(column, weight=1)
            self.diagnostics_card.grid_configure(row=0, column=0, columnspan=1, padx=(0, 10), pady=0)
            self.network_card.grid_configure(row=0, column=1, columnspan=1, padx=5, pady=0)
            self.console_card.grid_configure(row=0, column=2, columnspan=1, padx=(10, 0), pady=0)


class BackupsPage(tk.Frame):
    """Home for the existing verified all-world backup operation."""

    def __init__(self, parent: tk.Misc, *, on_backup: Callable[[], None]) -> None:
        super().__init__(parent, background=PALETTE["background"], padx=24, pady=20)
        panel = RoundedPanel(self, background=PALETTE["card"], border="#e5e5e5", radius=12, height=230)
        panel.pack(fill="x", anchor="n")
        tk.Label(panel.content, text="BACKUPS", background=PALETTE["card"], foreground=PALETTE["text"], font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=24, pady=(24, 8))
        tk.Label(panel.content, text="Create a verified archive of every world save. The server must be stopped before backup begins.", background=PALETTE["card"], foreground=PALETTE["muted"], justify="left", wraplength=500).pack(anchor="w", padx=24)
        self.backup_worlds_button = tk.Button(panel.content, text="BACK UP ALL WORLD SAVES", command=on_backup, background=PALETTE["secondary"], activebackground="#144688", foreground="#ffffff", activeforeground="#ffffff", relief="flat", font=("Segoe UI", 10, "bold"), padx=18, pady=10)
        self.backup_worlds_button.pack(anchor="w", padx=24, pady=(22, 24))


class PlaceholderPage(tk.Frame):
    """A deliberately non-functional page reserved for a future feature."""

    def __init__(self, parent: tk.Misc, title: str) -> None:
        super().__init__(parent, background=PALETTE["background"])
        panel = RoundedPanel(self, background=PALETTE["card"], border="#e5e5e5", radius=12, height=200)
        panel.pack(fill="x", padx=24, pady=20, anchor="n")
        tk.Label(panel.content, text=title.upper(), background=PALETTE["card"], foreground=PALETTE["text"], font=("Segoe UI", 20, "bold")).pack(pady=(48, 8))
        tk.Label(panel.content, text="This feature is being prepared.", background=PALETTE["card"], foreground=PALETTE["muted"], font=("Segoe UI", 10)).pack()
