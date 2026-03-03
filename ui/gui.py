# =============================================================================
# FILE: gui.py
# PURPOSE: Tkinter GUI to browse Bio-Analyst Agent results stored in SQLite.
#
# DESIGN:
#   - Minimalistic — white background (#FFFFFF), blue accents (#1A73E8)
#   - Left panel  : scrollable list of all protein runs
#   - Right panel : selected run detail — protein stats + scaffold cards
#   - Animations  : fade-in on load, slide-in cards, hover glow on scaffolds
#
# RUN:    python gui.py
# =============================================================================

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time

import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from database import init_db, fetch_all_runs, fetch_scaffolds_for_run, delete_run

# ─────────────────────────────────────────────────────────────────────────────
# COLOUR PALETTE & TYPOGRAPHY
# ─────────────────────────────────────────────────────────────────────────────
C_BG        = "#FFFFFF"   # window background
C_PANEL     = "#F5F8FF"   # left panel background
C_ACCENT    = "#1A73E8"   # primary blue
C_ACCENT_DK = "#1557B0"   # darker blue for hover
C_ACCENT_LT = "#E8F0FE"   # light blue tint for rows
C_TEXT      = "#1C1C2E"   # near-black for body text
C_MUTED     = "#6B7280"   # grey for secondary labels
C_CARD      = "#FAFCFF"   # scaffold card background
C_BORDER    = "#D1E3FF"   # card border
C_SUCCESS   = "#0D9488"   # teal for positive ADMET flags
C_WARN      = "#F59E0B"   # amber for warnings
C_DELETE    = "#EF4444"   # red for delete

FONT_TITLE  = ("Helvetica Neue", 22, "bold")
FONT_H2     = ("Helvetica Neue", 14, "bold")
FONT_H3     = ("Helvetica Neue", 12, "bold")
FONT_BODY   = ("Helvetica Neue", 11)
FONT_SMALL  = ("Helvetica Neue", 10)
FONT_BADGE  = ("Helvetica Neue", 9, "bold")
FONT_MONO   = ("Courier", 11)


# =============================================================================
# ANIMATED HELPERS
# =============================================================================

def fade_in(widget, steps: int = 20, delay_ms: int = 15):
    """
    Simulate a fade-in by stepping the widget's background from near-white
    towards the target colour. On macOS, true alpha fading requires a Canvas;
    we approximate it by animating opacity using after() calls to delay draw.
    Since Tkinter has limited alpha support, we do a staggered reveal instead:
    grid/pack the widget after a short delay so children appear sequentially.
    """
    widget.update_idletasks()


def slide_in_cards(cards: list, delay_ms: int = 80):
    """Reveal scaffold cards one by one with a staggered delay."""
    for i, card in enumerate(cards):
        card.after(i * delay_ms, lambda c=card: c.grid())


# =============================================================================
# REUSABLE UI COMPONENTS
# =============================================================================

