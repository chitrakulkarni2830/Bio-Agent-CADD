# 🧬 Bio-Analyst Agent — AI Drug Target Discovery Pipeline

> An autonomous multi-agent system that fetches real protein data from NCBI, analyses biophysical properties, proposes drug scaffolds using a local AI model, and visualises results in a desktop GUI — entirely free and offline.

---

## What It Does

Given a protein accession ID (e.g. `P0DTD1` for SARS-CoV-2 Mpro), the pipeline:

1. **Researches** the protein — biological function, disease link, key binding residues, known inhibitor classes, ADMET concerns
2. **Fetches real sequence data** from NCBI — molecular weight, isoelectric point, sequence length, top amino acids
3. **Proposes 3 drug scaffold candidates** — with mechanism, estimated MW, predicted logP, ADMET flags, and optimisation tips
4. **Saves all results** to a local SQLite database (`bio_research.db`)
5. **Displays everything** in a polished Tkinter dashboard with animated metric tiles and scaffold cards

---

## Project Structure

```text
bio_analyst_agent/
├── scripts/
│   ├── bio_analyst_agent.py   # Main pipeline — runs the 3-agent CrewAI crew
│   ├── database.py            # SQLite read/write layer
│   └── verify_setup.py        # Quick dependency check script
├── ui/
│   ├── app.py                 # Unified Tkinter app with run panel & log
│   ├── dashboard.py           # Primary GUI dashboard
│   └── gui.py                 # Alternate results browser GUI
├── data/
│   └── bio_research.db        # SQLite database (auto-created)
├── docs/
│   ├── README.md              # Project documentation
│   └── project_report.md      # Comprehensive project report
├── tools/
│   └── ncbi_tool.py           # NCBI fetch + BioPython analysis tool
└── requirements.txt           # Python dependencies
```

---

## Setup

### Prerequisites

- **Python 3.10–3.12** (recommended: 3.12)
- **Ollama** installed and running locally → [ollama.com](https://ollama.com)
- **Llama3 model** pulled in Ollama

```bash
# Pull the AI model (one-time, ~4 GB)
ollama pull llama3

# Start Ollama (if not already running)
ollama serve
```

### Install Dependencies

```bash
cd bio_analyst_agent
pip install -r requirements.txt
```

`requirements.txt` includes:
- `crewai==0.63.6` — multi-agent orchestration
- `langchain-community` — Ollama LLM adapter
- `biopython>=1.83` — NCBI access + sequence analysis
- `pandas>=2.0.0` — data handling
- `pydantic>=2.0.0` — data validation

### Seed Sample Data (Optional)

To populate the database with example proteins (SARS-CoV-2 Mpro + EGFR) without running the full AI pipeline:

```bash
python scripts/database.py
```

---

## Running

### Step 1 — Run the AI Pipeline

```bash
python scripts/bio_analyst_agent.py
```

This runs the full 3-agent pipeline. Expect **2–5 minutes** on first run. Results are saved to `data/bio_research.db`.

> **Note:** Requires Ollama running with `llama3` loaded. The target protein and NCBI accession ID are set at the top of `scripts/bio_analyst_agent.py` — edit `TARGET_PROTEIN` and `NCBI_ACCESSION` to analyse a different protein.

### Step 2 — Launch the Dashboard

```bash
python ui/app.py
# or, on Mac with system Python:
/opt/homebrew/bin/python3.12 ui/app.py
```

The GUI opens immediately. Select a protein from the left sidebar to see its full profile and drug scaffold proposals, or use the top bar to run a new analysis directly.

---

## The Three Agents

| Agent | Role | Tools |
|---|---|---|
| **Researcher** | Structural biology expert — covers function, disease-link, binding site, inhibitor classes, ADMET | None (LLM knowledge) |
| **Data Analyst** | Bioinformatics engineer — fetches real NCBI sequence data | `ncbi_protein_fetcher` |
| **Reporter** | Medicinal chemist — synthesises findings, proposes 3 scaffolds, outputs structured JSON | None (LLM knowledge) |

Agents run **sequentially**: Researcher → Data Analyst (with Researcher context) → Reporter (with both).

---

## Dashboard Features

- **Sidebar** — scrollable list of all analysed proteins
- **Metric tiles** — Molecular Weight, Isoelectric Point, Sequence Length with count-up animation
- **Science fields** — Disease Link, Binding Site Residues, Known Inhibitor Classes, ADMET Concerns
- **Drug Scaffold Cards** — staggered reveal animation, mechanism chip, MW/logP/ADMET data chips, optimisation note
- **Fade-in window** + pulsing status dot
- **Refresh button** — reload from database without restarting

---

## Changing the Target Protein

Edit the configuration block at the top of `scripts/bio_analyst_agent.py`:

```python
TARGET_PROTEIN = "EGFR Epidermal Growth Factor Receptor"
NCBI_ACCESSION = "P00533"
OLLAMA_MODEL   = "llama3"   # or "mistral", "phi3"
```

Then re-run `python scripts/bio_analyst_agent.py`.

---

## Database Schema

**`proteins`** — one row per protein target  
**`scaffolds`** — three rows per protein (drug scaffold proposals)  
**`run_log`** — audit trail of every pipeline run  

Running the same accession ID twice updates the existing row (no duplicates).

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Connection refused` on Ollama | Run `ollama serve` in a terminal |
| `model not found` | Run `ollama pull llama3` |
| NCBI fetch fails | Check internet connection; verify accession at [ncbi.nlm.nih.gov/protein](https://www.ncbi.nlm.nih.gov/protein/) |
| Dashboard shows "No proteins yet" | Run `python scripts/database.py` to seed sample data |
| Python version error | Use Python 3.10–3.12 |

---

## License

Academic / internship project. Not for clinical or commercial use.
