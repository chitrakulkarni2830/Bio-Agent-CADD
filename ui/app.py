# =============================================================================
# FILE: app.py
# PROJECT: Bio-Analyst Agent — Unified Launcher + Dashboard
#
# HOW TO RUN:
#   python app.py
#   (or: /opt/homebrew/bin/python3.12 app.py)
#
# WHAT THIS FILE DOES:
#   Top bar    : Protein name + Accession ID inputs + Run Analysis button
#   Left panel : Scrollable sidebar of all analysed proteins
#   Right panel: Protein detail — metric tiles (animated), science fields,
#                drug scaffold cards (staggered reveal)
#   Bottom log : Live scrolling output from the agent pipeline
#   Extras     : Window fade-in, pulsing status dot, Refresh button
# =============================================================================

import sys
import subprocess
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox

import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from database import initialise_database, get_all_proteins, get_scaffolds

# =============================================================================
# COLOUR PALETTE & TYPOGRAPHY
# =============================================================================

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
    "log_bg":       "#0D1B2A",
    "log_text":     "#7FDBCA",
    "run_btn":      "#1A8754",
    "run_btn_h":    "#145E3C",
    "seed_btn":     "#B45309",
    "seed_btn_h":   "#7C3700",
    "stop_btn":     "#CC3333",
    "stop_btn_h":   "#991111",
}

F = {
    "title":   ("Georgia", 20, "bold"),
    "heading": ("Georgia", 15, "bold"),
    "subhead": ("Georgia", 12, "italic"),
    "body":    ("Helvetica Neue", 11),
    "body_b":  ("Helvetica Neue", 11, "bold"),
    "small":   ("Helvetica Neue", 10),
    "mono":    ("Courier New", 11),
    "mono_lg": ("Courier New", 16, "bold"),
    "label":   ("Helvetica Neue", 9),
    "nav":     ("Helvetica Neue", 12),
    "log":     ("Courier New", 10),
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
                    fg=fg, bg=bg, padx=2, pady=2)


