# =============================================================================
# FILE: database.py
#
# WHAT THIS DOES:
#   Manages all read/write operations to bio_research.db (SQLite).
#
#   bio_analyst_agent.py  → calls save_protein() and save_scaffolds() to WRITE
#   dashboard.py          → calls get_all_proteins() and get_scaffolds()  to READ
#
# TABLES:
#   proteins  — one row per protein target (MW, pI, residues, etc.)
#   scaffolds — three rows per protein (drug scaffold proposals)
#   run_log   — one row per pipeline run (audit trail)
# =============================================================================

import sqlite3
from datetime import datetime

import os
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "bio_research.db")


# =============================================================================
# CREATE TABLES
# =============================================================================

def initialise_database(db_path: str = DB_PATH) -> None:
    """
    Creates the .db file and all tables on first run.
    On every subsequent run it finds existing tables and does nothing.
    """
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()

        # UNIQUE(accession_id) means running the same protein twice
        # will UPDATE the row, not create a duplicate
        c.execute("""
            CREATE TABLE IF NOT EXISTS proteins (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                accession_id            TEXT    UNIQUE NOT NULL,
                target_description      TEXT,
                protein_name            TEXT,
                sequence_length         INTEGER,
                molecular_weight_da     REAL,
                isoelectric_point       REAL,
                top_5_amino_acids       TEXT,
                druggability_note       TEXT,
                disease_link            TEXT,
                binding_site_residues   TEXT,
                known_inhibitor_classes TEXT,
                admet_concerns          TEXT,
                run_date                TEXT,
                ai_model_used           TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS scaffolds (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                protein_accession   TEXT NOT NULL,
                scaffold_name       TEXT,
                target_residues     TEXT,
                mechanism           TEXT,
                estimated_mw_da     REAL,
                predicted_logP      REAL,
                admet_flag          TEXT,
                optimisation_note   TEXT,
                run_date            TEXT,
                FOREIGN KEY (protein_accession) REFERENCES proteins(accession_id)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS run_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                accession_id  TEXT,
                timestamp     TEXT,
                status        TEXT,
                notes         TEXT
            )
        """)

        conn.commit()
    print(f"  [DB] Ready → {db_path}")


# backward-compat alias used by old code
def init_db(db_path: str = DB_PATH) -> None:
    initialise_database(db_path)


# =============================================================================
# WRITE FUNCTIONS
# =============================================================================

