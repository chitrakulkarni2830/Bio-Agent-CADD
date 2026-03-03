# Bio-Analyst Agent — Project Report

**Project Title:** Bio-Analyst Agent: An Autonomous Multi-Agent System for AI-Driven Drug Target Discovery  
**Date:** March 2026  
**Technology Stack:** Python · CrewAI · LangChain · Ollama (Llama3) · BioPython · SQLite · Tkinter

---

## 1. Executive Summary

The Bio-Analyst Agent is an end-to-end, locally-hosted AI pipeline for protein drug target discovery. It orchestrates three specialised AI agents — a Structural Biology Researcher, a Bioinformatics Data Analyst, and a Drug Discovery Reporter — that work sequentially to produce a complete drug target profile from a single protein accession ID.

The system fetches live sequence data directly from NCBI, computes biophysical properties using BioPython, generates three structured drug scaffold proposals via a local large language model (Llama3 via Ollama), persists all results to SQLite, and presents them in a polished Tkinter desktop dashboard. The entire pipeline runs locally, requires no API keys, and incurs zero cost.

---

## 2. Problem Statement

Early-stage drug discovery requires researchers to manually aggregate information from multiple sources: protein databases (NCBI, UniProt), scientific literature, and computational chemistry tools. This is time-consuming, fragmented, and requires deep domain expertise across structural biology, bioinformatics, and medicinal chemistry.

The Bio-Analyst Agent addresses this by automating the entire information-gathering and initial scaffold proposal phase using a multi-agent AI architecture, reducing a multi-hour manual task to a fully automated 2–5 minute pipeline run.

---

## 3. System Architecture

### 3.1 High-Level Pipeline

```
User Input (Accession ID)
        │
        ▼
┌───────────────────┐
│  Agent 1          │  Literature research — function, disease-link,
│  Researcher       │  binding residues, inhibitor classes, ADMET
└────────┬──────────┘
         │ context
         ▼
┌───────────────────┐
│  Agent 2          │  Live NCBI fetch → BioPython analysis
│  Data Analyst     │  (MW, pI, sequence length, amino acids)
└────────┬──────────┘
         │ context
         ▼
┌───────────────────┐
│  Agent 3          │  Synthesises findings → 3 scaffold proposals
│  Reporter         │  → structured JSON output
└────────┬──────────┘
         │
         ▼
   SQLite Database (bio_research.db)
         │
         ▼
   Tkinter Dashboard (dashboard.py)
```

### 3.2 Component Breakdown

| Component | File | Purpose |
|---|---|---|
| Pipeline Orchestrator | `bio_analyst_agent.py` | Configures agents, tasks, crew; parses output; saves to DB |
| NCBI Tool | `tools/ncbi_tool.py` | Fetches protein FASTA from NCBI Entrez; runs BioPython analysis |
| Database Layer | `database.py` | SQLite schema + all read/write operations |
| Dashboard GUI | `dashboard.py` | Primary visualisation interface |
| Results Browser | `gui.py` | Alternate detailed results viewer |

---

## 4. Agent Design

### Agent 1 — Senior Structural Biology Researcher

- **Role:** Provide a structured 5-point analysis of the target protein
- **Output covers:** Biological function, disease relevance, catalytic residues (e.g. His41-Cys145 for Mpro), known inhibitor classes, ADMET considerations
- **Tools:** None — relies on Llama3's scientific knowledge base
- **Max iterations:** 3

### Agent 2 — Bioinformatics Data Analyst

- **Role:** Fetch real sequence data and interpret biophysical properties
- **Tool:** `ncbi_protein_fetcher` — connects to NCBI Entrez, downloads FASTA sequence, runs BioPython `ProteinAnalysis` to compute:
  - Molecular weight (Da)
  - Isoelectric point (pI)
  - Sequence length (amino acids)
  - Top 5 amino acids by frequency
  - Druggability assessment (MW vs 20–100 kDa range)
- **Design principle:** Agent is instructed to always use the tool, never estimate values
- **Max iterations:** 4

### Agent 3 — Drug Discovery Report Writer

- **Role:** Synthesise all findings into a structured report with 3 drug scaffold proposals
- **Output format:** Two prose sections (Target Summary, Scaffold Rationale) plus a **valid JSON array** of 3 scaffold objects, parsed by regex and saved to the database
- **Scaffold fields:** `scaffold_name`, `target_residues`, `mechanism`, `estimated_mw_da`, `predicted_logP`, `admet_flag`, `optimisation_note`
- **Fallback:** If JSON parsing fails, placeholder scaffolds are inserted so the database and GUI remain functional
- **Max iterations:** 4

---

## 5. Data Model

The SQLite database (`bio_research.db`) contains three tables:

### `proteins`
Stores one row per protein target (upserted on re-run — no duplicates).

| Column | Type | Description |
|---|---|---|
| `accession_id` | TEXT UNIQUE | NCBI accession (e.g. P0DTD1) |
| `target_description` | TEXT | Human-readable protein name |
| `molecular_weight_da` | REAL | BioPython-calculated MW |
| `isoelectric_point` | REAL | pI at standard conditions |
| `sequence_length` | INTEGER | Cleaned amino acid count |
| `top_5_amino_acids` | TEXT | Frequency-ranked residues |
| `druggability_note` | TEXT | Automated druggability assessment |
| `disease_link` | TEXT | Extracted from Agent 1 output |
| `binding_site_residues` | TEXT | Extracted from Agent 1 output |
| `known_inhibitor_classes` | TEXT | Extracted from Agent 1 output |
| `admet_concerns` | TEXT | Extracted from Agent 1 output |
| `ai_model_used` | TEXT | e.g. "llama3" |