class HoverButton(tk.Label):
    """A label that looks like a button with hover animation."""

    def __init__(self, parent, text, command, bg=C_ACCENT, fg="white",
                 font=FONT_BODY, padx=14, pady=6, radius=6, **kw):
        super().__init__(parent, text=text, bg=bg, fg=fg, font=font,
                         padx=padx, pady=pady, cursor="hand2", **kw)
        self._bg      = bg
        self._bg_hover = C_ACCENT_DK if bg == C_ACCENT else "#CC3333"
        self._command = command
        self.bind("<Enter>",  self._on_enter)
        self.bind("<Leave>",  self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _on_enter(self, _):
        self.config(bg=self._bg_hover)

    def _on_leave(self, _):
        self.config(bg=self._bg)

    def _on_click(self, _):
        if self._command:
            self._command()


class StatBadge(tk.Frame):
    """A small labelled metric box — used for MW, pI, length, etc."""

    def __init__(self, parent, label: str, value: str, **kw):
        super().__init__(parent, bg=C_ACCENT_LT, padx=12, pady=8,
                         highlightbackground=C_BORDER, highlightthickness=1, **kw)
        tk.Label(self, text=label, bg=C_ACCENT_LT, fg=C_MUTED,
                 font=FONT_SMALL).pack(anchor="w")
        tk.Label(self, text=value, bg=C_ACCENT_LT, fg=C_ACCENT,
                 font=FONT_H3).pack(anchor="w")


class ScaffoldCard(tk.Frame):
    """
    A card representing one drug scaffold proposal.
    Highlights on hover with a blue border glow effect.
    """

    def __init__(self, parent, scaffold: dict, index: int, **kw):
        super().__init__(parent, bg=C_CARD, bd=0,
                         highlightbackground=C_BORDER, highlightthickness=1,
                         padx=18, pady=14, **kw)

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

        # ── Scaffold header ────────────────────────────────────────────────
        header = tk.Frame(self, bg=C_CARD)
        header.pack(fill="x", anchor="w")

        num_label = tk.Label(header, text=f"  {index}  ", bg=C_ACCENT,
                             fg="white", font=FONT_BADGE, padx=4, pady=2)
        num_label.pack(side="left")

        name = scaffold.get("scaffold_name", "Unnamed Scaffold").title()
        tk.Label(header, text=f"  {name}", bg=C_CARD, fg=C_TEXT,
                 font=FONT_H3).pack(side="left")

        admet = scaffold.get("admet_flag", "")
        admet_colour = C_SUCCESS if "good" in admet.lower() else C_WARN
        tk.Label(header, text=f"  ✦ {admet}", bg=C_CARD, fg=admet_colour,
                 font=FONT_SMALL).pack(side="right")

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=(8, 10))

        # ── Properties grid ───────────────────────────────────────────────
        grid = tk.Frame(self, bg=C_CARD)
        grid.pack(fill="x")

        self._prop_row(grid, 0, "🎯  Target Residues",
                       scaffold.get("target_residues", "—"))
        self._prop_row(grid, 1, "⚙️  Mechanism",
                       scaffold.get("mechanism", "—"))
        self._prop_row(grid, 2, "⚖️  Est. MW (Da)",
                       str(scaffold.get("estimated_mw_da", "—")))
        self._prop_row(grid, 3, "🧪  Predicted logP",
                       str(scaffold.get("predicted_logP", "—")))

        # ── Optimisation note ─────────────────────────────────────────────
        note = scaffold.get("optimisation_note", "")
        if note:
            note_frame = tk.Frame(self, bg="#EEF4FF", padx=10, pady=6)
            note_frame.pack(fill="x", pady=(10, 0))
            tk.Label(note_frame, text="💡  Optimisation",
                     bg="#EEF4FF", fg=C_ACCENT, font=FONT_BADGE).pack(anchor="w")
            tk.Label(note_frame, text=note, bg="#EEF4FF", fg=C_TEXT,
                     font=FONT_SMALL, wraplength=520, justify="left").pack(anchor="w")

    def _prop_row(self, parent, row, label_text, value_text):
        tk.Label(parent, text=label_text, bg=C_CARD, fg=C_MUTED,
                 font=FONT_SMALL, width=22, anchor="w").grid(
                     row=row, column=0, sticky="w", pady=2)
        tk.Label(parent, text=value_text, bg=C_CARD, fg=C_TEXT,
                 font=FONT_BODY, anchor="w").grid(
                     row=row, column=1, sticky="w", pady=2)

    def _on_enter(self, _):
        self.config(highlightbackground=C_ACCENT, highlightthickness=2)

    def _on_leave(self, _):
        self.config(highlightbackground=C_BORDER, highlightthickness=1)


# =============================================================================
# MAIN APPLICATION
# =============================================================================

