"""Page views for the main application navigation."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from datetime import datetime
from tkinter import scrolledtext, ttk
from typing import Any

from ..config import AppConfig, create_app_message
from ..world_options import BackupArchive, SettingField, WorldSaveInfo
from .widgets import CanvasIconButton, RoundedPanel, StatusPill

PALETTE = {
    "background": "#f9f9f9", "card": "#eeeeee", "card_high": "#e8e8e8",
    "text": "#1a1c1c", "muted": "#40493d", "primary": "#1a6e1a",
    "primary_dark": "#003a04", "primary_light": "#e5f4e2",
    "secondary": "#335ea1", "danger": "#ba1a1a", "border": "#c0c9b9",
}

_LEDGER_COLUMN_WIDTHS = (212, 104, 90, 76, 84)


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
    """Read-only archive inventory and the existing verified backup action."""

    def __init__(self, parent: tk.Misc, *, on_backup: Callable[[], None]) -> None:
        super().__init__(parent, background=PALETTE["background"])
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
        self._archive_rows: list[tk.Frame] = []
        self._build(on_backup)

    @staticmethod
    def _card(parent: tk.Misc, **kwargs: object) -> RoundedPanel:
        return RoundedPanel(parent, background=PALETTE["card"], border=PALETTE["border"], radius=8, **kwargs)

    def _build(self, on_backup: Callable[[], None]) -> None:
        header = tk.Frame(self.content, background=PALETTE["background"])
        header.pack(fill="x", pady=(0, 20))
        text = tk.Frame(header, background=PALETTE["background"])
        text.pack(side="left", fill="x", expand=True)
        tk.Label(text, text="BACKUP OPERATIONS", background=PALETTE["background"], foreground=PALETTE["text"], font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(text, text="Manage verified world-save snapshots and review archive health.", background=PALETTE["background"], foreground=PALETTE["muted"], font=("Segoe UI", 10)).pack(anchor="w", pady=(6, 0))
        self.backup_worlds_button = tk.Button(header, text="+  CREATE SNAPSHOT", command=on_backup, background=PALETTE["secondary"], activebackground="#144688", foreground="#ffffff", activeforeground="#ffffff", relief="flat", font=("Segoe UI", 9, "bold"), padx=18, pady=10)
        self.backup_worlds_button.pack(side="right", anchor="n")

        self._stats = tk.Frame(self.content, background=PALETTE["background"])
        self._stats.pack(fill="x", pady=(0, 16))
        self._stat_cards: list[RoundedPanel] = []
        self._total_value = self._stat_card(self._stats, "TOTAL ARCHIVES", "--")
        self._storage_value = self._stat_card(self._stats, "STORAGE USED", "--")
        self._latest_value = self._stat_card(self._stats, "LATEST BACKUP", "--", highlighted=True)

        self.layout = tk.Frame(self.content, background=PALETTE["background"])
        self.layout.pack(fill="both", expand=True)
        self.layout.columnconfigure(0, weight=2, minsize=520)
        self.layout.columnconfigure(1, weight=1, minsize=270)

        self._left_column = tk.Frame(self.layout, background=PALETTE["background"])
        self._left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 16))

        self.ledger_card = self._card(self._left_column, height=360)
        self.ledger_card.pack(fill="both", expand=True)
        ledger_header = tk.Frame(self.ledger_card.content, background=PALETTE["card_high"])
        ledger_header.pack(fill="x", padx=1, pady=1)
        tk.Label(ledger_header, text="ARCHIVE LEDGER", background=PALETTE["card_high"], foreground=PALETTE["text"], font=("Segoe UI", 14, "bold")).pack(side="left", padx=16, pady=12)
        self._inventory_status = tk.Label(ledger_header, text="Loading archives...", background=PALETTE["card_high"], foreground=PALETTE["muted"], font=("Segoe UI", 8))
        self._inventory_status.pack(side="right", padx=16)
        self._ledger_body = tk.Frame(self.ledger_card.content, background="#ffffff")
        self._ledger_body.pack(fill="both", expand=True, padx=1, pady=(0, 1))
        columns = ("ID", "DATE", "TYPE", "SIZE", "STATUS")
        self._ledger_header_row = tk.Frame(self._ledger_body, background="#ffffff")
        self._ledger_header_row.pack(fill="x")
        for index, title in enumerate(columns):
            self._ledger_header_row.columnconfigure(index, minsize=_LEDGER_COLUMN_WIDTHS[index])
            tk.Label(self._ledger_header_row, text=title, background="#ffffff", foreground=PALETTE["muted"], font=("Segoe UI", 8, "bold"), anchor="w").grid(row=0, column=index, sticky="ew", padx=12, pady=9)
        self._empty_label = tk.Label(self._ledger_body, text="Loading archive inventory...", background="#ffffff", foreground=PALETTE["muted"], font=("Segoe UI", 10))
        self._empty_label.pack(fill="both", expand=True, pady=70)

        self._right_column = tk.Frame(self.layout, background=PALETTE["background"])
        self._right_column.grid(row=0, column=1, sticky="new")
        policy = self._card(self._right_column, height=292)
        policy.pack(fill="x", pady=(0, 16))
        tk.Label(policy.content, text="BACKUP POLICY", background=PALETTE["card"], foreground=PALETTE["text"], font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(16, 12))
        for title, value in (("AUTOMATED BACKUPS", "Not configured"), ("RETENTION LIMIT", "Not configured"), ("STORAGE QUOTA", "Not configured")):
            item = tk.Frame(policy.content, background="#ffffff", highlightbackground=PALETTE["border"], highlightthickness=1)
            item.pack(fill="x", padx=16, pady=(0, 10))
            tk.Label(item, text=title, background="#ffffff", foreground=PALETTE["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(8, 1))
            tk.Label(item, text=value, background="#ffffff", foreground=PALETTE["text"], font=("Segoe UI", 9)).pack(anchor="w", padx=10, pady=(0, 8))
        tk.Label(policy.content, text="Read-only preview; scheduling is not available yet.", background=PALETTE["card"], foreground=PALETTE["muted"], font=("Segoe UI", 8), wraplength=240, justify="left").pack(anchor="w", padx=16)

        heuristics = self._card(self._right_column, height=190)
        heuristics.pack(fill="x")
        tk.Label(heuristics.content, text="STORAGE HEURISTICS", background=PALETTE["card"], foreground=PALETTE["text"], font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(16, 10))
        tk.Label(heuristics.content, text="Archive growth forecasting will be available when an automated retention policy is configured.", background=PALETTE["card"], foreground=PALETTE["muted"], font=("Segoe UI", 9), justify="left", wraplength=235).pack(anchor="w", padx=16)

    def _stat_card(self, parent: tk.Misc, title: str, value: str, *, highlighted: bool = False) -> tk.Label:
        background = PALETTE["primary_light"] if highlighted else PALETTE["card"]
        card = RoundedPanel(parent, background=background, border=PALETTE["border"], radius=8, height=92)
        column = len(self._stat_cards)
        self._stat_cards.append(card)
        parent.columnconfigure(column, weight=1, uniform="backup_stats")
        card.grid(row=0, column=column, sticky="ew", padx=(0, 8) if column < 2 else 0)
        tk.Label(card.content, text=title, background=background, foreground=PALETTE["primary"] if highlighted else PALETTE["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(14, 4))
        label = tk.Label(card.content, text=value, background=background, foreground=PALETTE["text"], font=("Segoe UI", 16, "bold"))
        label.pack(anchor="w", padx=12)
        return label

    def set_inventory_loading(self) -> None:
        self._inventory_status.config(text="Loading archives...")
        self._clear_archive_rows()
        self._empty_label.config(text="Loading archive inventory...")
        self._empty_label.pack(fill="both", expand=True, pady=70)

    def set_inventory_error(self, error: str) -> None:
        self._inventory_status.config(text="Inventory unavailable")
        self._clear_archive_rows()
        self._empty_label.config(text=f"Unable to load archives.\n{error}", foreground=PALETTE["danger"])
        self._empty_label.pack(fill="both", expand=True, pady=58)
        self._total_value.config(text="--")
        self._storage_value.config(text="--")
        self._latest_value.config(text="--")

    def set_backup_archives(self, archives: list[BackupArchive]) -> None:
        self._clear_archive_rows()
        self._empty_label.pack_forget()
        self._inventory_status.config(text=f"{len(archives)} archive{'s' if len(archives) != 1 else ''}")
        self._total_value.config(text=str(len(archives)))
        self._storage_value.config(text=self._format_size(sum(archive.size_bytes for archive in archives)))
        self._latest_value.config(text=self._format_relative_time(archives[0].created_at) if archives else "--")
        if not archives:
            self._empty_label.config(text="No archive snapshots found.", foreground=PALETTE["muted"])
            self._empty_label.pack(fill="both", expand=True, pady=70)
            return
        for archive in archives:
            self._add_archive_row(archive)

    def _add_archive_row(self, archive: BackupArchive) -> None:
        row_background = "#ffffff" if archive.verified else "#fff7f6"
        row = tk.Frame(self._ledger_body, background=row_background, highlightbackground=PALETTE["border"], highlightthickness=1)
        row.pack(fill="x")
        self._archive_rows.append(row)
        values = (
            archive.path.stem.upper(),
            archive.created_at.strftime("%Y-%m-%d\n%H:%M"),
            "MANUAL",
            self._format_size(archive.size_bytes),
            "Verified" if archive.verified else "Invalid",
        )
        for index, value in enumerate(values):
            row.columnconfigure(index, minsize=_LEDGER_COLUMN_WIDTHS[index])
            color = PALETTE["primary"] if archive.verified and index == 4 else (PALETTE["danger"] if not archive.verified and index == 4 else PALETTE["text"])
            tk.Label(row, text=value, background=row_background, foreground=color, font=("Consolas" if index in (0, 1, 3) else "Segoe UI", 9), anchor="w", justify="left").grid(row=0, column=index, sticky="ew", padx=12, pady=10)

    def _clear_archive_rows(self) -> None:
        for row in self._archive_rows:
            row.destroy()
        self._archive_rows.clear()

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        if size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

    @staticmethod
    def _format_relative_time(created_at: datetime) -> str:
        seconds = max(0, int((datetime.now() - created_at).total_seconds()))
        if seconds < 60:
            return "Just now"
        if seconds < 3600:
            return f"{seconds // 60} min ago"
        if seconds < 86400:
            return f"{seconds // 3600} hr ago"
        return created_at.strftime("%Y-%m-%d")

    def _update_scroll_region(self, _event: tk.Event[tk.Misc]) -> None:
        self._scroll_canvas.configure(scrollregion=self._scroll_canvas.bbox("all"))

    def _resize_content(self, event: tk.Event[tk.Misc]) -> None:
        self._scroll_canvas.itemconfigure(self._content_window, width=event.width)

    def _on_resize(self, event: tk.Event[tk.Misc]) -> None:
        if event.widget is not self:
            return
        compact_stats = event.width < 500
        for index, card in enumerate(self._stat_cards):
            column = 0 if compact_stats else index
            card.grid_configure(row=index if compact_stats else 0, column=column, padx=0 if compact_stats else ((0, 8) if index < 2 else 0), pady=(0, 8) if compact_stats and index < 2 else 0)
        for column in range(3):
            self._stats.columnconfigure(column, weight=1 if not compact_stats or column == 0 else 0)
        if event.width < 900:
            self.layout.columnconfigure(0, minsize=0)
            self.layout.columnconfigure(1, minsize=0)
            self._left_column.grid_configure(row=0, column=0, padx=0, pady=(0, 16))
            self._right_column.grid_configure(row=1, column=0, padx=0)
        else:
            self.layout.columnconfigure(0, minsize=520)
            self.layout.columnconfigure(1, minsize=270)
            self._left_column.grid_configure(row=0, column=0, padx=(0, 16), pady=0)
            self._right_column.grid_configure(row=0, column=1, padx=0, pady=0)


class WorldPage(tk.Frame):
    """Read-only WorldOption.sav inspection page based on the World reference."""

    _CATEGORY_FIELDS = (
        ("difficulty", "DIFFICULTY PRESET", ("difficulty",)),
        (
            "player",
            "PLAYER & COMBAT",
            ("death_penalty", "exp_rate", "player_damage_rate_attack", "player_damage_rate_defense"),
        ),
        (
            "environment",
            "WORLD ENVIRONMENT",
            (
                "day_time_speed_rate",
                "night_time_speed_rate",
                "enable_player_to_player_damage",
                "enable_friendly_fire",
            ),
        ),
        (
            "pals",
            "PAL MANAGEMENT",
            (
                "pal_capture_rate",
                "pal_spawn_num_rate",
                "pal_damage_rate_attack",
                "pal_damage_rate_defense",
                "pal_stomach_decrease_rate",
                "drop_item_max_num_rate",
                "collection_drop_rate",
            ),
        ),
        ("system", "SYSTEM & SECURITY", ("server_player_max_num",)),
    )

    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_refresh: Callable[[], None],
        on_world_selected: Callable[[str], None],
        on_import_local: Callable[[], None],
        on_merge: Callable[[], None],
    ) -> None:
        super().__init__(parent, background=PALETTE["background"])
        self._on_refresh = on_refresh
        self._on_world_selected = on_world_selected
        self._on_import_local = on_import_local
        self._on_merge = on_merge
        self._section_cards: dict[str, tk.Widget] = {}
        self._world_var = tk.StringVar(value="")
        self._local_world_var = tk.StringVar(value="No local WorldOption.sav selected")

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

        self._build()

    @staticmethod
    def _card(parent: tk.Misc, **kwargs: object) -> RoundedPanel:
        return RoundedPanel(parent, background="#ffffff", border=PALETTE["border"], radius=8, **kwargs)

    def _build(self) -> None:
        header = tk.Frame(self.content, background=PALETTE["background"])
        header.pack(fill="x", pady=(0, 16))
        heading = tk.Frame(header, background=PALETTE["background"])
        heading.pack(side="left", fill="x", expand=True)
        tk.Label(heading, text="World Settings", background=PALETTE["background"], foreground=PALETTE["text"], font=("Segoe UI", 24, "bold")).pack(anchor="w")
        tk.Label(heading, text="Inspect decoded world rules from WorldOption.sav.", background=PALETTE["background"], foreground=PALETTE["muted"], font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 0))

        actions = tk.Frame(header, background=PALETTE["background"])
        actions.pack(side="right", anchor="s")
        tk.Label(actions, text="WORLD", background=PALETTE["background"], foreground=PALETTE["muted"], font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 6))
        self._world_combo = ttk.Combobox(actions, textvariable=self._world_var, state="disabled", width=22)
        self._world_combo.pack(side="left", padx=(0, 8))
        self._world_combo.bind("<<ComboboxSelected>>", self._on_select)
        self.refresh_button = tk.Button(actions, text="REFRESH WORLDS", command=self._on_refresh, background=PALETTE["secondary"], activebackground="#144688", foreground="#ffffff", activeforeground="#ffffff", relief="flat", font=("Segoe UI", 8, "bold"), padx=12, pady=8)
        self.refresh_button.pack(side="left")

        self.import_button = tk.Button(actions, text="IMPORT LOCAL WORLD", command=self._on_import_local, background="#ffffff", activebackground="#f3f3f3", foreground=PALETTE["secondary"], relief="solid", borderwidth=1, font=("Segoe UI", 8, "bold"), padx=12, pady=8)
        self.import_button.pack(side="left", padx=(8, 0))

        self._read_only_banner = tk.Frame(self.content, background="#ffdad6", highlightbackground=PALETTE["danger"], highlightthickness=1)
        self._read_only_banner.pack(fill="x", pady=(0, 24))
        tk.Label(self._read_only_banner, text="READ-ONLY INSPECTION", background="#ffdad6", foreground="#93000a", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16, pady=(12, 2))
        tk.Label(self._read_only_banner, text="Saving is unavailable until WorldOption.sav parsing has been verified with a real game save.", background="#ffdad6", foreground="#93000a", font=("Segoe UI", 9), wraplength=900, justify="left").pack(anchor="w", padx=16, pady=(0, 12))

        self._merge_card = self._card(self.content)
        self._merge_card.pack(fill="x", pady=(0, 16))
        merge_header = tk.Frame(self._merge_card.content, background="#ffffff")
        merge_header.pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(merge_header, text="SAFE GAME SETTINGS MERGE", background="#ffffff", foreground=PALETTE["primary"], font=("Segoe UI", 12, "bold")).pack(side="left")
        self.merge_button = tk.Button(merge_header, text="MERGE GAME SETTINGS TO WSL WORLD", command=self._on_merge, state="disabled", background=PALETTE["secondary"], activebackground="#144688", foreground="#ffffff", disabledforeground="#7d8590", relief="flat", font=("Segoe UI", 8, "bold"), padx=12, pady=8)
        self.merge_button.pack(side="right")
        tk.Label(self._merge_card.content, textvariable=self._local_world_var, background="#ffffff", foreground=PALETTE["muted"], font=("Consolas", 9), anchor="w").pack(fill="x", padx=16, pady=(2, 8))
        self._merge_status = tk.Label(self._merge_card.content, text="Select a WSL world and import a local WorldOption.sav to preview gameplay-only changes.", background="#f3f3f3", foreground=PALETTE["muted"], font=("Segoe UI", 9), justify="left", anchor="w", wraplength=900)
        self._merge_status.pack(fill="x", padx=16, pady=(0, 14))

        self._preserved_card = self._card(self.content)
        self._preserved_card.pack(fill="x", pady=(0, 24))
        tk.Label(self._preserved_card.content, text="SERVER SETTINGS PROTECTED", background="#ffffff", foreground=PALETTE["primary"], font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(14, 4))
        tk.Label(self._preserved_card.content, text="AdminPassword, REST API, and RCON values are preserved from the WSL world. Password values are never displayed or copied from the local world.", background="#ffffff", foreground=PALETTE["muted"], font=("Segoe UI", 9), justify="left", wraplength=900).pack(anchor="w", padx=16, pady=(0, 14))

        self.layout = tk.Frame(self.content, background=PALETTE["background"])
        self.layout.pack(fill="both", expand=True)
        self.layout.columnconfigure(1, weight=1)

        self._categories = tk.Frame(self.layout, background=PALETTE["background"], width=220)
        self._categories.grid(row=0, column=0, sticky="new", padx=(0, 16))
        self._categories.grid_propagate(False)
        tk.Label(self._categories, text="CATEGORIES", background=PALETTE["background"], foreground=PALETTE["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(4, 8))
        for key, title, _field_keys in self._CATEGORY_FIELDS:
            tk.Button(self._categories, text=title.title(), command=lambda section=key: self._scroll_to(section), anchor="w", relief="flat", borderwidth=0, background=PALETTE["background"], activebackground=PALETTE["card_high"], foreground=PALETTE["muted"], activeforeground=PALETTE["text"], font=("Segoe UI", 9), padx=12, pady=8).pack(fill="x", pady=1)
        tk.Button(self._categories, text="Full JSON", command=lambda: self._scroll_to("json"), anchor="w", relief="flat", borderwidth=0, background=PALETTE["background"], activebackground=PALETTE["card_high"], foreground=PALETTE["muted"], activeforeground=PALETTE["text"], font=("Segoe UI", 9), padx=12, pady=8).pack(fill="x", pady=1)

        self._details = tk.Frame(self.layout, background=PALETTE["background"])
        self._details.grid(row=0, column=1, sticky="nsew")
        self._details_status = tk.Label(self._details, text="Choose a world to inspect its decoded settings.", background="#ffffff", foreground=PALETTE["muted"], font=("Segoe UI", 10), justify="left")
        self._details_status.pack(fill="x", padx=1, pady=1)

    def _update_scroll_region(self, _event: tk.Event[tk.Misc]) -> None:
        self._scroll_canvas.configure(scrollregion=self._scroll_canvas.bbox("all"))

    def _resize_content(self, event: tk.Event[tk.Misc]) -> None:
        self._scroll_canvas.itemconfigure(self._content_window, width=event.width)

    def _on_resize(self, event: tk.Event[tk.Misc]) -> None:
        if event.widget is not self:
            return
        if event.width < 900:
            self._categories.grid_configure(row=0, column=0, columnspan=2, sticky="ew", padx=0, pady=(0, 12))
            self._details.grid_configure(row=1, column=0, columnspan=2, sticky="nsew")
        else:
            self._categories.grid_configure(row=0, column=0, columnspan=1, sticky="new", padx=(0, 16), pady=0)
            self._details.grid_configure(row=0, column=1, columnspan=1, sticky="nsew")

    def _on_select(self, _event: object = None) -> None:
        world_id = self._world_var.get()
        if world_id:
            self._on_world_selected(world_id)

    def _scroll_to(self, section: str) -> None:
        card = self._section_cards.get(section)
        if card is None:
            return
        self.update_idletasks()
        total_height = max(self.content.winfo_height(), 1)
        self._scroll_canvas.yview_moveto(max(0.0, card.winfo_y() / total_height))

    def _clear_details(self) -> None:
        for child in self._details.winfo_children():
            child.destroy()
        self._section_cards.clear()

    def set_scan_loading(self) -> None:
        self.refresh_button.config(state="disabled", text="REFRESHING...")
        self._world_combo.config(state="disabled", values=())
        self._world_var.set("")
        self._clear_details()
        self._details_status = tk.Label(self._details, text="Scanning for WorldOption.sav files...", background="#ffffff", foreground=PALETTE["muted"], font=("Segoe UI", 10), justify="left")
        self._details_status.pack(fill="x", padx=1, pady=1)

    def set_worlds(self, worlds: list[WorldSaveInfo]) -> None:
        self.refresh_button.config(state="normal", text="REFRESH WORLDS")
        self._world_var.set("")
        if not worlds:
            self._world_combo.config(state="disabled", values=())
            self._clear_details()
            self._details_status = tk.Label(self._details, text="No WorldOption.sav files were found. Refresh after the server saves a world.", background="#ffffff", foreground=PALETTE["muted"], font=("Segoe UI", 10), justify="left", wraplength=700)
            self._details_status.pack(fill="x", padx=16, pady=32)
            return
        self._world_combo.config(state="readonly", values=[world.world_id for world in worlds])
        self._clear_details()
        self._details_status = tk.Label(self._details, text="Choose a world to inspect its decoded settings.", background="#ffffff", foreground=PALETTE["muted"], font=("Segoe UI", 10), justify="left")
        self._details_status.pack(fill="x", padx=16, pady=32)

    def set_scan_error(self, error: str) -> None:
        self.refresh_button.config(state="normal", text="REFRESH WORLDS")
        self._world_combo.config(state="disabled", values=())
        self._world_var.set("")
        self._clear_details()
        self._details_status = tk.Label(self._details, text=f"Unable to scan world saves.\n{error}", background="#ffdad6", foreground="#93000a", font=("Segoe UI", 10), justify="left", wraplength=700)
        self._details_status.pack(fill="x", padx=1, pady=1)

    def set_decode_loading(self, world_id: str) -> None:
        self._clear_details()
        self._details_status = tk.Label(self._details, text=f"Decoding {world_id}...", background="#ffffff", foreground=PALETTE["muted"], font=("Segoe UI", 10))
        self._details_status.pack(fill="x", padx=16, pady=32)

    def set_external_processing(self, message: str) -> None:
        """Show a non-editing external inspection stage while controls are locked."""
        self.refresh_button.config(state="disabled", text="PROCESSING...")
        self._world_combo.config(state="disabled")
        self.import_button.config(state="disabled")
        self.merge_button.config(state="disabled")
        self._clear_details()
        self._details_status = tk.Label(
            self._details,
            text=message,
            background="#ffffff",
            foreground=PALETTE["muted"],
            font=("Segoe UI", 10),
            justify="left",
            wraplength=700,
        )
        self._details_status.pack(fill="x", padx=16, pady=32)

    def finish_external_processing(self, world_id: str, message: str, *, error: bool = False) -> None:
        """Restore page controls after a PST workflow finishes or fails."""
        self.refresh_button.config(state="normal", text="REFRESH WORLDS")
        if self._world_combo.cget("values"):
            self._world_combo.config(state="readonly")
            self._world_var.set(world_id)
        self.import_button.config(state="normal")
        self._clear_details()
        self._details_status = tk.Label(
            self._details,
            text=message,
            background="#ffdad6" if error else "#ffffff",
            foreground="#93000a" if error else PALETTE["primary"],
            font=("Segoe UI", 10),
            justify="left",
            wraplength=700,
        )
        self._details_status.pack(fill="x", padx=16, pady=32)

    def set_decode_error(self, error: str) -> None:
        self._clear_details()
        self._details_status = tk.Label(self._details, text=f"Unable to decode the selected WorldOption.sav.\n{error}", background="#ffdad6", foreground="#93000a", font=("Segoe UI", 10), justify="left", wraplength=700)
        self._details_status.pack(fill="x", padx=1, pady=1)

    def set_local_world_loading(self, path: str) -> None:
        self._local_world_var.set(path)
        self._merge_status.config(text="Decoding local WorldOption.sav and preparing a safe merge preview...")
        self.merge_button.config(state="disabled")

    def set_local_world_error(self, error: str) -> None:
        self._local_world_var.set("Local WorldOption.sav could not be imported")
        self._merge_status.config(text=f"Unable to decode local WorldOption.sav.\n{error}", background="#ffdad6", foreground="#93000a")
        self.merge_button.config(state="disabled")

    def set_merge_preview(
        self,
        *,
        local_path: str,
        updated_count: int,
        unavailable_count: int,
        preserved_fields: tuple[str, ...],
        write_ready: bool,
    ) -> None:
        self._local_world_var.set(local_path)
        preserved = ", ".join(preserved_fields) if preserved_fields else "server-owned settings"
        if write_ready:
            message = (
                f"Ready: {updated_count} gameplay fields will be updated; "
                f"{unavailable_count} unavailable fields remain unchanged. Preserved: {preserved}."
            )
        else:
            message = (
                f"Preview only: {updated_count} gameplay fields differ; "
                f"{unavailable_count} unavailable fields remain unchanged. Preserved: {preserved}. "
                "Writing remains disabled until the codec passes real PlM round-trip verification."
            )
        self._merge_status.config(text=message, background="#f3f3f3", foreground=PALETTE["muted"])
        self.merge_button.config(state="normal" if write_ready else "disabled")

    def set_decoded(
        self,
        settings: list[tuple[SettingField, Any | None]],
        json_text: str,
    ) -> None:
        self._clear_details()
        values = {field.key: (field, value) for field, value in settings}
        for category, title, field_keys in self._CATEGORY_FIELDS:
            card = self._card(self._details)
            card.pack(fill="x", pady=(0, 16))
            self._section_cards[category] = card
            header = tk.Frame(card.content, background="#ffffff")
            header.pack(fill="x", padx=16, pady=(16, 10))
            tk.Label(header, text=title, background="#ffffff", foreground=PALETTE["primary"], font=("Segoe UI", 14, "bold")).pack(anchor="w")
            if category == "difficulty":
                self._build_difficulty(card.content, values.get("difficulty"))
            else:
                self._build_setting_rows(card.content, [values.get(key) for key in field_keys])
        self._build_json_card(json_text)

    def _build_difficulty(
        self,
        parent: tk.Misc,
        setting: tuple[SettingField, Any | None] | None,
    ) -> None:
        container = tk.Frame(parent, background="#ffffff")
        container.pack(fill="x", padx=16, pady=(0, 16))
        current = setting[1] if setting is not None else None
        for choice in ("Casual", "Normal", "Hard", "Custom"):
            selected = choice == current
            tile = tk.Frame(container, background="#e5f4e2" if selected else "#f3f3f3", highlightbackground=PALETTE["primary"] if selected else PALETTE["border"], highlightthickness=1)
            tile.pack(side="left", fill="x", expand=True, padx=(0, 8) if choice != "Custom" else 0)
            label = f"{choice}" if current is not None else "Unavailable"
            tk.Label(tile, text=label, background=tile["background"], foreground=PALETTE["text"], font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(10, 2))
            tk.Label(tile, text="Selected" if selected else "Read-only", background=tile["background"], foreground=PALETTE["muted"], font=("Segoe UI", 8)).pack(anchor="w", padx=10, pady=(0, 10))

    def _build_setting_rows(
        self,
        parent: tk.Misc,
        settings: list[tuple[SettingField, Any | None] | None],
    ) -> None:
        rows = tk.Frame(parent, background="#ffffff")
        rows.pack(fill="x", padx=16, pady=(0, 16))
        for setting in settings:
            row = tk.Frame(rows, background="#f3f3f3", highlightbackground=PALETTE["border"], highlightthickness=1)
            row.pack(fill="x", pady=(0, 8))
            if setting is None:
                label, value = "Unavailable", "Not supported by this save"
            else:
                field, setting_value = setting
                label = field.label
                if setting_value is None:
                    value = "Unavailable"
                elif field.kind == "bool":
                    value = "ON" if setting_value else "OFF"
                else:
                    value = str(setting_value)
            tk.Label(row, text=label, background="#f3f3f3", foreground=PALETTE["text"], font=("Segoe UI", 9, "bold"), anchor="w").pack(side="left", fill="x", expand=True, padx=12, pady=10)
            tk.Label(row, text=value, background="#ffffff", foreground=PALETTE["muted"], font=("Consolas", 9), anchor="e", padx=8, pady=4).pack(side="right", padx=8, pady=6)

    def _build_json_card(self, json_text: str) -> None:
        card = self._card(self._details)
        card.pack(fill="both", expand=True, pady=(0, 16))
        self._section_cards["json"] = card
        header = tk.Frame(card.content, background="#ffffff")
        header.pack(fill="x", padx=16, pady=(16, 8))
        tk.Label(header, text="FULL DECODED JSON", background="#ffffff", foreground=PALETTE["primary"], font=("Segoe UI", 14, "bold")).pack(side="left")
        self._json_search_var = tk.StringVar()
        search = tk.Entry(header, textvariable=self._json_search_var, width=24, background="#eeeeee", relief="flat")
        search.pack(side="right")
        search.bind("<Return>", lambda _event: self._find_json())
        tk.Button(header, text="FIND", command=self._find_json, background="#eeeeee", activebackground="#e2e2e2", foreground=PALETTE["muted"], relief="flat", font=("Segoe UI", 8, "bold"), padx=8, pady=4).pack(side="right", padx=(0, 6))
        self._json_text = scrolledtext.ScrolledText(card.content, height=20, state="normal", background="#1e1e1e", foreground="#e2e2e2", insertbackground="#ffffff", borderwidth=0, font=("Consolas", 9), wrap="none", padx=12, pady=10)
        self._json_text.insert("1.0", json_text)
        self._json_text.config(state="disabled")
        self._json_text.tag_configure("search_hit", background="#8f6f00")
        self._json_text.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    def _find_json(self) -> None:
        query = self._json_search_var.get()
        if not query or not hasattr(self, "_json_text"):
            return
        self._json_text.tag_remove("search_hit", "1.0", tk.END)
        found = self._json_text.search(query, self._json_text.index(tk.INSERT), stopindex=tk.END, nocase=True)
        if not found:
            found = self._json_text.search(query, "1.0", stopindex=tk.END, nocase=True)
        if found:
            end = f"{found}+{len(query)}c"
            self._json_text.tag_add("search_hit", found, end)
            self._json_text.mark_set(tk.INSERT, end)
            self._json_text.see(found)


class PlaceholderPage(tk.Frame):
    """A deliberately non-functional page reserved for a future feature."""

    def __init__(self, parent: tk.Misc, title: str) -> None:
        super().__init__(parent, background=PALETTE["background"])
        panel = RoundedPanel(self, background=PALETTE["card"], border=PALETTE["border"], radius=8, height=200)
        panel.pack(fill="x", padx=24, pady=20, anchor="n")
        tk.Label(panel.content, text=title.upper(), background=PALETTE["card"], foreground=PALETTE["text"], font=("Segoe UI", 20, "bold")).pack(pady=(48, 8))
        tk.Label(panel.content, text="This feature is being prepared.", background=PALETTE["card"], foreground=PALETTE["muted"], font=("Segoe UI", 10)).pack()
