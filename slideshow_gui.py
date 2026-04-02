#!/usr/bin/env python3
"""
Slideshow-Generator GUI - modernes dunkles Design
Importiert create_slideshow direkt (kein Subprocess-Aufruf).
"""

import argparse
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog

import create_slideshow  # direkt importieren - kein Subprocess noetig

# ── Farbpalette ────────────────────────────────────────────────────────────────
BG        = "#16161e"
SURFACE   = "#1f1f2e"
SURFACE2  = "#2a2a3d"
ACCENT    = "#7c6af7"
ACCENT_H  = "#9d8fff"
TEXT      = "#dcdcef"
TEXT_DIM  = "#7878a0"
SUCCESS   = "#4ade80"
WARNING   = "#facc15"
ERROR     = "#f87171"
BORDER    = "#35354d"
BTN_FG    = "#ffffff"
MUSIC_ACC = "#f472b6"

FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_LABEL = ("Segoe UI", 9)
FONT_MONO  = ("Consolas", 9)
FONT_BTN   = ("Segoe UI", 11, "bold")

RESOLUTIONS = {
    "1920 x 1080  (Full HD)":    (1920, 1080),
    "1280 x 720   (HD)":         (1280,  720),
    "3840 x 2160  (4K)":         (3840, 2160),
    "2560 x 1440  (QHD)":        (2560, 1440),
    "1080 x 1920  (Hochformat)": (1080, 1920),
    "Benutzerdefiniert":          None,
}

MUSIC_TRANSITIONS = {
    "none":      "Kein Uebergang (direkter Schnitt)",
    "crossfade": "Crossfade (ueberlappend)",
    "fadeout":   "Fadeout (nur Ausblenden)",
    "fadeinout": "Fade In & Out (Ein- und Ausblenden)",
}


class SlideshowGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Slideshow Generator")
        self.root.configure(bg=BG)
        self.root.minsize(820, 750)
        self.root.resizable(True, True)

        # Variablen
        self.folder_var     = tk.StringVar()
        self.output_var     = tk.StringVar(value="slideshow.mp4")
        self.duration_var   = tk.DoubleVar(value=5.0)
        self.transition_var = tk.DoubleVar(value=1.2)
        self.fps_var        = tk.IntVar(value=25)
        self.width_var      = tk.IntVar(value=1920)
        self.height_var     = tk.IntVar(value=1080)
        self.sort_var       = tk.StringVar(value="name")
        self.quality_var    = tk.IntVar(value=8)
        self.res_var        = tk.StringVar(value="1920 x 1080  (Full HD)")

        self.music_enabled_var   = tk.BooleanVar(value=False)
        self.music_folder_var    = tk.StringVar()
        self.music_sort_var      = tk.StringVar(value="name")
        self.music_trans_var     = tk.StringVar(value="crossfade")
        self.music_trans_dur_var = tk.DoubleVar(value=2.0)
        self.music_volume_var    = tk.DoubleVar(value=1.0)
        self.music_loop_var      = tk.BooleanVar(value=True)

        self.running       = False
        self._cancel_event = threading.Event()
        self._log_queue    = queue.Queue()
        self._music_widgets = []

        self._build_ui()
        self._update_quality_label()
        self._update_volume_label()
        self._toggle_music_widgets()
        self._poll_log_queue()  # Startet den Queue-Poller

    # ── Queue-Logging (thread-sicher) ─────────────────────────────────────────

    def _poll_log_queue(self):
        """Liest Nachrichten aus dem Worker-Thread und schreibt sie ins Log-Widget."""
        try:
            while True:
                text, tag = self._log_queue.get_nowait()
                self._log(text, tag)
        except queue.Empty:
            pass
        self.root.after(40, self._poll_log_queue)

    def _queue_log(self, text: str, tag: str = ""):
        """Wird aus dem Worker-Thread aufgerufen – thread-sicher."""
        self._log_queue.put((text, tag))

    def _queue_log_auto(self, text: str):
        """Automatische Tag-Erkennung fuer den Worker-Thread."""
        if any(k in text for k in ("Fertig", "gespeichert")):
            tag = "success"
        elif any(k in text for k in ("Fehler", "Error", "Warnung")):
            tag = "error"
        elif any(k in text for k in ("Musik", "Audio", "Audioverarbeitung",
                                      "Zusammenfuehren", "Loop")):
            tag = "music"
        elif text.startswith("  ["):
            tag = "accent"
        elif any(k in text for k in ("Ausgabe:", "gefunden", "Videolaenge")):
            tag = "dim"
        else:
            tag = ""
        self._log_queue.put((text, tag))

    # ── Hilfsmethoden ──────────────────────────────────────────────────────────

    def _card(self, parent, **kw):
        return tk.Frame(parent, bg=SURFACE, relief="flat", **kw)

    def _label(self, parent, text, dim=False, color=None, **kw):
        fg = color if color else (TEXT_DIM if dim else TEXT)
        return tk.Label(parent, text=text, bg=parent["bg"], fg=fg,
                        font=FONT_LABEL, **kw)

    def _section_label(self, parent, text, color=TEXT_DIM):
        return tk.Label(parent, text=text.upper(), bg=parent["bg"], fg=color,
                        font=("Segoe UI", 8, "bold"), anchor="w")

    def _entry(self, parent, textvariable, width=18):
        return tk.Entry(
            parent, textvariable=textvariable,
            bg=SURFACE2, fg=TEXT, insertbackground=TEXT,
            relief="flat", font=FONT_LABEL, width=width,
            highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT,
        )

    def _spinbox(self, parent, textvariable, from_, to, increment=1,
                 width=7, fmt=None):
        kw = dict(
            textvariable=textvariable,
            from_=from_, to=to, increment=increment,
            bg=SURFACE2, fg=TEXT, insertbackground=TEXT, buttonbackground=SURFACE2,
            relief="flat", font=FONT_LABEL, width=width,
            highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT,
        )
        if fmt:
            kw["format"] = fmt
        return tk.Spinbox(parent, **kw)

    def _browse_btn(self, parent, command, text="Durchsuchen"):
        btn = tk.Button(
            parent, text=text, command=command,
            bg=SURFACE2, fg=TEXT, activebackground=BORDER, activeforeground=TEXT,
            relief="flat", cursor="hand2", font=FONT_LABEL, padx=10, pady=4,
            highlightthickness=0,
        )
        self._hover(btn, BORDER, SURFACE2)
        return btn

    def _option_menu(self, parent, variable, *values,
                     accent=ACCENT, width=14, command=None):
        om = tk.OptionMenu(parent, variable, *values, command=command)
        om.config(bg=SURFACE2, fg=TEXT, activebackground=BORDER, activeforeground=TEXT,
                  relief="flat", highlightthickness=0, font=FONT_LABEL, width=width)
        om["menu"].config(bg=SURFACE2, fg=TEXT, activebackground=accent,
                          activeforeground=BTN_FG, relief="flat")
        return om

    def _separator(self, parent):
        return tk.Frame(parent, bg=BORDER, height=1)

    def _hover(self, widget, on, off):
        widget.bind("<Enter>", lambda _: widget.config(bg=on))
        widget.bind("<Leave>", lambda _: widget.config(bg=off))

    # ── UI aufbauen ────────────────────────────────────────────────────────────

    def _build_ui(self):
        header = tk.Frame(self.root, bg=SURFACE, pady=16)
        header.pack(fill="x")
        tk.Label(header, text="Slideshow Generator",
                 bg=SURFACE, fg=TEXT, font=FONT_TITLE).pack(side="left", padx=24)

        canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        sb = tk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=BG)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        inner.bind("<Configure>", lambda _: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1 * e.delta / 120), "units"))

        self._build_input_card(inner)
        self._build_settings_card(inner)
        self._build_music_card(inner)
        self._build_generate_btn(inner)
        self._build_log_card(inner)

    # ── Karte: Eingabe ──────────────────────────────────────────────────────────

    def _build_input_card(self, parent):
        card = self._card(parent)
        card.pack(fill="x", padx=16, pady=(16, 0))
        self._section_label(card, "Eingabe").pack(anchor="w", padx=16, pady=(12, 0))

        for label, var, cmd in [
            ("Bildordner *", self.folder_var, self._browse_folder),
            ("Ausgabedatei", self.output_var, self._browse_output),
        ]:
            lbl_row = tk.Frame(card, bg=SURFACE)
            lbl_row.pack(fill="x", padx=16,
                         pady=(8 if label.startswith("Bild") else 4, 0))
            self._label(lbl_row, label).pack(side="left")
            entry_row = tk.Frame(card, bg=SURFACE)
            entry_row.pack(fill="x", padx=16,
                           pady=(2, 0 if label.startswith("Bild") else 12))
            self._entry(entry_row, var, width=50).pack(
                side="left", fill="x", expand=True, ipady=5)
            self._browse_btn(entry_row, cmd).pack(side="left", padx=(6, 0))

    # ── Karte: Einstellungen ────────────────────────────────────────────────────

    def _build_settings_card(self, parent):
        card = self._card(parent)
        card.pack(fill="x", padx=16, pady=(10, 0))
        self._section_label(card, "Einstellungen").pack(anchor="w", padx=16,
                                                         pady=(12, 4))

        grid = tk.Frame(card, bg=SURFACE)
        grid.pack(fill="x", padx=16, pady=(0, 4))

        def pair(row, l1, w1, l2, w2):
            self._label(grid, l1).grid(row=row, column=0, sticky="w",
                                        pady=5, padx=(0, 8))
            w1.grid(row=row, column=1, sticky="w", pady=5, padx=(0, 24))
            self._label(grid, l2).grid(row=row, column=2, sticky="w",
                                        pady=5, padx=(0, 8))
            w2.grid(row=row, column=3, sticky="w", pady=5)

        pair(0,
             "Dauer pro Bild (s):",
             self._spinbox(grid, self.duration_var, 0.5, 30.0, 0.5, fmt="%.1f"),
             "Uebergangsdauer (s):",
             self._spinbox(grid, self.transition_var, 0.1, 10.0, 0.1, fmt="%.1f"))
        pair(1,
             "FPS:",
             self._spinbox(grid, self.fps_var, 10, 60, 5),
             "Sortierung:",
             self._option_menu(grid, self.sort_var, "name", "date", "random", width=8))

        self._separator(card).pack(fill="x", padx=16, pady=(4, 8))

        res_row = tk.Frame(card, bg=SURFACE)
        res_row.pack(fill="x", padx=16, pady=(0, 4))
        self._label(res_row, "Aufloesung:").pack(side="left", padx=(0, 8))
        self._option_menu(res_row, self.res_var, *RESOLUTIONS.keys(),
                          width=30, command=self._on_res_change).pack(side="left")

        custom_row = tk.Frame(card, bg=SURFACE)
        custom_row.pack(fill="x", padx=16, pady=(2, 10))
        self._label(custom_row, "Breite (px):").pack(side="left", padx=(0, 4))
        self.sb_w = self._spinbox(custom_row, self.width_var, 120, 7680, 2, width=6)
        self.sb_w.pack(side="left", padx=(0, 16))
        self._label(custom_row, "Hoehe (px):").pack(side="left", padx=(0, 4))
        self.sb_h = self._spinbox(custom_row, self.height_var, 120, 4320, 2, width=6)
        self.sb_h.pack(side="left")
        self._update_res_fields()

        self._separator(card).pack(fill="x", padx=16, pady=(0, 8))

        q_row = tk.Frame(card, bg=SURFACE)
        q_row.pack(fill="x", padx=16, pady=(0, 14))
        self._label(q_row, "Videoqualitaet:").pack(side="left", padx=(0, 10))
        tk.Scale(q_row, variable=self.quality_var, from_=1, to=10,
                 orient="horizontal", length=240,
                 command=lambda _: self._update_quality_label(),
                 bg=SURFACE, fg=TEXT, troughcolor=SURFACE2, activebackground=ACCENT,
                 highlightthickness=0, sliderlength=22, showvalue=False,
                 relief="flat").pack(side="left")
        self.quality_lbl = tk.Label(q_row, text="", bg=SURFACE, fg=ACCENT,
                                    font=("Segoe UI", 10, "bold"), width=16)
        self.quality_lbl.pack(side="left", padx=(10, 0))

    # ── Karte: Musik ───────────────────────────────────────────────────────────

    def _build_music_card(self, parent):
        card = self._card(parent)
        card.pack(fill="x", padx=16, pady=(10, 0))

        hdr = tk.Frame(card, bg=SURFACE)
        hdr.pack(fill="x", padx=16, pady=(10, 0))
        self._section_label(hdr, "Musik", color=MUSIC_ACC).pack(side="left")
        tk.Checkbutton(
            hdr, text="Musik hinzufuegen",
            variable=self.music_enabled_var,
            command=self._toggle_music_widgets,
            bg=SURFACE, fg=TEXT, selectcolor=SURFACE2,
            activebackground=SURFACE, activeforeground=TEXT,
            font=FONT_LABEL, cursor="hand2", highlightthickness=0,
        ).pack(side="left", padx=(12, 0))

        self._music_widgets.clear()

        def mw(w):
            self._music_widgets.append(w)
            return w

        sep = mw(self._separator(card))
        sep.pack(fill="x", padx=16, pady=(8, 0))

        lbl_row = mw(tk.Frame(card, bg=SURFACE))
        lbl_row.pack(fill="x", padx=16, pady=(8, 0))
        mw(self._label(lbl_row, "Musikordner:")).pack(side="left")

        entry_row = mw(tk.Frame(card, bg=SURFACE))
        entry_row.pack(fill="x", padx=16, pady=(2, 0))
        e_music = mw(self._entry(entry_row, self.music_folder_var, width=50))
        e_music.pack(side="left", fill="x", expand=True, ipady=5)
        btn_mf = mw(self._browse_btn(entry_row, self._browse_music_folder))
        btn_mf.pack(side="left", padx=(6, 0))

        grid = mw(tk.Frame(card, bg=SURFACE))
        grid.pack(fill="x", padx=16, pady=(10, 0))

        def m_pair(row, l1, w1, l2, w2):
            mw(self._label(grid, l1)).grid(row=row, column=0, sticky="w",
                                            pady=5, padx=(0, 8))
            mw(w1).grid(row=row, column=1, sticky="w", pady=5, padx=(0, 24))
            mw(self._label(grid, l2)).grid(row=row, column=2, sticky="w",
                                            pady=5, padx=(0, 8))
            mw(w2).grid(row=row, column=3, sticky="w", pady=5)

        m_pair(0,
               "Sortierung:",
               self._option_menu(grid, self.music_sort_var,
                                  "name", "date", "random", width=8),
               "Uebergangstyp:",
               self._option_menu(grid, self.music_trans_var,
                                  *MUSIC_TRANSITIONS.keys(),
                                  accent=MUSIC_ACC, width=14))
        m_pair(1,
               "Uebergangsdauer (s):",
               self._spinbox(grid, self.music_trans_dur_var,
                              0.1, 15.0, 0.1, fmt="%.1f"),
               "", tk.Frame(grid, bg=SURFACE))

        vol_row = mw(tk.Frame(card, bg=SURFACE))
        vol_row.pack(fill="x", padx=16, pady=(4, 0))
        mw(self._label(vol_row, "Lautstaerke:")).pack(side="left", padx=(0, 10))
        mw(tk.Scale(
            vol_row, variable=self.music_volume_var,
            from_=0.0, to=2.0, resolution=0.05,
            orient="horizontal", length=200,
            command=lambda _: self._update_volume_label(),
            bg=SURFACE, fg=TEXT, troughcolor=SURFACE2, activebackground=MUSIC_ACC,
            highlightthickness=0, sliderlength=22, showvalue=False, relief="flat",
        )).pack(side="left")
        self.vol_lbl = mw(tk.Label(vol_row, text="", bg=SURFACE, fg=MUSIC_ACC,
                                   font=("Segoe UI", 10, "bold"), width=8))
        self.vol_lbl.pack(side="left", padx=(10, 0))

        loop_row = mw(tk.Frame(card, bg=SURFACE))
        loop_row.pack(fill="x", padx=16, pady=(6, 0))
        mw(tk.Checkbutton(
            loop_row,
            text="Musik endlos wiederholen (Loop) bis Videolaenge erreicht",
            variable=self.music_loop_var,
            bg=SURFACE, fg=TEXT, selectcolor=SURFACE2,
            activebackground=SURFACE, activeforeground=TEXT,
            font=FONT_LABEL, cursor="hand2", highlightthickness=0,
        )).pack(side="left")

        note_row = mw(tk.Frame(card, bg=SURFACE))
        note_row.pack(fill="x", padx=16, pady=(4, 14))
        mw(self._label(
            note_row,
            "Unterstuetzte Formate: MP3, WAV, FLAC, AAC, M4A, OGG, OPUS, WMA",
            dim=True,
        )).pack(side="left")

    # ── Generate-Button ─────────────────────────────────────────────────────────

    def _build_generate_btn(self, parent):
        frame = tk.Frame(parent, bg=BG)
        frame.pack(fill="x", padx=16, pady=14)

        self.generate_btn = tk.Button(
            frame, text="   Slideshow generieren",
            command=self._start_generation,
            bg=ACCENT, fg=BTN_FG,
            activebackground=ACCENT_H, activeforeground=BTN_FG,
            font=FONT_BTN, relief="flat",
            padx=0, pady=12, cursor="hand2", highlightthickness=0,
        )
        self.generate_btn.pack(fill="x")
        self._hover(self.generate_btn, ACCENT_H, ACCENT)

        self.stop_btn = tk.Button(
            frame, text="Abbrechen",
            command=self._stop_generation,
            bg=SURFACE2, fg=ERROR,
            activebackground=BORDER, activeforeground=ERROR,
            font=FONT_LABEL, relief="flat",
            padx=0, pady=6, cursor="hand2", highlightthickness=0,
        )
        self.stop_btn.pack(fill="x", pady=(6, 0))

    # ── Log-Karte ──────────────────────────────────────────────────────────────

    def _build_log_card(self, parent):
        card = self._card(parent)
        card.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        hdr = tk.Frame(card, bg=SURFACE)
        hdr.pack(fill="x", padx=16, pady=(10, 0))
        self._section_label(hdr, "Ausgabe").pack(side="left")
        tk.Button(
            hdr, text="Leeren", command=self._clear_log,
            bg=SURFACE, fg=TEXT_DIM, activebackground=BORDER, activeforeground=TEXT,
            relief="flat", font=("Segoe UI", 8), cursor="hand2",
            highlightthickness=0, padx=6, pady=2,
        ).pack(side="right")

        self.log_text = tk.Text(
            card, bg="#0e0e1a", fg=TEXT,
            insertbackground=TEXT, font=FONT_MONO,
            relief="flat", wrap="word", state="disabled",
            height=14, padx=12, pady=8, highlightthickness=0,
        )
        self.log_text.pack(fill="both", expand=True, padx=16, pady=(6, 16))

        for tag, color in [
            ("success", SUCCESS), ("error", ERROR), ("warning", WARNING),
            ("dim", TEXT_DIM), ("accent", ACCENT), ("music", MUSIC_ACC),
        ]:
            self.log_text.tag_config(tag, foreground=color)

    # ── Steuerlogik ────────────────────────────────────────────────────────────

    def _toggle_music_widgets(self):
        state = "normal" if self.music_enabled_var.get() else "disabled"
        for w in self._music_widgets:
            try:
                w.config(state=state)
            except tk.TclError:
                pass

    def _on_res_change(self, value=None):
        dims = RESOLUTIONS.get(self.res_var.get())
        if dims:
            self.width_var.set(dims[0])
            self.height_var.set(dims[1])
        self._update_res_fields()

    def _update_res_fields(self):
        is_custom = RESOLUTIONS.get(self.res_var.get()) is None
        self.sb_w.config(state="normal" if is_custom else "disabled")
        self.sb_h.config(state="normal" if is_custom else "disabled")

    def _update_quality_label(self):
        labels = {
            1: "1 - sehr niedrig", 2: "2 - niedrig", 3: "3 - niedrig",
            4: "4 - mittel",       5: "5 - mittel",   6: "6 - gut",
            7: "7 - gut",          8: "8 - hoch",      9: "9 - sehr hoch",
            10: "10 - maximal",
        }
        self.quality_lbl.config(text=labels.get(self.quality_var.get(), ""))

    def _update_volume_label(self):
        self.vol_lbl.config(text=f"{int(round(self.music_volume_var.get()*100))} %")

    # ── Datei-Dialoge ──────────────────────────────────────────────────────────

    def _browse_folder(self):
        d = filedialog.askdirectory(title="Bildordner waehlen")
        if d:
            self.folder_var.set(d)
            if self.output_var.get() == "slideshow.mp4":
                self.output_var.set(os.path.join(d, "slideshow.mp4"))

    def _browse_output(self):
        f = filedialog.asksaveasfilename(
            title="Ausgabedatei speichern als",
            defaultextension=".mp4",
            filetypes=[("MP4-Video", "*.mp4"), ("Alle Dateien", "*.*")],
        )
        if f:
            self.output_var.set(f)

    def _browse_music_folder(self):
        d = filedialog.askdirectory(title="Musikordner waehlen")
        if d:
            self.music_folder_var.set(d)

    # ── Generierung ────────────────────────────────────────────────────────────

    def _start_generation(self):
        if self.running:
            return

        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            self._log(f"Kein gueltiger Bildordner: {folder}", "error")
            return
        if not self.output_var.get().strip():
            self._log("Kein Ausgabepfad angegeben.", "error")
            return
        if self.music_enabled_var.get():
            mf = self.music_folder_var.get().strip()
            if not mf or not os.path.isdir(mf):
                self._log(f"Musik aktiviert, aber kein gueltiger Musikordner: {mf}", "error")
                return

        self._cancel_event.clear()
        self.running = True
        self.generate_btn.config(state="disabled", text="  Wird generiert ...")
        self._log("─" * 60, "dim")
        self._log("Starte Slideshow-Generierung ...", "accent")

        threading.Thread(target=self._run_worker, daemon=True).start()

    def _run_worker(self):
        """Laeuft im Worker-Thread. Kommuniziert via self._log_queue."""
        args = argparse.Namespace(
            folder     = self.folder_var.get(),
            output     = self.output_var.get(),
            duration   = self.duration_var.get(),
            transition = self.transition_var.get(),
            fps        = self.fps_var.get(),
            width      = self.width_var.get(),
            height     = self.height_var.get(),
            sort       = self.sort_var.get(),
            quality    = self.quality_var.get(),
            music_folder             = self.music_folder_var.get() if self.music_enabled_var.get() else None,
            music_sort               = self.music_sort_var.get(),
            music_transition         = self.music_trans_var.get(),
            music_transition_duration= self.music_trans_dur_var.get(),
            music_volume             = self.music_volume_var.get(),
            music_loop               = self.music_loop_var.get(),
        )

        try:
            ok = create_slideshow.run(
                args,
                log=self._queue_log_auto,
                cancel_event=self._cancel_event,
            )
        except RuntimeError as e:
            self._queue_log(f"Fehler: {e}", "error")
            ok = False
        except Exception as e:
            self._queue_log(f"Unerwarteter Fehler: {e}", "error")
            ok = False

        if ok:
            self._queue_log("Fertig! Video erfolgreich gespeichert.", "success")
            self._queue_log(self.output_var.get(), "dim")
        elif not self._cancel_event.is_set():
            self._queue_log("Generierung fehlgeschlagen.", "error")

        self.root.after(0, self._generation_done)

    def _generation_done(self):
        self.running = False
        self.generate_btn.config(state="normal", text="   Slideshow generieren")

    def _stop_generation(self):
        if self.running:
            self._cancel_event.set()
            self._log("Abbruch wird ausgefuehrt ...", "warning")

    # ── Logging ────────────────────────────────────────────────────────────────

    def _log(self, text: str, tag: str = ""):
        self.log_text.config(state="normal")
        if tag:
            self.log_text.insert("end", text + "\n", tag)
        else:
            self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")


def main():
    root = tk.Tk()
    SlideshowGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
