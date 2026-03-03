# =============================================================================
# FILE: bio_analyst_agent.py
# PROJECT: Bio-Analyst Agent — Multi-Agent Bio-Discovery Pipeline
#
# HOW IT WORKS:
#   Agent 1 (Researcher)   → literature knowledge on the target protein
#   Agent 2 (Data Analyst) → fetches NCBI sequence, calculates MW + pI
#   Agent 3 (Reporter)     → synthesises findings + proposes 3 drug scaffolds
#   Output                 → saved to bio_discovery.db  (view with: python3 gui.py)
#
# HOW TO RUN:
#   source "../venv/bin/activate"     (the root BioProject venv)
#   python bio_analyst_agent.py
#
# Then open the GUI:
#   /opt/homebrew/bin/python3.12 gui.py
# =============================================================================

import json
import re
from datetime import datetime

from crewai import Agent, Task, Crew, Process
from langchain_community.chat_models import ChatOllama

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.ncbi_tool import ncbi_protein_fetcher, fetch_ncbi_data_dict
from database import initialise_database, save_protein, save_scaffolds, log_run


# =============================================================================
# SECTION A: CONFIGURATION
# =============================================================================

TARGET_PROTEIN = "Mpro SARS-CoV-2 main protease"
NCBI_ACCESSION = "P0DTD1"
ENTREZ_EMAIL   = "student@bioresearch.com"
OLLAMA_MODEL   = "llama3"   # alternatives: "mistral", "phi3"
TEMPERATURE    = 0.1
VERBOSE        = True


# =============================================================================
# SECTION B: CONNECT TO OLLAMA
# =============================================================================

print("=" * 60)
print("  Bio-Analyst Agent | Multi-Agent Bio-Discovery Pipeline")
print(f"  Target   : {TARGET_PROTEIN}")
print(f"  NCBI ID  : {NCBI_ACCESSION}")
print(f"  AI Model : Ollama / {OLLAMA_MODEL} — 100% FREE, runs locally")
print("=" * 60 + "\n")

local_llm = ChatOllama(
    model=OLLAMA_MODEL,
    base_url="http://localhost:11434",
    temperature=TEMPERATURE,
)
print(f"✅ Connected to Ollama ({OLLAMA_MODEL}).\n")


# =============================================================================
# SECTION C: INITIALISE DATABASE
# =============================================================================

init_db()


# =============================================================================
# SECTION D: DEFINE THE THREE AGENTS
# =============================================================================

researcher_agent = Agent(
    role="Senior Structural Biology Researcher",
    goal=(
        f"Provide a detailed structural and functional analysis of {TARGET_PROTEIN}. "
        f"Focus on: catalytic residues, binding pocket geometry, known inhibitor classes, "
        f"and ADMET considerations from published research."
    ),
    backstory=(
        "You are a computational biologist with 10 years experience in "
        "structure-based drug design. You have published papers on coronavirus "
        "protease inhibitors and write clearly for a biochemistry audience."
    ),
    tools=[],
    llm=local_llm,
    verbose=VERBOSE,
    allow_delegation=False,
    max_iter=3,
)

data_analyst_agent = Agent(
    role="Bioinformatics Data Analyst",
    goal=(
        f"Use the ncbi_protein_fetcher tool with input '{NCBI_ACCESSION}' to fetch "
        f"the protein sequence for {TARGET_PROTEIN}. Then interpret the results: "
        f"molecular weight, isoelectric point, top amino acids, and druggability."
    ),
    backstory=(
        "You are a bioinformatics engineer specialising in protein sequence analysis. "
        "You always use available tools to get REAL data rather than estimating."
    ),
    tools=[ncbi_protein_fetcher],
    llm=local_llm,
    verbose=VERBOSE,
    allow_delegation=False,
    max_iter=4,
)

