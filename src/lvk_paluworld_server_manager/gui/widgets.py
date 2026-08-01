"""Reusable Tk widgets used by the application's page views."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from typing import Any


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
