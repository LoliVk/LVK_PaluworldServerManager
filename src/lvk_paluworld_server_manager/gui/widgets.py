"""Reusable Tk widgets used by the application's page views."""

from __future__ import annotations

import ctypes
import sys
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import font as tkfont
from typing import Any

_MATERIAL_SYMBOLS_FONT_FAMILY = "Material Symbols Outlined"
_MATERIAL_SYMBOLS_FONT_PATH = (
    Path(__file__).resolve().parents[1]
    / "resources"
    / "fonts"
    / "MaterialSymbolsOutlined.ttf"
)
_MATERIAL_SYMBOLS_GLYPHS = {
    "backup": "\ue864",
    "dashboard": "\ue871",
    "delete_sweep": "\ue16c",
    "public": "\ue80b",
    "query_stats": "\ue4fc",
    "arrow_downward": "\ue5db",
}
_material_symbols_registered = False


def _register_material_symbols_font() -> bool:
    """Register the bundled Material Symbols font for this Windows process."""
    global _material_symbols_registered
    if _material_symbols_registered:
        return True
    if sys.platform != "win32" or not _MATERIAL_SYMBOLS_FONT_PATH.is_file():
        return False
    _material_symbols_registered = bool(
        ctypes.windll.gdi32.AddFontResourceExW(str(_MATERIAL_SYMBOLS_FONT_PATH), 0x10, None)
    )
    return _material_symbols_registered