def animate_count(widget, target: float, duration_ms=900,
                  suffix="", decimals=0, prefix=""):
    steps    = 40
    interval = max(1, duration_ms // steps)

    def step(i):
        if not widget.winfo_exists():
            return
        progress = (i / steps) ** 0.45
        current  = target * progress
        widget.config(text=f"{prefix}{current:,.{decimals}f}{suffix}")
        if i < steps:
            widget.after(interval, step, i + 1)
        else:
            widget.config(text=f"{prefix}{target:,.{decimals}f}{suffix}")

    step(0)


class HoverButton(tk.Label):
    """A label styled as a button with colour-swap on hover."""

    def __init__(self, parent, text, command,
                 bg=None, hover_bg=None, fg="white",
                 font=None, padx=16, pady=8, **kw):
        bg       = bg       or C["blue"]
        hover_bg = hover_bg or C["blue_dark"]
        font     = font     or F["body_b"]
        super().__init__(parent, text=text, bg=bg, fg=fg,
                         font=font, padx=padx, pady=pady,
                         cursor="hand2", **kw)
        self._bg  = bg
        self._hbg = hover_bg
        self._cmd = command
        self.bind("<Enter>",   lambda _: self.config(bg=self._hbg))
        self.bind("<Leave>",   lambda _: self.config(bg=self._bg))
        self.bind("<Button-1>", lambda _: self._cmd() if self._cmd else None)


# =============================================================================
# MAIN APPLICATION
# =============================================================================

class BioAnalystApp(tk.Tk):
    """
    Single-file unified app:
      • Top bar  — input fields + action buttons
      • Body     — left sidebar (protein list) + right detail panel
      • Bottom   — collapsible live log
    """

    def __init__(self):
        super().__init__()
        initialise_database()

        self.proteins        = []
        self.selected_index  = None
        self._pulse_state    = True
        self._pipeline_proc  = None
        self._log_queue      = queue.Queue()

        self._build_window()
        self._build_topbar()
        self._build_body()
        self._build_log_panel()
        self._build_statusbar()

        # Fade in
        self.attributes("-alpha", 0.0)
        self._fade_in(0)

        self._refresh_proteins()
        self._start_pulse()
        self._poll_log_queue()

    # ── Window ────────────────────────────────────────────────────────────────

    def _build_window(self):
        self.title("🧬  Bio-Analyst Agent  |  Drug Discovery Dashboard")
        self.geometry("1280x820")
        self.minsize(980, 620)
        self.configure(bg=C["bg"])
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - 1280) // 2
        y = (self.winfo_screenheight() -  820) // 2
        self.geometry(f"1280x820+{x}+{y}")

    # ── Top bar ───────────────────────────────────────────────────────────────

    def _build_topbar(self):
        bar = tk.Frame(self, bg=C["blue"], height=62)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        # Brand
        tk.Label(bar, text="🧬  Bio-Analyst Agent",
                 font=("Georgia", 16, "bold"),
                 fg=C["white"], bg=C["blue"],
                 padx=20).pack(side="left", pady=14)

        # Buttons (right-aligned)
        btn_frame = tk.Frame(bar, bg=C["blue"])
        btn_frame.pack(side="right", padx=12, pady=10)

        HoverButton(btn_frame, "⟳  Refresh", self._refresh_proteins,
                    bg="#1557B0", hover_bg="#0E4A99",
                    padx=12, pady=6).pack(side="right", padx=(6, 0))

        HoverButton(btn_frame, "🌱  Seed Sample Data", self._seed_data,
                    bg=C["seed_btn"], hover_bg=C["seed_btn_h"],
                    padx=12, pady=6).pack(side="right", padx=(6, 0))

        # Input fields
        fields = tk.Frame(bar, bg=C["blue"])
        fields.pack(side="left", padx=(6, 0), pady=10)

        tk.Label(fields, text="Protein:", fg="#BDD8FF",
                 bg=C["blue"], font=F["small"]).grid(row=0, column=0, padx=(0, 4))
        self._protein_var = tk.StringVar(value="Mpro SARS-CoV-2 main protease")
        tk.Entry(fields, textvariable=self._protein_var,
                 font=F["body"], width=30,
                 bg="#1557B0", fg="white", insertbackground="white",
                 relief="flat", bd=4).grid(row=0, column=1, padx=(0, 14))

        tk.Label(fields, text="NCBI ID:", fg="#BDD8FF",
                 bg=C["blue"], font=F["small"]).grid(row=0, column=2, padx=(0, 4))
        self._accession_var = tk.StringVar(value="P0DTD1")
        tk.Entry(fields, textvariable=self._accession_var,
                 font=F["body"], width=12,
                 bg="#1557B0", fg="white", insertbackground="white",
                 relief="flat", bd=4).grid(row=0, column=3, padx=(0, 14))

        self._run_btn = HoverButton(fields, "▶  Run Analysis", self._run_pipeline,
                                    bg=C["run_btn"], hover_bg=C["run_btn_h"],
                                    padx=14, pady=6)
        self._run_btn.grid(row=0, column=4)

    # ── Body (sidebar + detail) ───────────────────────────────────────────────

    def _build_body(self):
        self._body = tk.Frame(self, bg=C["bg"])
        self._body.pack(fill="both", expand=True)

        # Sidebar
        self._sidebar = tk.Frame(self._body, bg=C["sidebar"], width=270)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)
        self._build_sidebar()

        # Divider
        tk.Frame(self._body, width=1, bg=C["border"]).pack(side="left", fill="y")

        # Right detail panel
        self._right = tk.Frame(self._body, bg=C["bg"])
        self._right.pack(side="left", fill="both", expand=True)
        self._build_main_area()

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self):
        # Header
        hdr = tk.Frame(self._sidebar, bg=C["blue"], height=48)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="PROTEIN TARGETS",
                 font=("Helvetica Neue", 9, "bold"),
                 fg=C["white"], bg=C["blue"],
                 anchor="w", padx=18).pack(fill="both", expand=True)

        hline(self._sidebar, pady=0)

        # Scrollable list
        outer = tk.Frame(self._sidebar, bg=C["sidebar"])
        outer.pack(fill="both", expand=True, pady=(4, 0))

        canvas = tk.Canvas(outer, bg=C["sidebar"],
                           highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        self.list_frame = tk.Frame(canvas, bg=C["sidebar"])
        self.list_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

    # ── Main panel ────────────────────────────────────────────────────────────

    def _build_main_area(self):
        # Header row
        hdr = tk.Frame(self._right, bg=C["bg"], height=48)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        self.title_lbl = tk.Label(hdr,
                                  text="Select a protein from the sidebar →",
                                  font=F["heading"], fg=C["muted"], bg=C["bg"],
                                  anchor="w", padx=28)
        self.title_lbl.pack(side="left", fill="both", expand=True)
        self.date_lbl = tk.Label(hdr, text="",
                                 font=F["small"], fg=C["muted"], bg=C["bg"],
                                 anchor="e", padx=24)
        self.date_lbl.pack(side="right")

        hline(self._right, pady=0)

        # Scrollable detail canvas
        detail_outer = tk.Frame(self._right, bg=C["bg"])
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
            lambda e: self.detail_canvas.yview_scroll(
                -1 * (e.delta // 120), "units"))

        # Empty state
        self.empty_lbl = tk.Label(
            self.detail_frame,
            text=("No proteins in the database yet.\n\n"
                  "Click  🌱 Seed Sample Data  to load examples,\n"
                  "or click  ▶ Run Analysis  to run the full pipeline."),
            font=F["body"], fg=C["muted"], bg=C["bg"], justify="center")

    # ── Log panel ─────────────────────────────────────────────────────────────

    def _build_log_panel(self):
        """Collapsible bottom log panel."""
        self._log_visible = False

        self._log_toggle_bar = tk.Frame(self, bg=C["sidebar"], height=28)
        self._log_toggle_bar.pack(fill="x", side="bottom")
        self._log_toggle_bar.pack_propagate(False)

        self._log_toggle_lbl = tk.Label(
            self._log_toggle_bar,
            text="▲  Show Pipeline Log",
            font=F["small"], fg=C["blue"], bg=C["sidebar"],
            cursor="hand2")
        self._log_toggle_lbl.pack(side="left", padx=14, pady=4)
        self._log_toggle_lbl.bind("<Button-1>", lambda _: self._toggle_log())

        self._log_outer = tk.Frame(self, bg=C["log_bg"], height=200)

        self._log_text = tk.Text(
            self._log_outer,
            bg=C["log_bg"], fg=C["log_text"],
            font=F["log"], wrap="word",
            relief="flat", bd=0,
            state="disabled")
        log_scroll = tk.Scrollbar(self._log_outer, orient="vertical",
                                  command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="right", fill="y")
        self._log_text.pack(fill="both", expand=True, padx=6, pady=4)

    def _toggle_log(self):
        if self._log_visible:
            self._log_outer.pack_forget()
            self._log_toggle_lbl.config(text="▲  Show Pipeline Log")
        else:
            self._log_outer.pack(fill="x", side="bottom", before=self._log_toggle_bar)
            self._log_toggle_lbl.config(text="▼  Hide Pipeline Log")
        self._log_visible = not self._log_visible

    def _append_log(self, text: str):
        self._log_text.config(state="normal")
        self._log_text.insert("end", text)
        self._log_text.see("end")
        self._log_text.config(state="disabled")

    def _clear_log(self):
        self._log_text.config(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.config(state="disabled")

    # ── Status bar ────────────────────────────────────────────────────────────

    def _build_statusbar(self):
        bar = tk.Frame(self._right, bg=C["sidebar"], height=26)
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

        self.status_lbl = tk.Label(bar, text="Ready",
                                   font=("Helvetica Neue", 9),
                                   fg=C["green"], bg=C["sidebar"])
        self.status_lbl.pack(side="right", padx=12)

    # ── Animations ────────────────────────────────────────────────────────────

    def _fade_in(self, step):
        self.attributes("-alpha", min(step / 20.0, 1.0))
        if step < 20:
            self.after(15, self._fade_in, step + 1)

    def _start_pulse(self):
        self._pulse_state = not self._pulse_state
        color = C["blue"] if self._pulse_state else C["blue_mid"]
        if self.status_dot.winfo_exists():
            self.status_dot.config(fg=color)
        self.after(900, self._start_pulse)

    # ── Pipeline execution ────────────────────────────────────────────────────

    def _run_pipeline(self):
        if self._pipeline_proc and self._pipeline_proc.poll() is None:
            messagebox.showinfo("Already Running",
                                "The pipeline is already running.\n"
                                "Please wait for it to finish.")
            return

        protein    = self._protein_var.get().strip()
        accession  = self._accession_var.get().strip()
        if not protein or not accession:
            messagebox.showwarning("Missing Input",
                                   "Please enter both a Protein Name and NCBI Accession ID.")
            return

        # Show log panel automatically
        if not self._log_visible:
            self._toggle_log()

        self._clear_log()
        self._append_log(f"{'='*60}\n")
        self._append_log(f"  Starting pipeline...\n")
        self._append_log(f"  Protein   : {protein}\n")
        self._append_log(f"  NCBI ID   : {accession}\n")
        self._append_log(f"{'='*60}\n\n")

        # Disable run button
        self._run_btn.config(text="⏳  Running…",
                             bg="#666666", cursor="watch")
        self._run_btn._cmd  = None
        self.status_lbl.config(text="Running pipeline…", fg=C["amber"])

        # Patch the configuration in bio_analyst_agent.py via env vars and
        # run it as a subprocess so stdout streams back to us live
        import os
        env = os.environ.copy()
        env["BAA_TARGET_PROTEIN"] = protein
        env["BAA_NCBI_ACCESSION"]  = accession

        # We pass env vars → the pipeline script needs to read them.
        # But since bio_analyst_agent.py hardcodes values, we build a tiny
        # wrapper script string and run it instead.
        runner_code = f"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

# Override config before importing the pipeline modules
import sys, os
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, "scripts"))

import database
database.initialise_database()

from datetime import datetime
import json, re
from crewai import Agent, Task, Crew, Process
from langchain_community.chat_models import ChatOllama
from tools.ncbi_tool import ncbi_protein_fetcher, fetch_ncbi_data_dict
from database import save_protein, save_scaffolds, log_run

TARGET_PROTEIN = {repr(protein)}
NCBI_ACCESSION = {repr(accession)}
OLLAMA_MODEL   = "llama3"
TEMPERATURE    = 0.1

print("--- Connecting to Ollama ({{}})... ---".format(OLLAMA_MODEL))
local_llm = ChatOllama(model=OLLAMA_MODEL, base_url="http://localhost:11434",
                       temperature=TEMPERATURE)
print("Connected.\\n")

researcher_agent = Agent(
    role="Senior Structural Biology Researcher",
    goal=(f"Provide a detailed analysis of {{TARGET_PROTEIN}}. "
          f"Focus on catalytic residues, binding pocket, known inhibitors, ADMET."),
    backstory="Computational biologist with 10 years experience in structure-based drug design.",
    tools=[], llm=local_llm, verbose=True, allow_delegation=False, max_iter=3)

data_analyst_agent = Agent(
    role="Bioinformatics Data Analyst",
    goal=(f"Use ncbi_protein_fetcher with input '{{NCBI_ACCESSION}}' to fetch "
          f"the sequence for {{TARGET_PROTEIN}}. Interpret MW, pI, amino acids, druggability."),
    backstory="Bioinformatics engineer specialising in protein sequence analysis.",
    tools=[ncbi_protein_fetcher], llm=local_llm, verbose=True,
    allow_delegation=False, max_iter=4)

reporter_agent = Agent(
    role="Drug Discovery Report Writer",
    goal=("Synthesise all findings. Write a report with 3 drug scaffold proposals "
          "and a valid JSON array for database storage."),
    backstory="Medicinal chemist bridging biology with computational drug design.",
    tools=[], llm=local_llm, verbose=True, allow_delegation=False, max_iter=4)

task_research = Task(
    description=(f"Research {{TARGET_PROTEIN}}. Cover in a numbered list:\\n"
                 "1. FUNCTION  2. DISEASE LINK  3. BINDING SITE  "
                 "4. KNOWN INHIBITORS  5. ADMET CONCERNS"),
    agent=researcher_agent,
    expected_output="Numbered 1-5 covering function, disease, residues, inhibitors, ADMET.")

task_analysis = Task(
    description=(f"Fetch sequence for {{TARGET_PROTEIN}} using ncbi_protein_fetcher "
                 f"with input '{{NCBI_ACCESSION}}'. Interpret MW, pI, top amino acids."),
    agent=data_analyst_agent,
    expected_output="Data report with real numbers + written interpretation.",
    context=[task_research])

task_report = Task(
    description=(
        "## SECTION A — Target Summary (3-4 sentences)\\n\\n"
        "## SECTION B — 3 Drug Scaffold Proposals\\n"
        "For each: Name, Binding residues, Mechanism, ADMET, Optimisation tip.\\n\\n"
        "## SECTION C — JSON DATA BLOCK (REQUIRED)\\n"
        "Output a valid JSON array with exactly 3 scaffold objects:\\n"
        '[{{"scaffold_name":"...","target_residues":"...","mechanism":"...",'
        '"estimated_mw_da":450,"predicted_logP":2.1,'
        '"admet_flag":"...","optimisation_note":"..."}}]'
    ),
    agent=reporter_agent,
    expected_output="Section A, B, C with valid JSON array of 3 scaffolds.",
    context=[task_research, task_analysis])

crew = Crew(agents=[researcher_agent, data_analyst_agent, reporter_agent],
            tasks=[task_research, task_analysis, task_report], verbose=True)

print("\\n🚀 Starting crew...\\n" + "-"*60)
crew_result       = crew.kickoff()
final_output_text = str(crew_result)

ncbi_data       = fetch_ncbi_data_dict(NCBI_ACCESSION)
researcher_text = ""
if hasattr(task_research, "output") and task_research.output:
    if hasattr(task_research.output, "raw_output"):
        researcher_text = task_research.output.raw_output
    elif hasattr(task_research.output, "exported_output"):
        researcher_text = str(task_research.output.exported_output)
    else:
        researcher_text = str(task_research.output)

def _extract(text, keyword, chars=350):
    lines = text.split("\\n")
    for i, line in enumerate(lines):
        if keyword.lower() in line.lower():
            return " ".join(lines[i:i+4]).strip()[:chars]
    return "See terminal output."

scaffolds = []
match = re.search(r'\\[\\s*\\{{.*?\\}}\\s*\\]', final_output_text, re.DOTALL)
if match:
    try:
        scaffolds = json.loads(match.group())
    except json.JSONDecodeError:
        pass
if not scaffolds:
    scaffolds = [{{"scaffold_name": f"Scaffold {{i+1}} — re-run for full data",
                   "target_residues":"N/A","mechanism":"N/A",
                   "estimated_mw_da":0,"predicted_logP":0,
                   "admet_flag":"N/A","optimisation_note":final_output_text[:100]}}
                 for i in range(3)]

protein_data = {{
    "accession_id":            NCBI_ACCESSION,
    "target_description":      TARGET_PROTEIN,
    "protein_name":            ncbi_data.get("protein_name", TARGET_PROTEIN),
    "sequence_length":         ncbi_data.get("sequence_length", 0),
    "molecular_weight_da":     ncbi_data.get("molecular_weight_da", 0.0),
    "isoelectric_point":       ncbi_data.get("isoelectric_point_pi", 0.0),
    "top_5_amino_acids":       ncbi_data.get("top_5_amino_acids", ""),
    "druggability_note":       ncbi_data.get("druggability_note", ""),
    "disease_link":            _extract(researcher_text, "disease"),
    "binding_site_residues":   _extract(researcher_text, "binding"),
    "known_inhibitor_classes": _extract(researcher_text, "inhibitor"),
    "admet_concerns":          _extract(researcher_text, "admet"),
    "run_date":                datetime.now().strftime("%Y-%m-%d"),
    "ai_model_used":           OLLAMA_MODEL,
}}

ok1 = save_protein(protein_data)
ok2 = save_scaffolds(scaffolds, NCBI_ACCESSION)
log_run(NCBI_ACCESSION, "success" if (ok1 and ok2) else "partial",
        f"model={{OLLAMA_MODEL}}")
print(f"\\n✅ Pipeline complete! Protein: {{'✓' if ok1 else '✗'}}  Scaffolds: {{'✓' if ok2 else '✗'}}")
"""

        import tempfile, os
        script_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)))
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", dir=script_dir,
            delete=False, prefix="_baa_runner_")
        tmp.write(runner_code)
        tmp.flush()
        tmp.close()
        self._tmp_script = tmp.name

        def run():
            try:
                proc = subprocess.Popen(
                    [sys.executable, tmp.name],
                    cwd=script_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True, bufsize=1)
                self._pipeline_proc = proc
                for line in proc.stdout:
                    self._log_queue.put(line)
                proc.wait()
            finally:
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass
                self._log_queue.put("__DONE__")

        threading.Thread(target=run, daemon=True).start()

    def _poll_log_queue(self):
        try:
            while True:
                line = self._log_queue.get_nowait()
                if line == "__DONE__":
                    self._on_pipeline_done()
                else:
                    self._append_log(line)
        except queue.Empty:
            pass
        self.after(100, self._poll_log_queue)

    def _on_pipeline_done(self):
        self._append_log("\n" + "="*60 + "\n")
        self._append_log("  ✅  Pipeline finished — refreshing results…\n")
        self._append_log("="*60 + "\n")
        self._run_btn.config(text="▶  Run Analysis",
                             bg=C["run_btn"], cursor="hand2")
        self._run_btn._cmd = self._run_pipeline
        self.status_lbl.config(text="Ready", fg=C["green"])
        
        # Explicitly select the newly run protein
        target_acc = self._accession_var.get().strip()
        self.proteins = get_all_proteins()
        for i, p in enumerate(self.proteins):
            if p.get("accession_id") == target_acc:
                self.selected_index = i
                break
        self._refresh_proteins()

    # ── Seed sample data ──────────────────────────────────────────────────────

    def _seed_data(self):
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        db_script  = os.path.join(os.path.dirname(script_dir), "scripts", "database.py")
        try:
            result = subprocess.run(
                [sys.executable, db_script],
                cwd=script_dir,
                capture_output=True, text=True, timeout=15)
            if not self._log_visible:
                self._toggle_log()
            self._append_log("\n--- Seed Sample Data ---\n")
            self._append_log(result.stdout or "")
            if result.stderr:
                self._append_log(result.stderr)
            self._refresh_proteins()
        except Exception as e:
            messagebox.showerror("Seed Error", str(e))

    # ── Data ──────────────────────────────────────────────────────────────────

    def _refresh_proteins(self):
        self.proteins = get_all_proteins()
        self._rebuild_list()
        n = len(self.proteins)
        self.count_lbl.config(text=f"{n} protein(s)")
        if self.proteins and self.selected_index is None:
            self._select_protein(0)
        elif self.proteins and self.selected_index is not None:
            idx = min(self.selected_index, len(self.proteins) - 1)
            self._select_protein(idx)

    def _rebuild_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        if not self.proteins:
            tk.Label(self.list_frame,
                     text="No proteins yet.\nRun the pipeline or\nclick Seed Sample Data.",
                     font=F["small"], fg=C["muted"], bg=C["sidebar"],
                     justify="left", padx=18, pady=16).pack(anchor="w")
            self.empty_lbl.pack(pady=80)
            return
        self.empty_lbl.pack_forget()
        for i, p in enumerate(self.proteins):
            self._make_list_item(i, p)

    def _make_list_item(self, idx, p):
        is_sel = (idx == self.selected_index)
        bg   = C["selected"] if is_sel else C["sidebar"]
        fg   = C["selected_txt"] if is_sel else C["text"]
        fg2  = C["selected_txt"] if is_sel else C["muted"]

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
            w.bind("<Enter>",    on_enter)
            w.bind("<Leave>",    on_leave)

    def _select_protein(self, idx):
        self.selected_index = idx
        self._rebuild_list()
        p         = self.proteins[idx]
        scaffolds = get_scaffolds(p["accession_id"])

        self.title_lbl.config(
            text=p.get("target_description", p.get("accession_id", "")),
            fg=C["text"])
        self.date_lbl.config(
            text=(f"Analysed: {p.get('run_date', '—')}  ·  "
                  f"Model: {p.get('ai_model_used', '—')}"))

        for w in self.detail_frame.winfo_children():
            w.destroy()
        self.detail_canvas.yview_moveto(0)
        self._build_detail(p, scaffolds)

    # ── Detail panel ──────────────────────────────────────────────────────────

    def _build_detail(self, p, scaffolds):
        pad = {"padx": 28, "pady": 0}

        # Accession + name
        top = tk.Frame(self.detail_frame, bg=C["bg"])
        top.pack(fill="x", padx=pad.get("padx", 28), pady=(20, 4))
        tk.Label(top, text=p.get("accession_id", "—"),
                 font=("Courier New", 11, "bold"),
                 fg=C["blue"], bg=C["bg"], anchor="w").pack(anchor="w")
        tk.Label(top,
                 text=p.get("protein_name", p.get("target_description", ""))[:90],
                 font=F["subhead"], fg=C["muted"], bg=C["bg"],
                 anchor="w").pack(anchor="w")

        hline(self.detail_frame, pady=10)

        # ── Metric tiles with count-up animation ──────────────────────────────
        tiles_row = tk.Frame(self.detail_frame, bg=C["bg"])
        tiles_row.pack(fill="x", padx=28, pady=(0, 16))

        mw_val  = float(p.get("molecular_weight_da", 0) or 0)
        pi_val  = float(p.get("isoelectric_point",    0) or 0)
        len_val = float(p.get("sequence_length",       0) or 0)

        mw_lbl  = self._metric_tile(tiles_row, "Molecular Weight",      "—", C["blue"])
        pi_lbl  = self._metric_tile(tiles_row, "Isoelectric Point (pI)","—", C["blue"])
        len_lbl = self._metric_tile(tiles_row, "Sequence Length",       "—", C["blue"])

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

        # ── Science fields 2×2 grid ───────────────────────────────────────────
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
                     anchor="w", padx=12).pack(fill="x", pady=(8, 2))
            tk.Label(cell, text=(content or "—")[:260],
                     font=F["small"], fg=C["text"], bg=C["blue_light"],
                     anchor="w", padx=12,
                     wraplength=380, justify="left").pack(fill="x", pady=(2, 10))

        # ── Top amino acid chips ──────────────────────────────────────────────
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

        # ── Druggability banner ───────────────────────────────────────────────
        drug = p.get("druggability_note", "")
        if drug:
            banner = tk.Frame(self.detail_frame, bg=C["green_bg"],
                              highlightbackground=C["green"], highlightthickness=1)
            banner.pack(fill="x", padx=28, pady=(8, 0))
            tk.Label(banner, text=f"✓  {drug}",
                     font=F["small"], fg=C["green"], bg=C["green_bg"],
                     anchor="w", padx=14, pady=8,
                     wraplength=700, justify="left").pack(fill="x")

        # ── Scaffold cards ────────────────────────────────────────────────────
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
            tk.Label(self.detail_frame,
                     text="No scaffold data for this protein.",
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
                 anchor="w", padx=14).pack(fill="x", pady=(10, 2))
        value_lbl = tk.Label(tile, text=initial_value,
                             font=F["mono_lg"], fg=accent, bg=C["white"],
                             anchor="w", padx=14)
        value_lbl.pack(fill="x", pady=(0, 12))
        return value_lbl

    def _scaffold_card(self, s, index):
        if not self.detail_frame.winfo_exists():
            return
        card = tk.Frame(self.detail_frame, bg=C["white"],
                        highlightbackground=C["blue"], highlightthickness=2)
        card.pack(fill="x", padx=28, pady=6)

        tk.Label(card, text=f" {index + 1} ",
                 font=("Georgia", 13, "bold"),
                 fg=C["white"], bg=C["blue"],
                 padx=10, pady=6).pack(side="left", anchor="n",
                                       padx=(0, 12), pady=12)

        content = tk.Frame(card, bg=C["white"])
        content.pack(side="left", fill="both", expand=True, pady=10)

        tk.Label(content, text=s.get("scaffold_name", "Unknown Scaffold"),
                 font=("Georgia", 12, "bold"),
                 fg=C["blue_dark"], bg=C["white"], anchor="w").pack(anchor="w")

        mech = s.get("mechanism", "")
        if mech:
            chip(content, mech).pack(anchor="w", pady=(3, 6))

        # Data chips row
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

        mw_val = float(s.get("estimated_mw_da", 0) or 0)
        lp_val = float(s.get("predicted_logP",  0) or 0)
        admet  = s.get("admet_flag", "—")

        data_chip(data_row, "Est. MW (Da)", f"{mw_val:.0f}")
        data_chip(data_row, "Pred. logP",   f"{lp_val:.1f}")

        admet_frame = tk.Frame(data_row, bg=C["amber_bg"],
                               highlightbackground=C["amber"], highlightthickness=1)
        admet_frame.pack(side="left")
        tk.Label(admet_frame, text="ADMET",
                 font=("Helvetica Neue", 8),
                 fg=C["amber"], bg=C["amber_bg"], padx=8, pady=2).pack()
        tk.Label(admet_frame, text=(admet or "—")[:40],
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
