# =============================================================================
# FILE: dashboard.py
#
# HOW TO RUN (Mac):
#   /opt/homebrew/bin/python3.12 dashboard.py
#   A native Mac window opens immediately. No browser. No server.
#
# DESIGN: Clean Scientific — White + Blue
# =============================================================================

import tkinter as tk
from tkinter import ttk
import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from database import initialise_database, get_all_proteins, get_scaffolds

# ── Colour palette ────────────────────────────────────────────────────────────
C = {
    "bg":           "#FFFFFF",
    "sidebar":      "#F0F4FF",
    "blue":         "#1A6BCC",
    "blue_light":   "#E8F0FE",
    "blue_mid":     "#4A90D9",
    "blue_dark":    "#0E4A99",
    "text":         "#0D1B2A",
    "muted":        "#6B7A99",
    "border":       "#D6E2F8",
    "green":        "#1A8754",
    "green_bg":     "#D1FAE5",
    "amber":        "#B45309",
    "amber_bg":     "#FEF3C7",
    "white":        "#FFFFFF",
    "row_alt":      "#F7F9FF",
    "hover":        "#DCE8FC",
    "selected":     "#1A6BCC",
    "selected_txt": "#FFFFFF",
}

F = {
    "title":   ("Georgia", 22, "bold"),
    "heading": ("Georgia", 15, "bold"),
    "subhead": ("Georgia", 12, "italic"),
    "body":    ("Helvetica Neue", 11),
    "body_b":  ("Helvetica Neue", 11, "bold"),
    "small":   ("Helvetica Neue", 10),
    "mono":    ("Courier New", 11),
    "mono_lg": ("Courier New", 16, "bold"),
    "label":   ("Helvetica Neue", 9),
    "nav":     ("Helvetica Neue", 12),
}


# =============================================================================
# HELPER WIDGETS
# =============================================================================

def hline(parent, color=None, pady=6):
    color = color or C["border"]
    tk.Frame(parent, height=1, bg=color).pack(fill="x", padx=20, pady=pady)


def chip(parent, text, fg=None, bg=None):
    fg = fg or C["blue"]
    bg = bg or C["blue_light"]
    return tk.Label(parent, text=f"  {text}  ", font=F["label"],
                    fg=fg, bg=bg, padx=2, pady=2, relief="flat")


def animate_count(widget, target: float, duration_ms=900,
                  suffix="", decimals=0, prefix=""):
    """
    Animates a label counting up from 0 → target using an ease-out curve.
    Uses only Tkinter's .after() — no extra libraries.
    """
    steps    = 40
    interval = duration_ms // steps

    def step(i):
        progress = (i / steps) ** 0.45
        current  = target * progress
        fmt = f"{prefix}{current:,.{decimals}f}{suffix}"
        widget.config(text=fmt)
        if i < steps:
            widget.after(interval, step, i + 1)
        else:
            widget.config(text=f"{prefix}{target:,.{decimals}f}{suffix}")

    step(0)


# =============================================================================
# MAIN APPLICATION
# =============================================================================

