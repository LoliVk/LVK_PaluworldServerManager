"""Page views for the main application navigation."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import scrolledtext

from ..config import AppConfig, create_app_message
from .widgets import CanvasIconButton, RoundedPanel, StatusPill

PALETTE = {
    "background": "#f9f9f9", "card": "#eeeeee", "card_high": "#e8e8e8",
    "text": "#1a1c1c", "muted": "#40493d", "primary": "#1a6e1a",
    "primary_dark": "#003a04", "primary_light": "#e5f4e2",
    "secondary": "#335ea1", "danger": "#ba1a1a", "border": "#c0c9b9",
}


class DashboardPage(tk.Frame):
    """Server dashboard arranged as the two-column reference design."""

    def __init__(
        self, parent: tk.Misc, config: AppConfig, *, on_start: Callable[[], None],
        on_stop: Callable[[], None], on_update: Callable[[], None],
        on_diagnostics: Callable[[], None], on_clear_console: Callable[[], None],
        on_scroll_console: Callable[[], None], on_console_manual_scroll: Callable[[], None],
    ) -> None:
        super().__init__(parent, background=PALETTE["background"])
        self.config = config
        self._scroll_canvas = tk.Canvas(self, background=PALETTE["background"], highlightthickness=0)
        self._scrollbar = tk.Scrollbar(self, orient="vertical", command=self._scroll_canvas.yview)
        self._scroll_canvas.configure(yscrollcommand=self._scrollbar.set)
        self._scrollbar.pack(side="right", fill="y")
        self._scroll_canvas.pack(side="left", fill="both", expand=True)
        self.content = tk.Frame(self._scroll_canvas, background=PALETTE["background"], padx=24, pady=24)
        self._content_window = self._scroll_canvas.create_window(0, 0, anchor="nw", window=self.content)
        self.content.bind("<Configure>", self._update_scroll_region, add="+")
        self._scroll_canvas.bind("<Configure>", self._resize_content, add="+")
        self.bind("<Configure>", self._on_resize, add="+")
        self._build(on_start, on_stop, on_update, on_diagnostics, on_clear_console, on_scroll_console, on_console_manual_scroll)

    @staticmethod
    def _card(parent: tk.Misc, **kwargs: object) -> RoundedPanel:
        return RoundedPanel(parent, background=PALETTE["card"], border=PALETTE["border"], radius=8, **kwargs)

    @staticmethod
    def _section_header(parent: tk.Misc, title: str) -> None:
        header = tk.Frame(parent, background=PALETTE["card_high"])
        header.pack(fill="x", padx=1, pady=1)
        tk.Label(header, text=title, background=PALETTE["card_high"], foreground=PALETTE["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=16, pady=10)

    def _build(self, on_start: Callable[[], None], on_stop: Callable[[], None], on_update: Callable[[], None], on_diagnostics: Callable[[], None], on_clear_console: Callable[[], None], on_scroll_console: Callable[[], None], on_console_manual_scroll: Callable[[], None]) -> None:
        self.layout = tk.Frame(self.content, background=PALETTE["background"])
        self.layout.pack(fill="both", expand=True)
        self.layout.columnconfigure(0, weight=2, minsize=500)
        self.layout.columnconfigure(1, weight=1, minsize=300)
        self.layout.rowconfigure(1, weight=1)

        self.server_card = self._card(self.layout, height=224)
        self.server_card.grid(row=0, column=0, sticky="nsew", padx=(0, 16), pady=(0, 16))
        server_content = self.server_card.content
        title_row = tk.Frame(server_content, background=PALETTE["card"])
        title_row.pack(fill="x", padx=20, pady=(18, 10))
        title_text = tk.Frame(title_row, background=PALETTE["card"])
        title_text.pack(side="left", fill="x", expand=True)
        self.server_status_label = tk.Label(title_text, text="SERVER STOPPED", background=PALETTE["card"], foreground=PALETTE["text"], font=("Segoe UI", 18, "bold"), anchor="w")
        self.server_status_label.pack(anchor="w")
        tk.Label(title_text, text=create_app_message(self.config), background=PALETTE["card"], foreground=PALETTE["muted"], font=("Segoe UI", 9), anchor="w").pack(anchor="w", pady=(3, 0))
        self.server_system_label = tk.Label(title_row, text="SYSTEM READY", background=PALETTE["primary_light"], foreground=PALETTE["primary"], font=("Segoe UI", 8, "bold"), padx=10, pady=5)
        self.server_system_label.pack(side="right", anchor="n")
        self.mode_var = tk.StringVar(value="background")
        actions = tk.Frame(server_content, background=PALETTE["card"])
        actions.pack(fill="x", padx=20, pady=(4, 18))
        button_style = {"relief": "flat", "font": ("Segoe UI", 9, "bold"), "padx": 14, "pady": 9}
        self.start_server_button = tk.Button(actions, text="START SERVER", command=on_start, background=PALETTE["primary"], activebackground=PALETTE["primary_dark"], foreground="#ffffff", activeforeground="#ffffff", **button_style)
        self.start_server_button.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.stop_server_button = tk.Button(actions, text="STOP SERVER", command=on_stop, state="disabled", background="#ffffff", activebackground="#ffdad6", foreground=PALETTE["danger"], activeforeground=PALETTE["danger"], highlightbackground=PALETTE["danger"], highlightthickness=1, **button_style)
        self.stop_server_button.pack(side="left", fill="x", expand=True, padx=(6, 0))

        self.console_card = self._card(self.layout, height=420)
        self.console_card.grid(row=1, column=0, sticky="nsew", padx=(0, 16))
        console_header = tk.Frame(self.console_card.content, background=PALETTE["card_high"])
        console_header.pack(fill="x", padx=1, pady=1)
        tk.Label(console_header, text="LIVE CONSOLE", background=PALETTE["card_high"], foreground=PALETTE["muted"], font=("Segoe UI", 9, "bold")).pack(side="left", padx=16, pady=10)
        console_actions = tk.Frame(console_header, background=PALETTE["card_high"])
        console_actions.pack(side="right", padx=10, pady=4)
        self.clear_console_button = CanvasIconButton(console_actions, icon="delete_sweep", tooltip="Clear Console", command=on_clear_console, foreground=PALETTE["muted"], hover_background="#e2e2e2")
        self.clear_console_button.pack(side="left", padx=(0, 4))
        self.scroll_console_button = CanvasIconButton(console_actions, icon="arrow_downward", tooltip="Auto-scroll", command=on_scroll_console, foreground=PALETTE["muted"], hover_background="#e2e2e2")
        self.scroll_console_button.pack(side="left")
        self.output_text = scrolledtext.ScrolledText(self.console_card.content, height=16, state="disabled", background="#1e1e1e", foreground="#e2e2e2", insertbackground="#ffffff", borderwidth=0, font=("Consolas", 9), padx=12, pady=10)
        self.output_text.bind("<MouseWheel>", on_console_manual_scroll, add="+")
        self.output_text.bind("<Button-4>", on_console_manual_scroll, add="+")
        self.output_text.bind("<Button-5>", on_console_manual_scroll, add="+")
        self.output_text.vbar.bind("<Button-1>", on_console_manual_scroll, add="+")
        self.output_text.pack(fill="both", expand=True, padx=12, pady=(8, 12))

        self.network_card = self._card(self.layout, height=260)
        self.network_card.grid(row=0, column=1, sticky="new", pady=(0, 16))
        self._section_header(self.network_card.content, "NETWORK INFO")
        self.network_value_labels: dict[str, tk.Label] = {}
        network_rows = tk.Frame(self.network_card.content, background=PALETTE["card"])
        network_rows.pack(fill="x", padx=14, pady=(10, 0))
        for title, key in (("LAN IP (WSL)", "lan"), ("PUBLIC IP", "public")):
            row = tk.Frame(network_rows, background="#ffffff", highlightbackground=PALETTE["border"], highlightthickness=1)
            row.pack(fill="x", pady=(0, 8))
            tk.Label(row, text=title, background="#ffffff", foreground=PALETTE["muted"], font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=10, pady=(7, 0))
            value = tk.Label(row, text="WAITING FOR SERVER", background="#ffffff", foreground=PALETTE["text"], font=("Consolas", 9), anchor="w")
            value.pack(fill="x", padx=10, pady=(1, 7))
            self.network_value_labels[key] = value
        port_row = tk.Frame(network_rows, background=PALETTE["card"])
        port_row.pack(fill="x", pady=(2, 0))
        tk.Label(port_row, text="GAME PORT 8211 (UDP)", background=PALETTE["card"], foreground=PALETTE["muted"], font=("Segoe UI", 8, "bold")).pack(side="left")
        self.network_port_pill = StatusPill(port_row, "CHECKING", foreground=PALETTE["muted"], background="#ffffff")
        self.network_port_pill.pack(side="right")
        self.ip_label = tk.Label(self.network_card.content, text="", background=PALETTE["card"], foreground=PALETTE["secondary"])
        self.network_status_label = tk.Label(self.network_card.content, text="Network checks will run automatically.", background=PALETTE["card"], foreground=PALETTE["muted"], font=("Segoe UI", 8), anchor="w", justify="left", wraplength=260)
        self.network_status_label.pack(fill="x", padx=14, pady=(8, 0))

        self.diagnostics_card = self._card(self.layout, height=330)
        self.diagnostics_card.grid(row=1, column=1, sticky="new")
        self._section_header(self.diagnostics_card.content, "DIAGNOSTICS")
        self.environment_status_label = tk.Label(self.diagnostics_card.content, text="REFRESHING...", background=PALETTE["card"], foreground=PALETTE["muted"], font=("Segoe UI", 8, "bold"))
        self.environment_status_label.pack(anchor="w", padx=16, pady=(12, 4))
        self.environment_badges: dict[str, StatusPill] = {}
        rows = tk.Frame(self.diagnostics_card.content, background=PALETTE["card"])
        rows.pack(fill="x", padx=16)
        for label, key in (("WSL 2 Runtime", "wsl"), ("SteamCMD", "steamcmd"), ("PalServer.exe", "palserver")):
            row = tk.Frame(rows, background=PALETTE["card"])
            row.pack(fill="x", pady=5)
            tk.Label(row, text=label, background=PALETTE["card"], foreground=PALETTE["text"], font=("Segoe UI", 9)).pack(side="left")
            badge = StatusPill(row, "CHECKING", foreground=PALETTE["muted"], background="#ffffff")
            badge.pack(side="right")
            self.environment_badges[key] = badge
        controls = tk.Frame(self.diagnostics_card.content, background=PALETTE["card"])
        controls.pack(fill="x", side="bottom", padx=16, pady=16)
        tk.Button(controls, text="VIEW DIAGNOSTICS", command=on_diagnostics, background="#ffffff", activebackground=PALETTE["primary_light"], foreground=PALETTE["primary"], relief="flat", highlightbackground=PALETTE["primary"], highlightthickness=1, font=("Segoe UI", 8, "bold"), pady=7).pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.update_server_button = tk.Button(controls, text="UPDATE NOW", command=on_update, background=PALETTE["secondary"], activebackground="#144688", foreground="#ffffff", activeforeground="#ffffff", relief="flat", font=("Segoe UI", 8, "bold"), pady=8)
        self.update_server_button.pack(side="left", fill="x", expand=True, padx=(4, 0))

    def _update_scroll_region(self, _event: tk.Event[tk.Misc]) -> None:
        self._scroll_canvas.configure(scrollregion=self._scroll_canvas.bbox("all"))

    def _resize_content(self, event: tk.Event[tk.Misc]) -> None:
        self._scroll_canvas.itemconfigure(self._content_window, width=event.width)

    def _on_resize(self, event: tk.Event[tk.Misc]) -> None:
        if event.widget is not self:
            return
        compact = event.width < 900
        if compact:
            self.layout.columnconfigure(0, minsize=0)
            self.layout.columnconfigure(1, minsize=0)
            self.server_card.grid_configure(row=0, column=0, columnspan=1, padx=0, pady=(0, 16))
            self.network_card.grid_configure(row=1, column=0, padx=0, pady=(0, 16))
            self.diagnostics_card.grid_configure(row=2, column=0, padx=0, pady=(0, 16))
            self.console_card.grid_configure(row=3, column=0, padx=0)
        else:
            self.layout.columnconfigure(0, minsize=500)
            self.layout.columnconfigure(1, minsize=300)
            self.server_card.grid_configure(row=0, column=0, columnspan=1, padx=(0, 16), pady=(0, 16))
            self.console_card.grid_configure(row=1, column=0, padx=(0, 16))
            self.network_card.grid_configure(row=0, column=1, padx=0, pady=(0, 16))
            self.diagnostics_card.grid_configure(row=1, column=1, padx=0, pady=0)


class BackupsPage(tk.Frame):
    """Home for the existing verified all-world backup operation."""

    def __init__(self, parent: tk.Misc, *, on_backup: Callable[[], None]) -> None:
        super().__init__(parent, background=PALETTE["background"], padx=24, pady=20)
        panel = RoundedPanel(self, background=PALETTE["card"], border=PALETTE["border"], radius=8, height=230)
        panel.pack(fill="x", anchor="n")
        tk.Label(panel.content, text="BACKUPS", background=PALETTE["card"], foreground=PALETTE["text"], font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=24, pady=(24, 8))
        tk.Label(panel.content, text="Create a verified archive of every world save. The server must be stopped before backup begins.", background=PALETTE["card"], foreground=PALETTE["muted"], justify="left", wraplength=500).pack(anchor="w", padx=24)
        self.backup_worlds_button = tk.Button(panel.content, text="BACK UP ALL WORLD SAVES", command=on_backup, background=PALETTE["secondary"], activebackground="#144688", foreground="#ffffff", activeforeground="#ffffff", relief="flat", font=("Segoe UI", 10, "bold"), padx=18, pady=10)
        self.backup_worlds_button.pack(anchor="w", padx=24, pady=(22, 24))


class PlaceholderPage(tk.Frame):
    """A deliberately non-functional page reserved for a future feature."""

    def __init__(self, parent: tk.Misc, title: str) -> None:
        super().__init__(parent, background=PALETTE["background"])
        panel = RoundedPanel(self, background=PALETTE["card"], border=PALETTE["border"], radius=8, height=200)
        panel.pack(fill="x", padx=24, pady=20, anchor="n")
        tk.Label(panel.content, text=title.upper(), background=PALETTE["card"], foreground=PALETTE["text"], font=("Segoe UI", 20, "bold")).pack(pady=(48, 8))
        tk.Label(panel.content, text="This feature is being prepared.", background=PALETTE["card"], foreground=PALETTE["muted"], font=("Segoe UI", 10)).pack()
