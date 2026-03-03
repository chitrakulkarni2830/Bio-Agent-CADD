# =============================================================================
# FILE: tools/ncbi_tool.py
# PURPOSE: Custom tool for Agent 2 — fetches SARS-CoV-2 Mpro sequence from
#          NCBI and calculates Molecular Weight + Isoelectric Point.
#
# COMPATIBLE WITH: crewai 0.1.32 (uses langchain @tool decorator)
# =============================================================================

from Bio import Entrez, SeqIO
from Bio.SeqUtils.ProtParam import ProteinAnalysis
from langchain.tools import tool


# =============================================================================
# TOOL: ncbi_protein_fetcher
# Used by Agent 2 (Data Analyst). Pass an NCBI accession ID like "P0DTD1".
# =============================================================================

@tool
def ncbi_protein_fetcher(input: str) -> str:
    """
    Fetches a protein sequence from NCBI using an accession ID and calculates
    its molecular weight (Da) and isoelectric point (pI).

    Input  : the NCBI accession ID string, e.g. 'P0DTD1'
    Output : a text report with sequence length, MW, pI, top amino acids,
             and a druggability note.
    """
    accession_id = input.strip()
    email        = "student@bioresearch.com"

    try:
        print(f"  [NCBI Tool] Connecting to NCBI for accession: {accession_id}")
        Entrez.email = email

        handle = Entrez.efetch(
            db="protein",
            id=accession_id,
            rettype="fasta",
            retmode="text"
        )
        record = SeqIO.read(handle, "fasta")
        handle.close()

        raw_sequence = str(record.seq)
        print(f"  [NCBI Tool] Fetched — {len(raw_sequence)} amino acids")

        # Clean: keep only standard 20 amino acids
        standard_aas  = "ACDEFGHIKLMNPQRSTVWY"
        clean_sequence = "".join(aa for aa in raw_sequence.upper()
                                 if aa in standard_aas)

        if not clean_sequence:
            return f"Error: no standard amino acids found for {accession_id}"

        analysis         = ProteinAnalysis(clean_sequence)
        molecular_weight = round(analysis.molecular_weight(), 2)
        isoelectric_point = round(analysis.isoelectric_point(), 2)
        sequence_length   = len(clean_sequence)

        aa_pcts   = analysis.get_amino_acids_percent()
        top_5     = sorted(aa_pcts.items(), key=lambda x: x[1], reverse=True)[:5]
        top_5_str = ", ".join(f"{aa}: {round(p * 100, 1)}%" for aa, p in top_5)

        druggability = (
            "Target appears druggable: MW within typical enzyme range (20–100 kDa)."
            if 20000 < molecular_weight < 100000
            else "Unusual MW — may need special delivery strategies."
        )

        print(f"  [NCBI Tool] MW={molecular_weight} Da | pI={isoelectric_point}")

        return (
            f"NCBI Results for accession: {accession_id}\n"
            f"Protein name    : {record.description}\n"
            f"Sequence length : {sequence_length} amino acids\n"
            f"Molecular weight: {molecular_weight} Da\n"
            f"Isoelectric pt  : pH {isoelectric_point}\n"
            f"Top 5 amino acids: {top_5_str}\n"
            f"Sequence preview: {raw_sequence[:60]}...\n"
            f"Druggability    : {druggability}"
        )

    except Exception as error:
        return (
            f"Error fetching {accession_id}: {error}\n"
            f"Check connection + verify ID at: https://www.ncbi.nlm.nih.gov/protein/"
        )


# =============================================================================
# RESULT DICT HELPER — used by bio_analyst_agent.py to extract numbers for DB
# =============================================================================

def fetch_ncbi_data_dict(accession_id: str, email: str = "student@bioresearch.com") -> dict:
    """
    Calls NCBI directly and returns a structured dict (for SQLite storage).
    This mirrors what the @tool function does but returns a dict, not a string.
    """
    try:
        Entrez.email = email
        handle = Entrez.efetch(db="protein", id=accession_id,
                               rettype="fasta", retmode="text")
        record = SeqIO.read(handle, "fasta")
        handle.close()

        raw_sequence = str(record.seq)
        standard_aas = "ACDEFGHIKLMNPQRSTVWY"
        clean_sequence = "".join(aa for aa in raw_sequence.upper()
                                 if aa in standard_aas)

        analysis          = ProteinAnalysis(clean_sequence)
        molecular_weight  = round(analysis.molecular_weight(), 2)
        isoelectric_point = round(analysis.isoelectric_point(), 2)
        aa_pcts  = analysis.get_amino_acids_percent()
        top_5    = sorted(aa_pcts.items(), key=lambda x: x[1], reverse=True)[:5]
        top_5_str = ", ".join(f"{aa}: {round(p*100, 1)}%" for aa, p in top_5)

        return {
            "status":               "success",
            "sequence_length":      len(clean_sequence),
            "molecular_weight_da":  molecular_weight,
            "isoelectric_point_pi": isoelectric_point,
            "top_5_amino_acids":    top_5_str,
            "druggability_note": (
                "Target appears druggable: MW within typical enzyme range (20–100 kDa)."
                if 20000 < molecular_weight < 100000
                else "Unusual MW — may need special delivery strategies."
            )
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# =============================================================================
# QUICK TEST: python tools/ncbi_tool.py
# =============================================================================
if __name__ == "__main__":
    result = ncbi_protein_fetcher.run("P0DTD1")
    print(result)