class BioAnalystApp(tk.Tk):
    """
    Layout:
      ┌──────────┬──────────────────────────────────────────┐
      │          │  Header bar                              │
      │ Sidebar  ├──────────────────────────────────────────┤
      │ (protein │  Detail panel (scrollable)               │
      │  list)   │  • Protein profile (like Section 9)      │
      │          │  • Scaffold cards (3 proposals)          │
      └──────────┴──────────────────────────────────────────┘
    """

    def __init__(self):
        super().__init__()
        initialise_database()
        self.proteins       = []
        self.selected_index = None
        self._pulse_state   = True

        self._build_window()
        self._build_layout()
        self._build_sidebar()
        self._build_main()
        self._build_statusbar()

        # Fade the window in from invisible
        self.attributes("-alpha", 0.0)
        self._fade_in(0)

        self._refresh_proteins()
        self._start_pulse()

    # ── Window ────────────────────────────────────────────────────────────────

    def _build_window(self):
        self.title("Bio-Analyst Agent  ·  Drug Discovery Dashboard")
        self.geometry("1180x750")
        self.minsize(900, 580)
        self.configure(bg=C["bg"])
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - 1180) // 2
        y = (self.winfo_screenheight() -  750) // 2
        self.geometry(f"1180x750+{x}+{y}")

    # ── Master layout ─────────────────────────────────────────────────────────

    def _build_layout(self):
        self.outer = tk.Frame(self, bg=C["bg"])
        self.outer.pack(fill="both", expand=True)

        self.sidebar_frame = tk.Frame(self.outer, bg=C["sidebar"], width=270)
        self.sidebar_frame.pack(side="left", fill="y")
        self.sidebar_frame.pack_propagate(False)

        self.right = tk.Frame(self.outer, bg=C["bg"])
        self.right.pack(side="left", fill="both", expand=True)

        tk.Frame(self.outer, width=1, bg=C["border"]).place(x=270, y=0, relheight=1.0)

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self):
        header = tk.Frame(self.sidebar_frame, bg=C["blue"], height=64)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🧬  Bio-Analyst",
                 font=("Georgia", 14, "bold"),
                 fg=C["white"], bg=C["blue"],
                 anchor="w", padx=18).pack(fill="both", expand=True)

        tk.Label(self.sidebar_frame, text="PROTEIN TARGETS",
                 font=("Helvetica Neue", 9, "bold"),
                 fg=C["muted"], bg=C["sidebar"],
                 anchor="w", padx=18, pady=8).pack(fill="x")

        hline(self.sidebar_frame, pady=0)

        list_outer = tk.Frame(self.sidebar_frame, bg=C["sidebar"])
        list_outer.pack(fill="both", expand=True, pady=(4, 0))

        canvas = tk.Canvas(list_outer, bg=C["sidebar"],
                           highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(list_outer, orient="vertical",
                                 command=canvas.yview)
        self.list_frame = tk.Frame(canvas, bg=C["sidebar"])
        self.list_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        hline(self.sidebar_frame, pady=4)
        tk.Button(self.sidebar_frame, text="⟳  Refresh",
                  font=F["small"], fg=C["blue"], bg=C["sidebar"],
                  activeforeground=C["white"], activebackground=C["blue"],
                  relief="flat", bd=0, cursor="hand2", pady=8,
                  command=self._refresh_proteins).pack(fill="x", padx=12, pady=(0, 8))

    # ── Main panel ────────────────────────────────────────────────────────────

    def _build_main(self):
        self.main_header = tk.Frame(self.right, bg=C["bg"], height=64)
        self.main_header.pack(fill="x")
        self.main_header.pack_propagate(False)

        self.title_lbl = tk.Label(self.main_header,
                                  text="Select a protein target →",
                                  font=F["heading"], fg=C["muted"], bg=C["bg"],
                                  anchor="w", padx=28)
        self.title_lbl.pack(side="left", fill="both", expand=True)

        self.date_lbl = tk.Label(self.main_header, text="",
                                 font=F["small"], fg=C["muted"], bg=C["bg"],
                                 anchor="e", padx=24)
        self.date_lbl.pack(side="right")

        hline(self.right, pady=0)

        detail_outer = tk.Frame(self.right, bg=C["bg"])
        detail_outer.pack(fill="both", expand=True)

        self.detail_canvas = tk.Canvas(detail_outer, bg=C["bg"],
                                       highlightthickness=0, bd=0)
        vbar = tk.Scrollbar(detail_outer, orient="vertical",
                            command=self.detail_canvas.yview)
        self.detail_frame = tk.Frame(self.detail_canvas, bg=C["bg"])
        self.detail_frame.bind(
            "<Configure>",
            lambda e: self.detail_canvas.configure(
                scrollregion=self.detail_canvas.bbox("all")))
        self.detail_canvas.create_window((0, 0), window=self.detail_frame,
                                         anchor="nw")
        self.detail_canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side="right", fill="y")
        self.detail_canvas.pack(side="left", fill="both", expand=True)

        self.detail_canvas.bind_all(
            "<MouseWheel>",
            lambda e: self.detail_canvas.yview_scroll(-1*(e.delta//120), "units"))

        self.empty_lbl = tk.Label(
            self.detail_frame,
            text=("No proteins in the database yet.\n\n"
                  "Seed sample data first:\n"
                  "  python database.py\n\n"
                  "Or run the full pipeline:\n"
                  "  python bio_analyst_agent.py"),
            font=F["body"], fg=C["muted"], bg=C["bg"], justify="center")

    def _build_statusbar(self):
        bar = tk.Frame(self.right, bg=C["sidebar"], height=26)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self.status_dot = tk.Label(bar, text="●",
                                   font=("Helvetica Neue", 10),
                                   fg=C["blue"], bg=C["sidebar"])
        self.status_dot.pack(side="left", padx=(12, 0))

        tk.Label(bar, text="bio_research.db  ·  Bio-Analyst Agent",
                 font=("Helvetica Neue", 9),
                 fg=C["muted"], bg=C["sidebar"]).pack(side="left", padx=4)

        self.count_lbl = tk.Label(bar, text="",
                                  font=("Helvetica Neue", 9),
                                  fg=C["muted"], bg=C["sidebar"])
        self.count_lbl.pack(side="right", padx=12)

    # ── Animations ────────────────────────────────────────────────────────────

    def _fade_in(self, step):
        """Window alpha 0 → 1 over ~300 ms."""
        self.attributes("-alpha", min(step / 20.0, 1.0))
        if step < 20:
            self.after(15, self._fade_in, step + 1)

    def _start_pulse(self):
        """Status dot alternates between two blues every 900 ms."""
        self._pulse_state = not self._pulse_state
        color = C["blue"] if self._pulse_state else C["blue_mid"]
        if self.status_dot.winfo_exists():
            self.status_dot.config(fg=color)
        self.after(900, self._start_pulse)

    # ── Data ──────────────────────────────────────────────────────────────────

    def _refresh_proteins(self):
        self.proteins = get_all_proteins()
        self._rebuild_list()
        self.count_lbl.config(text=f"{len(self.proteins)} protein(s)")
        if self.proteins and self.selected_index is None:
            self._select_protein(0)

    def _rebuild_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        if not self.proteins:
            tk.Label(self.list_frame,
                     text="No proteins yet.\nRun the pipeline first.",
                     font=F["small"], fg=C["muted"], bg=C["sidebar"],
                     justify="left", padx=18, pady=12).pack(anchor="w")
            self.empty_lbl.pack(pady=80)
            return
        self.empty_lbl.pack_forget()
        for i, p in enumerate(self.proteins):
            self._make_list_item(i, p)

    def _make_list_item(self, idx: int, p: dict):
        is_sel = (idx == self.selected_index)
        bg  = C["selected"] if is_sel else C["sidebar"]
        fg  = C["selected_txt"] if is_sel else C["text"]
        fg2 = C["selected_txt"] if is_sel else C["muted"]

        row = tk.Frame(self.list_frame, bg=bg, cursor="hand2")
        row.pack(fill="x", padx=8, pady=2)

        short = p.get("target_description", p.get("accession_id", "Unknown"))
        if len(short) > 30:
            short = short[:28] + "…"

        tk.Label(row, text=short, font=F["nav"],
                 fg=fg, bg=bg, anchor="w", padx=12, pady=6).pack(fill="x")
        tk.Label(row, text=p.get("accession_id", ""),
                 font=F["label"], fg=fg2, bg=bg,
                 anchor="w", padx=14, pady=0).pack(fill="x")
        tk.Frame(row, height=1, bg=C["border"]).pack(fill="x", padx=8, pady=(4, 0))

        def on_click(e, i=idx): self._select_protein(i)
        def on_enter(e, r=row, i=idx):
            if i != self.selected_index:
                r.config(bg=C["hover"])
                for c in r.winfo_children(): c.config(bg=C["hover"])
        def on_leave(e, r=row, i=idx):
            if i != self.selected_index:
                r.config(bg=C["sidebar"])
                for c in r.winfo_children(): c.config(bg=C["sidebar"])

        for w in [row] + list(row.winfo_children()):
            w.bind("<Button-1>", on_click)
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)

    def _select_protein(self, idx: int):
        self.selected_index = idx
        self._rebuild_list()
        p         = self.proteins[idx]
        scaffolds = get_scaffolds(p["accession_id"])

        self.title_lbl.config(
            text=p.get("target_description", p.get("accession_id", "")),
            fg=C["text"])
        self.date_lbl.config(
            text=f"Analysed: {p.get('run_date', '—')}  ·  Model: {p.get('ai_model_used', '—')}")

        for w in self.detail_frame.winfo_children():
            w.destroy()
        self.detail_canvas.yview_moveto(0)
        self._build_detail(p, scaffolds)

    # ── Detail panel ──────────────────────────────────────────────────────────

    def _build_detail(self, p: dict, scaffolds: list):
        pad = {"padx": 28, "pady": 0}

        # Accession + protein name
        top = tk.Frame(self.detail_frame, bg=C["bg"])
        top.pack(fill="x", **pad, pady=(20, 4))
        tk.Label(top, text=p.get("accession_id", "—"),
                 font=("Courier New", 11, "bold"),
                 fg=C["blue"], bg=C["bg"], anchor="w").pack(anchor="w")
        tk.Label(top,
                 text=p.get("protein_name", p.get("target_description", ""))[:90],
                 font=F["subhead"], fg=C["muted"], bg=C["bg"],
                 anchor="w").pack(anchor="w")

        hline(self.detail_frame, pady=10)

        # Metric tiles with count-up animation
        tiles_row = tk.Frame(self.detail_frame, bg=C["bg"])
        tiles_row.pack(fill="x", padx=28, pady=(0, 16))

        mw_val  = float(p.get("molecular_weight_da", 0) or 0)
        pi_val  = float(p.get("isoelectric_point", 0)   or 0)
        len_val = float(p.get("sequence_length", 0)      or 0)

        mw_lbl  = self._metric_tile(tiles_row, "Molecular Weight",    "0 Da",  C["blue"])
        pi_lbl  = self._metric_tile(tiles_row, "Isoelectric Point (pI)", "0.00", C["blue"])
        len_lbl = self._metric_tile(tiles_row, "Sequence Length",     "0 AA",  C["blue"])

        self.after(100, lambda: animate_count(mw_lbl,  mw_val,  suffix=" Da", decimals=0))
        self.after(200, lambda: animate_count(pi_lbl,  pi_val,  suffix="",    decimals=2))
        self.after(300, lambda: animate_count(len_lbl, len_val, suffix=" AA", decimals=0))

        # Charge note
        charge = ("Negatively charged at pH 7.4  (pI < 7.4)"
                  if pi_val < 7.4 else
                  "Positively charged at pH 7.4  (pI > 7.4)")
        tk.Label(self.detail_frame, text=charge,
                 font=F["small"], fg=C["muted"], bg=C["bg"],
                 anchor="w").pack(anchor="w", padx=28, pady=(0, 12))

        # 2 × 2 science fields grid
        grid = tk.Frame(self.detail_frame, bg=C["bg"])
        grid.pack(fill="x", padx=28, pady=(0, 12))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        fields = [
            ("Disease Link",            p.get("disease_link",            "—"), 0, 0),
            ("Binding Site Residues",   p.get("binding_site_residues",   "—"), 0, 1),
            ("Known Inhibitor Classes", p.get("known_inhibitor_classes", "—"), 1, 0),
            ("ADMET Concerns",          p.get("admet_concerns",          "—"), 1, 1),
        ]
        for title, content, row, col in fields:
            cell = tk.Frame(grid, bg=C["blue_light"],
                            highlightbackground=C["border"], highlightthickness=1)
            cell.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            tk.Label(cell, text=title.upper(),
                     font=("Helvetica Neue", 8, "bold"),
                     fg=C["blue"], bg=C["blue_light"],
                     anchor="w", padx=12, pady=(8, 2)).pack(fill="x")
            tk.Label(cell, text=(content or "—")[:260],
                     font=F["small"], fg=C["text"], bg=C["blue_light"],
                     anchor="w", padx=12, pady=(2, 10),
                     wraplength=380, justify="left").pack(fill="x")

        # Amino acid chips
        aa_raw = p.get("top_5_amino_acids", "")
        if aa_raw:
            aa_frame = tk.Frame(self.detail_frame, bg=C["bg"])
            aa_frame.pack(fill="x", padx=28, pady=(4, 6))
            tk.Label(aa_frame, text="TOP AMINO ACIDS",
                     font=("Helvetica Neue", 8, "bold"),
                     fg=C["muted"], bg=C["bg"]).pack(side="left", padx=(0, 8))
            for aa in aa_raw.split(","):
                aa = aa.strip()
                if aa:
                    chip(aa_frame, aa).pack(side="left", padx=2)

        # Druggability banner
        drug = p.get("druggability_note", "")
        if drug:
            banner = tk.Frame(self.detail_frame, bg=C["green_bg"],
                              highlightbackground=C["green"], highlightthickness=1)
            banner.pack(fill="x", padx=28, pady=(8, 0))
            tk.Label(banner, text=f"✓  {drug}",
                     font=F["small"], fg=C["green"], bg=C["green_bg"],
                     anchor="w", padx=14, pady=8,
                     wraplength=700, justify="left").pack(fill="x")

        # Scaffold section
        hline(self.detail_frame, pady=14)
        tk.Label(self.detail_frame, text="Drug Scaffold Proposals",
                 font=("Georgia", 14, "bold"),
                 fg=C["text"], bg=C["bg"], anchor="w").pack(anchor="w", padx=28)
        tk.Label(self.detail_frame,
                 text=f"{len(scaffolds)} candidate scaffold(s)  ·  AI-generated",
                 font=F["small"], fg=C["muted"], bg=C["bg"],
                 anchor="w").pack(anchor="w", padx=28, pady=(2, 12))

        if scaffolds:
            for i, s in enumerate(scaffolds):
                self.after(i * 120, lambda sc=s, d=i: self._scaffold_card(sc, d))
        else:
            tk.Label(self.detail_frame, text="No scaffold data for this protein.",
                     font=F["small"], fg=C["muted"], bg=C["bg"],
                     anchor="w", padx=28).pack(anchor="w", pady=8)

        tk.Frame(self.detail_frame, bg=C["bg"], height=40).pack()

    def _metric_tile(self, parent, label_text, initial_value, accent):
        tile = tk.Frame(parent, bg=C["white"],
                        highlightbackground=C["border"], highlightthickness=1)
        tile.pack(side="left", expand=True, fill="x", padx=5)
        tk.Label(tile, text=label_text.upper(),
                 font=("Helvetica Neue", 8, "bold"),
                 fg=C["muted"], bg=C["white"],
                 anchor="w", padx=14, pady=(10, 2)).pack(fill="x")
        value_lbl = tk.Label(tile, text=initial_value,
                             font=F["mono_lg"], fg=accent, bg=C["white"],
                             anchor="w", padx=14, pady=(0, 12))
        value_lbl.pack(fill="x")
        return value_lbl

    def _scaffold_card(self, s: dict, index: int):
        card = tk.Frame(self.detail_frame, bg=C["white"],
                        highlightbackground=C["blue"], highlightthickness=2)
        card.pack(fill="x", padx=28, pady=6)

        tk.Label(card, text=f" {index + 1} ",
                 font=("Georgia", 13, "bold"),
                 fg=C["white"], bg=C["blue"],
                 padx=10, pady=6).pack(side="left", anchor="n", padx=(0, 12), pady=12)

        content = tk.Frame(card, bg=C["white"])
        content.pack(side="left", fill="both", expand=True, pady=10)

        tk.Label(content, text=s.get("scaffold_name", "Unknown Scaffold"),
                 font=("Georgia", 12, "bold"),
                 fg=C["blue_dark"], bg=C["white"], anchor="w").pack(anchor="w")

        mech = s.get("mechanism", "")
        if mech:
            chip(content, mech).pack(anchor="w", pady=(3, 6))

        data_row = tk.Frame(content, bg=C["white"])
        data_row.pack(fill="x", pady=(0, 6))

        def data_chip(parent, lbl, val, fg=C["text"]):
            f = tk.Frame(parent, bg=C["row_alt"],
                         highlightbackground=C["border"], highlightthickness=1)
            f.pack(side="left", padx=(0, 8))
            tk.Label(f, text=lbl, font=("Helvetica Neue", 8),
                     fg=C["muted"], bg=C["row_alt"], padx=8, pady=2).pack()
            tk.Label(f, text=str(val), font=("Courier New", 10, "bold"),
                     fg=fg, bg=C["row_alt"], padx=8, pady=2).pack()

        mw_val = s.get("estimated_mw_da", 0) or 0
        lp_val = s.get("predicted_logP", 0)  or 0
        admet  = s.get("admet_flag", "—")

        data_chip(data_row, "Est. MW (Da)", f"{float(mw_val):.0f}")
        data_chip(data_row, "Pred. logP",   f"{float(lp_val):.1f}")

        admet_frame = tk.Frame(data_row, bg=C["amber_bg"],
                               highlightbackground=C["amber"], highlightthickness=1)
        admet_frame.pack(side="left")
        tk.Label(admet_frame, text="ADMET",
                 font=("Helvetica Neue", 8),
                 fg=C["amber"], bg=C["amber_bg"], padx=8, pady=2).pack()
        tk.Label(admet_frame, text=(admet or "—")[:35],
                 font=("Helvetica Neue", 9),
                 fg=C["amber"], bg=C["amber_bg"], padx=8, pady=2).pack()

        res = s.get("target_residues", "")
        if res:
            tk.Label(content, text=f"Targets:  {res}",
                     font=F["small"], fg=C["text"], bg=C["white"],
                     anchor="w").pack(anchor="w", pady=(2, 0))

        note = s.get("optimisation_note", "")
        if note:
            note_frame = tk.Frame(content, bg=C["blue_light"],
                                  highlightbackground=C["border"], highlightthickness=1)
            note_frame.pack(fill="x", pady=(6, 4), padx=(0, 16))
            tk.Label(note_frame,
                     text=f"Optimisation →  {note[:180]}",
                     font=F["small"], fg=C["blue_dark"], bg=C["blue_light"],
                     anchor="w", padx=10, pady=6,
                     wraplength=560, justify="left").pack(fill="x")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    app = BioAnalystApp()
    app.mainloop()
