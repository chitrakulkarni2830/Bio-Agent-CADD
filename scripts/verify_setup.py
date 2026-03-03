# =============================================================================
# FILE: verify_setup.py
# Run this before bio_analyst_agent.py to check everything is working.
# Usage: python verify_setup.py
# =============================================================================

print("=" * 55)
print("  Bio-Analyst Agent — Environment Check")
print("=" * 55)

errors_found = False

# ── Check 1: Python packages ──────────────────────────────────────────────────

packages_to_check = [
    ("crewai",           "CrewAI (agent framework)"),
    ("langchain_ollama", "LangChain-Ollama (local AI bridge)"),
    ("Bio",              "Biopython (NCBI + sequence analysis)"),
    ("pandas",           "Pandas (CSV export)"),
    ("pydantic",         "Pydantic (data validation)"),
]

print("\n📦 Checking Python packages:")
for module_name, label in packages_to_check:
    try:
        __import__(module_name)              # Try to import the module
        print(f"  ✅  {label}")
    except ImportError:
        # If import fails, the package is missing
        print(f"  ❌  {label}  ← MISSING!")
        print(f"      Fix: pip install {module_name.replace('_', '-')}")
        errors_found = True

# ── Check 2: Ollama is running ────────────────────────────────────────────────

print("\n🤖 Checking Ollama connection:")
try:
    import urllib.request
    # Try to reach Ollama at its default address on this machine
    urllib.request.urlopen("http://localhost:11434", timeout=3)
    print("  ✅  Ollama is running on localhost:11434")
except Exception:
    print("  ❌  Ollama is NOT running or not installed!")
    print("      Fix: Install from https://ollama.com, then start the app.")
    errors_found = True

# ── Check 3: Custom NCBI tool can be imported ─────────────────────────────────

print("\n🔬 Checking custom NCBI tool:")
try:
    from tools.ncbi_tool import NCBIProteinFetcherTool
    print("  ✅  NCBIProteinFetcherTool imported successfully")
except Exception as e:
    print(f"  ❌  Could not import NCBI tool: {e}")
    print("      Fix: Make sure you are running this from the bio_analyst_agent/ folder")
    errors_found = True

# ── Summary ───────────────────────────────────────────────────────────────────

print("\n" + "=" * 55)
if errors_found:
    print("  ⚠️  Some checks failed. Fix the issues above, then re-run.")
    print("      Full install: pip install -r requirements.txt")
else:
    print("  ✅  All checks passed! Run the pipeline with:")
    print("      python bio_analyst_agent.py")
print("=" * 55)