def save_protein(data: dict, db_path: str = DB_PATH) -> bool:
    """INSERT OR REPLACE one protein's analysis results."""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO proteins (
                    accession_id, target_description, protein_name,
                    sequence_length, molecular_weight_da, isoelectric_point,
                    top_5_amino_acids, druggability_note,
                    disease_link, binding_site_residues,
                    known_inhibitor_classes, admet_concerns,
                    run_date, ai_model_used
                ) VALUES (
                    :accession_id, :target_description, :protein_name,
                    :sequence_length, :molecular_weight_da, :isoelectric_point,
                    :top_5_amino_acids, :druggability_note,
                    :disease_link, :binding_site_residues,
                    :known_inhibitor_classes, :admet_concerns,
                    :run_date, :ai_model_used
                )
            """, data)
            conn.commit()
        print(f"  [DB] Protein saved → {data.get('accession_id')}")
        return True
    except Exception as e:
        print(f"  [DB] Error: {e}")
        return False


def save_scaffolds(scaffolds: list, protein_accession: str,
                   db_path: str = DB_PATH) -> bool:
    """Saves scaffold proposals. Deletes old ones first to avoid duplicates."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "DELETE FROM scaffolds WHERE protein_accession = ?",
                (protein_accession,)
            )
            for s in scaffolds:
                conn.execute("""
                    INSERT INTO scaffolds (
                        protein_accession, scaffold_name, target_residues,
                        mechanism, estimated_mw_da, predicted_logP,
                        admet_flag, optimisation_note, run_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    protein_accession,
                    s.get("scaffold_name", "Unknown"),
                    s.get("target_residues", ""),
                    s.get("mechanism", ""),
                    float(s.get("estimated_mw_da", 0) or 0),
                    float(s.get("predicted_logP", 0) or 0),
                    s.get("admet_flag", ""),
                    s.get("optimisation_note", ""),
                    today,
                ))
            conn.commit()
        print(f"  [DB] {len(scaffolds)} scaffold(s) saved")
        return True
    except Exception as e:
        print(f"  [DB] Scaffold error: {e}")
        return False


def log_run(accession_id: str, status: str,
            notes: str = "", db_path: str = DB_PATH) -> None:
    """Records every pipeline run for audit trail."""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO run_log (accession_id, timestamp, status, notes)"
                " VALUES (?,?,?,?)",
                (accession_id, datetime.now().isoformat(), status, notes),
            )
            conn.commit()
    except Exception as e:
        print(f"  [DB] Log error: {e}")


# =============================================================================
# READ FUNCTIONS (called by dashboard.py)
# =============================================================================

def get_all_proteins(db_path: str = DB_PATH) -> list:
    """Returns all proteins as a list of dicts, newest first."""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM proteins ORDER BY run_date DESC, id DESC"
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def get_scaffolds(accession_id: str, db_path: str = DB_PATH) -> list:
    """Returns scaffold proposals for one specific protein."""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM scaffolds WHERE protein_accession = ? ORDER BY id",
                (accession_id,),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


# =============================================================================
# SEED DATA — run this file directly to populate sample proteins for testing
# Command:  python database.py   (using the root BioProject venv)
# =============================================================================
if __name__ == "__main__":
    initialise_database()

    save_protein({
        "accession_id": "P0DTD1",
        "target_description": "Mpro SARS-CoV-2 Main Protease",
        "protein_name": "SARS-CoV-2 polyprotein [Severe acute respiratory syndrome coronavirus 2]",
        "sequence_length": 306,
        "molecular_weight_da": 33796.8,
        "isoelectric_point": 6.24,
        "top_5_amino_acids": "L: 9.2%, A: 8.5%, G: 7.8%, V: 7.1%, E: 6.4%",
        "druggability_note": "Target appears druggable: MW within enzyme range (20–100 kDa).",
        "disease_link": "Essential for SARS-CoV-2 replication. Cleaves the viral polyprotein at 11 cleavage sites, making it indispensable for the virus life cycle.",
        "binding_site_residues": "Catalytic dyad: His41 and Cys145. Pocket residues: Glu166, His163, Met165. No close human homologue — low off-target risk.",
        "known_inhibitor_classes": "Alpha-ketoamides (covalent warhead), peptidomimetics, Michael acceptors. Nirmatrelvir (Paxlovid) clinically validates this target.",
        "admet_concerns": "Metabolic stability and oral membrane permeability are primary challenges. Protease inhibitors often need formulation strategies.",
        "run_date": "2025-06-01",
        "ai_model_used": "llama3",
    })
    save_scaffolds([
        {"scaffold_name": "Alpha-ketoamide", "target_residues": "Cys145, His41",
         "mechanism": "Covalent inhibition", "estimated_mw_da": 452,
         "predicted_logP": 2.1, "admet_flag": "Good oral bioavailability",
         "optimisation_note": "Add fluorine at P3 cap to improve metabolic stability."},
        {"scaffold_name": "Indole peptidomimetic", "target_residues": "S1, S2, Glu166",
         "mechanism": "Non-covalent H-bond network", "estimated_mw_da": 518,
         "predicted_logP": 1.8, "admet_flag": "Moderate aqueous solubility",
         "optimisation_note": "Trim P2 group to reduce MW below Lipinski 500 Da limit."},
        {"scaffold_name": "Benzimidazole", "target_residues": "Glu166, His163",
         "mechanism": "Competitive inhibition", "estimated_mw_da": 391,
         "predicted_logP": 2.5, "admet_flag": "High membrane permeability",
         "optimisation_note": "Introduce steric bulk to improve selectivity vs. host proteases."},
    ], "P0DTD1")

    save_protein({
        "accession_id": "P00533",
        "target_description": "EGFR Epidermal Growth Factor Receptor",
        "protein_name": "Epidermal growth factor receptor [Homo sapiens]",
        "sequence_length": 1210,
        "molecular_weight_da": 134277.0,
        "isoelectric_point": 6.77,
        "top_5_amino_acids": "L: 10.1%, E: 8.9%, G: 7.2%, A: 6.8%, R: 6.1%",
        "druggability_note": "Large receptor kinase. ATP-binding pocket extensively characterised for CADD.",
        "disease_link": "Overexpressed or mutated in NSCLC, breast, colorectal cancers. EGFR mutations drive targeted therapy resistance (T790M, C797S).",
        "binding_site_residues": "ATP hinge: Met793. Catalytic Lys: Lys745. Gatekeeper: Thr790. Covalent anchor (3rd gen): Cys797.",
        "known_inhibitor_classes": "Quinazolines (gefitinib/erlotinib), anilino-pyrimidines (osimertinib), macrocyclic inhibitors (4th gen pipeline).",
        "admet_concerns": "Skin toxicity (rash), diarrhoea from wild-type EGFR inhibition. Mutant selectivity is critical design criterion.",
        "run_date": "2025-06-03",
        "ai_model_used": "llama3",
    })
    save_scaffolds([
        {"scaffold_name": "4-Anilinoquinazoline", "target_residues": "Lys745, Met793",
         "mechanism": "ATP-competitive", "estimated_mw_da": 446,
         "predicted_logP": 3.2, "admet_flag": "Good oral absorption",
         "optimisation_note": "C6/C7 disubstitution improves selectivity over other ErbB family members."},
        {"scaffold_name": "Pyrimidine-acrylamide (3rd gen)", "target_residues": "Cys797, Met793",
         "mechanism": "Irreversible covalent", "estimated_mw_da": 499,
         "predicted_logP": 3.8, "admet_flag": "Selective for T790M resistance mutation",
         "optimisation_note": "Tune Michael acceptor electrophilicity for mutant vs. WT selectivity."},
        {"scaffold_name": "Macrocyclic inhibitor", "target_residues": "Lys745, Asp855, Met793",
         "mechanism": "Allosteric + ATP-competitive", "estimated_mw_da": 612,
         "predicted_logP": 4.1, "admet_flag": "Beyond Ro5 — oral BCS class II",
         "optimisation_note": "Macrocyclisation reduces conformational entropy cost and improves mutant selectivity."},
    ], "P00533")

    proteins = get_all_proteins()
    print(f"\n✅ Seed done — {len(proteins)} protein(s) in database.")
    for p in proteins:
        print(f"   {p['accession_id']:10s}  MW={p['molecular_weight_da']:>10,.0f} Da  {p['target_description'][:45]}")