### `scaffolds`
Three rows per protein (old rows replaced on re-run).

| Column | Type | Description |
|---|---|---|
| `scaffold_name` | TEXT | Chemical class name |
| `mechanism` | TEXT | Covalent / non-covalent / allosteric |
| `estimated_mw_da` | REAL | Predicted scaffold molecular weight |
| `predicted_logP` | REAL | Lipophilicity estimate |
| `admet_flag` | TEXT | Key ADMET property note |
| `optimisation_note` | TEXT | One specific optimisation suggestion |

### `run_log`
Append-only audit trail — one row per pipeline execution.

---

## 6. GUI Dashboard

The Tkinter dashboard (`dashboard.py`) provides a clean, animated interface:

- **Window fade-in** on launch (alpha 0→1 over 300 ms)
- **Sidebar** — scrollable list of all proteins with hover effects and selected-state highlighting
- **Metric tiles** — MW, pI, and Sequence Length with **count-up animation** (ease-out curve, 40 steps)
- **Science grid** — 2×2 card layout for Disease Link, Binding Site, Inhibitor Classes, ADMET Concerns
- **Amino acid chips** — visual pill display of top amino acids
- **Druggability banner** — green highlight if target is druggable
- **Scaffold cards** — staggered reveal (120ms per card), mechanism chip, MW/logP/ADMET data rows
- **Pulsing status dot** — live indicator animating between two blues every 900 ms
- **Refresh button** — reloads from database without window restart

A secondary GUI (`gui.py`) provides an alternative view with collapsible raw report text and a delete-run function.

---

## 7. Example Results — SARS-CoV-2 Main Protease (P0DTD1)

| Property | Value |
|---|---|
| Molecular Weight | 33,796.8 Da |
| Isoelectric Point | pH 6.24 |
| Sequence Length | 306 amino acids |
| Top Amino Acids | Leu 9.2%, Ala 8.5%, Gly 7.8%, Val 7.1%, Glu 6.4% |
| Druggability | ✓ Within enzyme range (20–100 kDa) |

**Proposed Drug Scaffolds:**

| Scaffold | Targets | MW (Da) | logP | ADMET |
|---|---|---|---|---|
| Alpha-ketoamide | Cys145, His41 | 452 | 2.1 | Good oral bioavailability |
| Indole peptidomimetic | S1, S2, Glu166 | 518 | 1.8 | Moderate aqueous solubility |
| Benzimidazole | Glu166, His163 | 391 | 2.5 | High membrane permeability |

---

## 8. Example Results — EGFR (P00533)

| Property | Value |
|---|---|
| Molecular Weight | 134,277.0 Da |
| Isoelectric Point | pH 6.77 |
| Sequence Length | 1,210 amino acids |
| Druggability | Large receptor kinase — ATP pocket characterised for CADD |

**Proposed Drug Scaffolds:**

| Scaffold | Targets | MW (Da) | logP | ADMET |
|---|---|---|---|---|
| 4-Anilinoquinazoline | Lys745, Met793 | 446 | 3.2 | Good oral absorption |
| Pyrimidine-acrylamide (3rd gen) | Cys797, Met793 | 499 | 3.8 | T790M-selective |
| Macrocyclic inhibitor | Lys745, Asp855, Met793 | 612 | 4.1 | Beyond Ro5 — BCS class II |

---

## 9. Key Design Decisions

**Local-first AI:** Using Ollama with Llama3 means the pipeline runs fully offline, requires no API keys, and has no usage costs — critical for an academic/internship context.

**Real data, not hallucinations:** Agent 2 is explicitly instructed to use the `ncbi_protein_fetcher` tool and never estimate biophysical values. The `fetch_ncbi_data_dict` function provides structured numeric data independently for reliable database storage.

**Upsert pattern:** `INSERT OR REPLACE` on `accession_id` means re-running a protein updates its row cleanly without creating duplicates.

**JSON scaffold extraction:** The Reporter agent is prompted with a concrete JSON template. The output is parsed using a regex that tolerates surrounding prose, with a graceful fallback to placeholder scaffolds if parsing fails.

**Separation of pipeline and GUI:** The pipeline (`bio_analyst_agent.py`) and dashboard (`dashboard.py`) are fully decoupled — the GUI reads only from SQLite, so it can be launched at any time without re-running the agents.

---

## 10. Limitations and Future Work

| Limitation | Potential Enhancement |
|---|---|
| Fixed target (hardcoded at top of file) | GUI input field to enter any accession ID and trigger pipeline |
| Sequential agent execution (2–5 min) | Async/parallel agent runs for independent tasks |
| Llama3 scaffold proposals are AI-estimated | Integration with RDKit for actual molecular structure validation |
| Single database | Multi-project support with selectable database files |
| No export | PDF/CSV export of protein profiles and scaffold tables |
| No structure visualisation | PyMOL or Py3Dmol integration for 3D binding site rendering |

---

## 11. Conclusion

The Bio-Analyst Agent demonstrates how multi-agent AI architectures can meaningfully accelerate early-stage drug discovery research. By combining CrewAI's agent orchestration, BioPython's sequence analysis, real NCBI data, and a local LLM, the system delivers a complete protein-to-scaffold pipeline that previously would have required hours of manual work across multiple tools and databases.

The project establishes a strong foundation that can be extended toward full computational drug design workflows, including structure-based virtual screening, ADMET prediction, and molecular docking.

---

*Bio-Analyst Agent | Internship Project | 2026*