reporter_agent = Agent(
    role="Drug Discovery Report Writer",
    goal=(
        "Synthesise all findings from the previous agents. Write a clear discovery "
        "report with a target summary, 3 drug scaffold proposals with rationale, "
        "and a valid JSON array of scaffold data for database storage."
    ),
    backstory=(
        "You are a medicinal chemist and scientific writer bridging wet-lab biology "
        "with computational drug design. You always include valid JSON in your output."
    ),
    tools=[],
    llm=local_llm,
    verbose=VERBOSE,
    allow_delegation=False,
    max_iter=4,
)


# =============================================================================
# SECTION E: DEFINE THE THREE TASKS
# =============================================================================

task_research = Task(
    description=(
        f"Research the protein target: **{TARGET_PROTEIN}**\n\n"
        f"Cover these 5 points in a numbered list:\n"
        f"  1. FUNCTION: Role in the virus life cycle\n"
        f"  2. DISEASE LINK: Why it is a valuable drug target\n"
        f"  3. BINDING SITE: Key catalytic residues (e.g. His41-Cys145 for Mpro)\n"
        f"  4. KNOWN INHIBITORS: At least 2 inhibitor chemical classes\n"
        f"  5. ADMET CONCERNS: Main challenges for drug-like molecules\n\n"
        f"2-4 sentences per point. Use specific residue names and chemical terms."
    ),
    agent=researcher_agent,
    expected_output=(
        "A numbered list (1-5) covering protein function, disease relevance, "
        "catalytic residues, known inhibitor classes, and ADMET considerations."
    ),
)

task_analysis = Task(
    description=(
        f"Fetch and analyse the sequence for {TARGET_PROTEIN}.\n\n"
        f"STEP 1 — Use the ncbi_protein_fetcher tool with input: '{NCBI_ACCESSION}'\n\n"
        f"STEP 2 — Interpret the returned data:\n"
        f"   A. Molecular weight — within the typical enzyme range (20-100 kDa)?\n"
        f"   B. Isoelectric point — charge at physiological pH 7.4?\n"
        f"   C. Top 5 amino acids — active site chemistry implications?\n"
        f"   D. Overall druggability assessment.\n\n"
        f"Always use the REAL numbers from the tool. Do not guess."
    ),
    agent=data_analyst_agent,
    expected_output=(
        "A data report with raw numbers (MW, pI, sequence length) from the tool "
        "followed by written interpretation of A through D."
    ),
    context=[task_research],
)

task_report = Task(
    description=(
        "Write the final Bio-Discovery Report using ALL findings from previous tasks.\n\n"
        "## SECTION A — Target Summary (3-4 sentences)\n\n"
        "## SECTION B — 3 Drug Scaffold Proposals\n"
        "For each scaffold:\n"
        "  - Name (alpha-ketoamide, indole, benzimidazole, etc.)\n"
        "  - Binding residues targeted and mechanism\n"
        "  - ADMET strengths\n"
        "  - One specific optimisation suggestion\n\n"
        "## SECTION C — JSON DATA BLOCK (REQUIRED)\n"
        "Output a valid JSON array with exactly 3 scaffold objects:\n\n"
        "```json\n"
        "[\n"
        "  {\n"
        '    "scaffold_name": "alpha-ketoamide",\n'
        '    "target_residues": "Cys145, His41",\n'
        '    "mechanism": "covalent inhibition",\n'
        '    "estimated_mw_da": 450,\n'
        '    "predicted_logP": 2.1,\n'
        '    "admet_flag": "good oral bioavailability",\n'
        '    "optimisation_note": "add fluorine to improve metabolic stability"\n'
        "  },\n"
        "  { ...second scaffold... },\n"
        "  { ...third scaffold... }\n"
        "]\n"
        "```"
    ),
    agent=reporter_agent,
    expected_output=(
        "Section A (target summary), Section B (3 scaffolds), "
        "Section C (valid JSON array with exactly 3 scaffold objects)."
    ),
    context=[task_research, task_analysis],
)


