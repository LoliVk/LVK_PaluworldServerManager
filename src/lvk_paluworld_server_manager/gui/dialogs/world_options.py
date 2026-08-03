"""WorldOption.sav editor dialog."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import Any

from ... import server, world_options

#: Sentinel placed on the world-option queue once a background task finishes.
_WORLD_OPTIONS_DONE = object()


class WorldOptionEditorDialog(tk.Toplevel):
    """Modal dialog for discovering and inspecting ``WorldOption.sav``.

    Follows the same worker-thread + :class:`queue.Queue` + :meth:`after`
    pattern as :class:`DiagnosticDialog`/:class:`NetworkSetupDialog` so all
    GVAS decode work happens off the Tk main thread.

    The dialog never guesses which world to edit: it scans the dedicated
    server's ``SaveGames/0`` directory and lets the user choose. This dialog
    is deliberately read-only until parsing has been verified with a real
    save; it never creates backups or writes a save file.
    """

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self._parent = parent
        self._queue: queue.Queue[object] = queue.Queue()
        self._poll_job: str | None = None

        self._worlds: list[world_options.WorldSaveInfo] = []
        self._gvas_file: Any | None = None  # GvasFile once decoded

        self.title("檢視世界設定 / View World Settings")
        self.geometry("640x640")
        self.resizable(False, False)
        self.grab_set()
        self.configure(padx=16, pady=16)

        tk.Label(
            self,
            text="世界設定檢視器\nWorld Settings Viewer",
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
            text="唯讀模式 / Read-only mode: saving is unavailable until real-save verification.",
            foreground="#b05000",
            font=("Segoe UI", 9),
        )
        warning_label.pack(fill="x", pady=(8, 0))

        button_frame = tk.Frame(self)
        button_frame.pack(pady=(8, 0))

        self._read_only_button = tk.Button(
            button_frame,
            text="唯讀 / Read-only",
            width=18,
            state="disabled",
        )
        self._read_only_button.pack(side="left", padx=4)

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
            elif kind == "decoded":
                self._on_decoded(payload)

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
        self._status_label.config(text="請選擇要檢視的世界 / Select a world to view")

    def _on_world_selected(self, _event: object = None) -> None:
        world_id = self._world_var.get()
        world = next((w for w in self._worlds if w.world_id == world_id), None)
        if world is None:
            return
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
        _world, gvas_file, _save_type = payload
        self._gvas_file = gvas_file
        self._render_settings_form(gvas_file.properties)
        self._set_json_content(world_options.dump_gvas_json(gvas_file))
        self._status_label.config(text="讀取成功 / Loaded successfully", foreground="#1a6e1a")

    def _render_settings_form(self, properties: dict[str, Any]) -> None:
        """(Re)build the grouped settings form from the decoded properties."""
        for child in self._settings_frame.winfo_children():
            child.destroy()
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
                    tk.Checkbutton(row, variable=var, state="disabled").pack(side="left")
                elif field.kind == "enum":
                    var = tk.StringVar(value=str(value))
                    ttk.Combobox(
                        row,
                        textvariable=var,
                        values=list(field.enum_choices),
                        state="disabled",
                        width=20,
                    ).pack(side="left")
                else:
                    var = tk.StringVar(value=str(value))
                    tk.Entry(row, textvariable=var, width=20, state="disabled").pack(side="left")