class RoundedPanel(tk.Canvas):
    """A lightweight rounded surface that keeps standard Tk widgets inside it."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        background: str,
        border: str,
        radius: int = 12,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            parent,
            background=background,
            highlightthickness=0,
            borderwidth=0,
            **kwargs,
        )
        self._surface_background = background
        self._surface_border = border
        self._radius = radius
        self.content = tk.Frame(self, background=background)
        self._content_window = self.create_window(1, 1, anchor="nw", window=self.content)
        self.bind("<Configure>", self._resize_surface, add="+")

    def _resize_surface(self, event: tk.Event[tk.Misc]) -> None:
        width = max(event.width, 2)
        height = max(event.height, 2)
        radius = min(self._radius, width // 2, height // 2)
        self.delete("surface")
        self.create_rectangle(radius, 0, width - radius, height, fill=self._surface_background, outline="", tags="surface")
        self.create_rectangle(0, radius, width, height - radius, fill=self._surface_background, outline="", tags="surface")
        for x, y, start in (
            (0, 0, 90),
            (width - radius * 2, 0, 0),
            (0, height - radius * 2, 180),
            (width - radius * 2, height - radius * 2, 270),
        ):
            self.create_arc(x, y, x + radius * 2, y + radius * 2, start=start, extent=90, fill=self._surface_background, outline=self._surface_border, tags="surface")
        self.create_rectangle(radius, 0, width - radius, height, outline=self._surface_border, tags="surface")
        self.create_rectangle(0, radius, width, height - radius, outline=self._surface_border, tags="surface")
        self.tag_lower("surface")
        self.coords(self._content_window, 1, 1)
        self.itemconfigure(self._content_window, width=max(width - 2, 1), height=max(height - 2, 1))


class StatusPill(tk.Canvas):
    """Small rounded status badge without adding a themed-widget dependency."""

    def __init__(self, parent: tk.Misc, text: str, *, foreground: str, background: str) -> None:
        super().__init__(parent, height=22, highlightthickness=0, background=parent.cget("background"))
        self._text = ""
        self._foreground = foreground
        self._background = background
        self._font = tkfont.Font(family="Segoe UI", size=8, weight="bold")
        self.set(text, foreground=foreground, background=background)

    def set(self, text: str, *, foreground: str | None = None, background: str | None = None) -> None:
        self._text = text
        self._foreground = foreground or self._foreground
        self._background = background or self._background
        width = self._font.measure(text) + 22
        self.configure(width=width)
        self.delete("all")
        self.create_oval(0, 0, 22, 22, fill=self._background, outline="")
        self.create_oval(width - 22, 0, width, 22, fill=self._background, outline="")
        self.create_rectangle(11, 0, width - 11, 22, fill=self._background, outline="")
        self.create_text(width // 2, 11, text=text, font=self._font, fill=self._foreground)


class CanvasIconButton(tk.Canvas):
    """A compact Canvas-drawn icon button with hover and tooltip support."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        icon: str,
        tooltip: str,
        command: Callable[[], None],
        foreground: str,
        hover_background: str,
    ) -> None:
        super().__init__(
            parent,
            width=24,
            height=24,
            background=parent.cget("background"),
            highlightthickness=0,
            borderwidth=0,
            cursor="hand2",
            takefocus=True,
        )
        self._icon = icon
        self._tooltip_text = tooltip
        self._command = command
        self._foreground = foreground
        self._hover_background = hover_background
        self._tooltip: tk.Toplevel | None = None
        self._tooltip_job: str | None = None
        self._hovered = False
        self._use_material_symbols = _register_material_symbols_font()
        self._draw()
        self.bind("<Enter>", self._on_enter, add="+")
        self.bind("<Leave>", self._on_leave, add="+")
        self.bind("<Button-1>", self._on_click, add="+")
        self.bind("<Return>", self._on_click, add="+")
        self.bind("<space>", self._on_click, add="+")

    def invoke(self) -> None:
        """Run the button's action, matching the useful part of ``tk.Button``."""
        self._command()

    def set_colors(self, *, background: str, foreground: str) -> None:
        """Synchronize the icon with its parent navigation item's state."""
        self.configure(background=background)
        self._foreground = foreground
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        if self._hovered:
            self.create_oval(0, 0, 24, 24, fill=self._hover_background, outline="")
            self.create_rectangle(0, 6, 24, 18, fill=self._hover_background, outline="")
        glyph = _MATERIAL_SYMBOLS_GLYPHS.get(self._icon)
        if self._use_material_symbols and glyph is not None:
            self.create_text(
                12,
                12,
                text=glyph,
                fill=self._foreground,
                font=(_MATERIAL_SYMBOLS_FONT_FAMILY, 16),
            )
        elif self._icon == "delete_sweep":
            # A 16 px interpretation of Material's delete_sweep: bin on the
            # left, with the sweeping arrow clearly separated on the right.
            # It remains as a fallback if Windows cannot register the font.
            self.create_line(7, 7, 8, 17, 12, 17, 13, 7, fill=self._foreground, width=1)
            self.create_line(6, 6, 14, 6, fill=self._foreground, width=1)
            self.create_line(9, 5, 11, 5, fill=self._foreground, width=1)
            self.create_line(15, 11, 19, 11, fill=self._foreground, width=1)
            self.create_line(17, 9, 19, 11, 17, 13, fill=self._foreground, width=1)
        elif self._icon == "arrow_downward":
            self.create_line(12, 5, 12, 18, fill=self._foreground, width=1)
            self.create_line(8, 14, 12, 18, 16, 14, fill=self._foreground, width=1)

    def _on_enter(self, _event: tk.Event[tk.Misc]) -> None:
        self._hovered = True
        self._draw()
        self._tooltip_job = self.after(500, self._show_tooltip)

    def _on_leave(self, _event: tk.Event[tk.Misc]) -> None:
        self._hovered = False
        self._draw()
        if self._tooltip_job is not None:
            self.after_cancel(self._tooltip_job)
            self._tooltip_job = None
        self._hide_tooltip()

    def _on_click(self, _event: tk.Event[tk.Misc]) -> str:
        self.invoke()
        return "break"

    def _show_tooltip(self) -> None:
        self._tooltip_job = None
        if not self._hovered or self._tooltip is not None:
            return
        tooltip = tk.Toplevel(self)
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(f"+{self.winfo_rootx()}+{self.winfo_rooty() + 28}")
        tk.Label(
            tooltip,
            text=self._tooltip_text,
            background="#2f3131",
            foreground="#f1f1f0",
            font=("Segoe UI", 8),
            padx=6,
            pady=3,
        ).pack()
        self._tooltip = tooltip

    def _hide_tooltip(self) -> None:
        if self._tooltip is not None:
            self._tooltip.destroy()
            self._tooltip = None