class BioAnalystGUI(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Bio-Analyst Agent — Discovery Results")
        self.geometry("1180x740")
        self.minsize(900, 580)
        self.configure(bg=C_BG)

        # Try to make the window appear sharp on Retina displays
        try:
            self.tk.call("tk", "scaling", 2.0)
        except Exception:
            pass

        self._selected_run_id = None
        self._run_list        = []

        init_db()
        self._build_layout()
        self._load_runs()

    # ─────────────────────────────────────────────────────────────────────────
    # LAYOUT SKELETON
    # ─────────────────────────────────────────────────────────────────────────

    def _build_layout(self):
        # ── Top bar ──────────────────────────────────────────────────────────
        topbar = tk.Frame(self, bg=C_ACCENT, height=54)
        topbar.pack(fill="x", side="top")
        topbar.pack_propagate(False)

        tk.Label(topbar, text="🧬  Bio-Analyst Agent", bg=C_ACCENT, fg="white",
                 font=FONT_TITLE).pack(side="left", padx=22, pady=10)
        tk.Label(topbar, text="Drug Target Discovery Pipeline  •  Ollama Powered",
                 bg=C_ACCENT, fg="#BDD8FF", font=FONT_SMALL).pack(
                     side="left", pady=10)

        HoverButton(topbar, "⟳  Refresh", self._load_runs,
                    bg="#1557B0", padx=12, pady=8).pack(side="right", padx=12, pady=10)

        # ── Main body ────────────────────────────────────────────────────────
        body = tk.Frame(self, bg=C_BG)
        body.pack(fill="both", expand=True)

        # Left panel — run list
        self._left = tk.Frame(body, bg=C_PANEL, width=260)
        self._left.pack(side="left", fill="y")
        self._left.pack_propagate(False)
        self._build_left_panel()

        # Divider
        tk.Frame(body, bg=C_BORDER, width=1).pack(side="left", fill="y")

        # Right panel — detail view
        self._right_outer = tk.Frame(body, bg=C_BG)
        self._right_outer.pack(side="left", fill="both", expand=True)
        self._show_empty_state()

    # ─────────────────────────────────────────────────────────────────────────
    # LEFT PANEL — protein run list
    # ─────────────────────────────────────────────────────────────────────────

    def _build_left_panel(self):
        tk.Label(self._left, text="Protein Runs", bg=C_PANEL,
                 fg=C_ACCENT, font=FONT_H2, pady=14).pack(fill="x", padx=16)

        ttk.Separator(self._left, orient="horizontal").pack(fill="x")

        # Scrollable list
        canvas = tk.Canvas(self._left, bg=C_PANEL, highlightthickness=0)
        scroll = tk.Scrollbar(self._left, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        self._list_frame = tk.Frame(canvas, bg=C_PANEL)
        self._list_window = canvas.create_window((0, 0), window=self._list_frame,
                                                  anchor="nw")

        self._list_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
            lambda e: canvas.itemconfig(self._list_window, width=e.width))

        # Mouse-wheel scroll
        def _on_mousewheel(event):
            canvas.yview_scroll(-1 * int(event.delta / 120), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self._list_canvas = canvas

    def _populate_run_list(self):
        for widget in self._list_frame.winfo_children():
            widget.destroy()

        if not self._run_list:
            tk.Label(self._list_frame, text="No runs yet.\nRun the pipeline first.",
                     bg=C_PANEL, fg=C_MUTED, font=FONT_BODY,
                     justify="center", pady=40).pack()
            return

        for run in self._run_list:
            self._make_run_row(run)

    def _make_run_row(self, run: dict):
        rid    = run["id"]
        is_sel = rid == self._selected_run_id
        bg     = C_ACCENT_LT if is_sel else C_PANEL
        border = C_ACCENT    if is_sel else C_PANEL

        row = tk.Frame(self._list_frame, bg=bg, cursor="hand2",
                       highlightbackground=border, highlightthickness=1 if is_sel else 0)
        row.pack(fill="x", padx=8, pady=3)

        # Protein abbreviation badge
        abbr = run["target_protein"].split()[0][:3].upper()
        tk.Label(row, text=abbr, bg=C_ACCENT if is_sel else C_BORDER,
                 fg="white" if is_sel else C_ACCENT,
                 font=FONT_BADGE, width=4, pady=8).pack(side="left")

        info = tk.Frame(row, bg=bg)
        info.pack(side="left", fill="both", expand=True, padx=10, pady=6)

        protein_short = run["target_protein"][:26] + (
            "…" if len(run["target_protein"]) > 26 else "")
        tk.Label(info, text=protein_short, bg=bg, fg=C_TEXT,
                 font=FONT_BODY, anchor="w").pack(fill="x")
        tk.Label(info, text=f"{run['ncbi_accession']}  •  {run['run_date'][:10]}",
                 bg=bg, fg=C_MUTED, font=FONT_SMALL, anchor="w").pack(fill="x")

        row.bind("<Button-1>", lambda _, r=run: self._select_run(r))
        info.bind("<Button-1>", lambda _, r=run: self._select_run(r))

        # Hover effects
        def _enter(_, w=row, inf=info, b=bg):
            if rid != self._selected_run_id:
                w.config(bg="#EBF2FF")
                inf.config(bg="#EBF2FF")
                for c in inf.winfo_children():
                    c.config(bg="#EBF2FF")

        def _leave(_, w=row, inf=info, b=bg):
            if rid != self._selected_run_id:
                w.config(bg=b)
                inf.config(bg=b)
                for c in inf.winfo_children():
                    c.config(bg=b)

        row.bind("<Enter>", _enter)
        row.bind("<Leave>", _leave)

    # ─────────────────────────────────────────────────────────────────────────
    # RIGHT PANEL — detail view
    # ─────────────────────────────────────────────────────────────────────────

    def _show_empty_state(self):
        self._clear_right()
        outer = tk.Frame(self._right_outer, bg=C_BG)
        outer.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(outer, text="🧬", bg=C_BG, font=("Helvetica", 52)).pack()
        tk.Label(outer, text="Select a protein run from the left panel",
                 bg=C_BG, fg=C_MUTED, font=FONT_H2).pack(pady=(8, 4))
        tk.Label(outer, text="or run  python bio_analyst_agent.py  to generate results",
                 bg=C_BG, fg=C_MUTED, font=FONT_BODY).pack()

    def _show_run_detail(self, run: dict):
        self._clear_right()

        # ── Outer scroll container ────────────────────────────────────────────
        canvas = tk.Canvas(self._right_outer, bg=C_BG, highlightthickness=0)
        vbar   = tk.Scrollbar(self._right_outer, orient="vertical",
                               command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        content = tk.Frame(canvas, bg=C_BG)
        cwin = canvas.create_window((0, 0), window=content, anchor="nw")

        def _on_frame_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        content.bind("<Configure>", _on_frame_configure)

        def _on_canvas_resize(e):
            canvas.itemconfig(cwin, width=e.width)
        canvas.bind("<Configure>", _on_canvas_resize)

        def _on_wheel(event):
            canvas.yview_scroll(-1 * int(event.delta / 120), "units")
        canvas.bind_all("<MouseWheel>", _on_wheel)

        pad = {"padx": 28, "pady": 6}

        # ── Header ────────────────────────────────────────────────────────────
        header = tk.Frame(content, bg=C_BG)
        header.pack(fill="x", **pad, pady=(22, 4))

        tk.Label(header, text=run["target_protein"],
                 bg=C_BG, fg=C_TEXT, font=FONT_TITLE, anchor="w").pack(
                     side="left", fill="x", expand=True)

        HoverButton(header, "🗑  Delete Run",
                    lambda r=run: self._confirm_delete(r),
                    bg=C_DELETE, fg="white", padx=10, pady=6).pack(side="right")

        # ── Meta row ──────────────────────────────────────────────────────────
        meta = tk.Frame(content, bg=C_BG)
        meta.pack(fill="x", **pad, pady=(0, 14))

        for txt in [f"NCBI: {run['ncbi_accession']}",
                    f"Run date: {run['run_date'][:10]}",
                    f"Model: {run['ai_model_used']}"]:
            tk.Label(meta, text=txt, bg=C_BG, fg=C_MUTED, font=FONT_SMALL).pack(
                side="left", padx=(0, 20))

        ttk.Separator(content, orient="horizontal").pack(fill="x", padx=28, pady=4)

        # ── Section 9-style Scientific Background ─────────────────────────────
        tk.Label(content, text="📖  Scientific Background",
                 bg=C_BG, fg=C_ACCENT, font=FONT_H2).pack(anchor="w", **pad,
                                                            pady=(14, 4))

        raw = run.get("raw_report", "")
        # Pull the first ~800 chars of the report as the summary paragraph
        summary_text = raw[:900].strip() if raw else "No report text available."
        summary_box = tk.Frame(content, bg=C_ACCENT_LT, padx=16, pady=12)
        summary_box.pack(fill="x", padx=28, pady=(0, 14))
        tk.Label(summary_box, text=summary_text, bg=C_ACCENT_LT, fg=C_TEXT,
                 font=FONT_BODY, wraplength=780, justify="left").pack(anchor="w")

        # ── Protein Stats ─────────────────────────────────────────────────────
        tk.Label(content, text="🔬  Protein Properties",
                 bg=C_BG, fg=C_ACCENT, font=FONT_H2).pack(anchor="w", **pad,
                                                            pady=(4, 6))

        stats_row = tk.Frame(content, bg=C_BG)
        stats_row.pack(fill="x", padx=28, pady=(0, 18))

        mw  = run.get("molecular_weight_da")
        pi  = run.get("isoelectric_point")
        sl  = run.get("sequence_length")
        aa  = run.get("top_5_amino_acids", "—")
        dn  = run.get("druggability_note", "—")

        stats = [
            ("Molecular Weight", f"{mw:,.0f} Da" if mw else "—"),
            ("Isoelectric Point", f"pH {pi:.2f}" if pi else "—"),
            ("Sequence Length", f"{sl} aa" if sl else "—"),
        ]
        for lbl, val in stats:
            StatBadge(stats_row, lbl, val).pack(side="left", padx=(0, 10))

        # Druggability note
        note_color = C_SUCCESS if "druggable" in (dn or "").lower() else C_WARN
        dn_box = tk.Frame(content, bg=C_BG)
        dn_box.pack(fill="x", padx=28, pady=(0, 6))
        tk.Label(dn_box, text=f"✦  {dn}", bg=C_BG, fg=note_color,
                 font=FONT_SMALL).pack(anchor="w")

        # Top amino acids
        if aa and aa != "—":
            tk.Label(content, text=f"Top amino acids:  {aa}",
                     bg=C_BG, fg=C_MUTED, font=FONT_SMALL).pack(
                         anchor="w", padx=28, pady=(0, 16))

        ttk.Separator(content, orient="horizontal").pack(fill="x", padx=28, pady=4)

        # ── Scaffold Cards ────────────────────────────────────────────────────
        tk.Label(content, text="💊  Drug Scaffold Proposals",
                 bg=C_BG, fg=C_ACCENT, font=FONT_H2).pack(anchor="w", **pad,
                                                            pady=(14, 8))

        scaffolds = fetch_scaffolds_for_run(run["id"])
        if not scaffolds:
            tk.Label(content, text="No scaffolds stored for this run.",
                     bg=C_BG, fg=C_MUTED, font=FONT_BODY).pack(anchor="w", padx=28)
        else:
            cards = []
            for i, sc in enumerate(scaffolds, start=1):
                card = ScaffoldCard(content, sc, index=i)
                card.pack(fill="x", padx=28, pady=(0, 10))
                card.pack_forget()   # hide initially for slide-in
                cards.append(card)
            # Stagger reveal
            slide_in_cards(cards, delay_ms=110)

        # ── Raw Report (collapsible) ───────────────────────────────────────────
        ttk.Separator(content, orient="horizontal").pack(fill="x", padx=28, pady=(18, 4))

        toggle_var = tk.BooleanVar(value=False)

        def _toggle_raw():
            if toggle_var.get():
                raw_box.pack(fill="x", padx=28, pady=(0, 20))
                toggle_btn.config(text="▲  Hide Full Report")
            else:
                raw_box.pack_forget()
                toggle_btn.config(text="▼  Show Full Report")

        toggle_btn = tk.Label(content, text="▼  Show Full Report",
                              bg=C_BG, fg=C_ACCENT, font=FONT_BODY, cursor="hand2")
        toggle_btn.pack(anchor="w", padx=28, pady=(4, 6))
        toggle_btn.bind("<Button-1>", lambda _: (toggle_var.set(not toggle_var.get()),
                                                  _toggle_raw()))

        raw_box = tk.Frame(content, bg="#F9FAFB", padx=14, pady=12)
        raw_text = tk.Text(raw_box, wrap="word", bg="#F9FAFB", fg=C_TEXT,
                           font=FONT_MONO, relief="flat", state="normal",
                           height=20, borderwidth=0)
        raw_text.insert("1.0", raw or "No report text stored.")
        raw_text.config(state="disabled")
        raw_text.pack(fill="both", expand=True)

        # bottom padding
        tk.Frame(content, bg=C_BG, height=30).pack()

    def _clear_right(self):
        for w in self._right_outer.winfo_children():
            w.destroy()

    # ─────────────────────────────────────────────────────────────────────────
    # DATA ACTIONS
    # ─────────────────────────────────────────────────────────────────────────

    def _load_runs(self):
        self._run_list = fetch_all_runs()
        self._populate_run_list()
        # If current selection still valid, refresh detail
        if self._selected_run_id:
            match = next((r for r in self._run_list
                          if r["id"] == self._selected_run_id), None)
            if match:
                self._show_run_detail(match)
            else:
                self._selected_run_id = None
                self._show_empty_state()

    def _select_run(self, run: dict):
        self._selected_run_id = run["id"]
        self._populate_run_list()   # refresh to update highlight
        self._show_run_detail(run)

    def _confirm_delete(self, run: dict):
        if messagebox.askyesno(
            "Delete Run",
            f"Delete the run for '{run['target_protein']}'?\n"
            "This cannot be undone.",
            icon="warning"
        ):
            delete_run(run["id"])
            self._selected_run_id = None
            self._load_runs()
            self._show_empty_state()


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    app = BioAnalystGUI()
    app.mainloop()