# =============================================================================
# SECTION F: ASSEMBLE AND RUN THE CREW
# =============================================================================

crew = Crew(
    agents=[researcher_agent, data_analyst_agent, reporter_agent],
    tasks=[task_research, task_analysis, task_report],
    verbose=VERBOSE,
)

print("🚀 Starting pipeline — this may take 2-5 minutes...\n")
print("-" * 60)

# Ensure tables exist before we run
initialise_database()

crew_result       = crew.kickoff()
final_output_text = str(crew_result)

# Re-fetch NCBI data to get clean numeric values for the database
ncbi_data = fetch_ncbi_data_dict(NCBI_ACCESSION, ENTREZ_EMAIL)

# Pull researcher agent text for extracting structured fields
researcher_text = str(task_research.output) if hasattr(task_research, "output") else ""


def _extract(text: str, keyword: str, chars: int = 350) -> str:
    """Pulls the sentence block containing a keyword from free-form agent text."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if keyword.lower() in line.lower():
            return " ".join(lines[i: i + 4]).strip()[:chars]
    return "See terminal output for full details."


def parse_and_save(output_text: str, ncbi: dict, researcher: str) -> None:
    """Parses agent output and saves everything to bio_research.db."""
    print("\n" + "=" * 55)
    print("  Saving results to bio_research.db ...")

    # Extract JSON scaffold array from reporter output
    scaffolds = []
    match = re.search(r'\[\s*\{.*?\}\s*\]', output_text, re.DOTALL)
    if match:
        try:
            scaffolds = json.loads(match.group())
            print(f"  ✅ Parsed {len(scaffolds)} scaffold(s)")
        except json.JSONDecodeError:
            print("  ⚠️  JSON parse failed — saving placeholder scaffolds")
    if not scaffolds:
        scaffolds = [
            {"scaffold_name": f"Scaffold {i+1} — re-run for full data",
             "target_residues": "N/A", "mechanism": "N/A",
             "estimated_mw_da": 0, "predicted_logP": 0,
             "admet_flag": "N/A", "optimisation_note": output_text[:100]}
            for i in range(3)
        ]

    protein_data = {
        "accession_id":            NCBI_ACCESSION,
        "target_description":      TARGET_PROTEIN,
        "protein_name":            ncbi.get("protein_name", TARGET_PROTEIN),
        "sequence_length":         ncbi.get("sequence_length", 0),
        "molecular_weight_da":     ncbi.get("molecular_weight_da", 0.0),
        "isoelectric_point":       ncbi.get("isoelectric_point_pi", 0.0),
        "top_5_amino_acids":       ncbi.get("top_5_amino_acids", ""),
        "druggability_note":       ncbi.get("druggability_note", ""),
        "disease_link":            _extract(researcher, "disease"),
        "binding_site_residues":   _extract(researcher, "binding"),
        "known_inhibitor_classes": _extract(researcher, "inhibitor"),
        "admet_concerns":          _extract(researcher, "admet"),
        "run_date":                datetime.now().strftime("%Y-%m-%d"),
        "ai_model_used":           OLLAMA_MODEL,
    }

    ok1 = save_protein(protein_data)
    ok2 = save_scaffolds(scaffolds, NCBI_ACCESSION)
    log_run(NCBI_ACCESSION, "success" if (ok1 and ok2) else "partial",
            f"model={OLLAMA_MODEL}")

    print(f"  Protein  : {'✓' if ok1 else '✗'}")
    print(f"  Scaffolds: {'✓' if ok2 else '✗'}")
    print(f"\n  Launch dashboard:  /opt/homebrew/bin/python3.12 dashboard.py")
    print("=" * 55)


parse_and_save(final_output_text, ncbi_data, researcher_text)

print("\n" + "=" * 60)
print("  FULL AGENT REPORT")
print("=" * 60)
print(final_output_text)
print("\n✅  Pipeline complete!")

