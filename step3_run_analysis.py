"""Step 3: run every analysis (about a minute per 15,000 matches). Results go to output/. Click the green ▶ below."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

if __name__ == "__main__":
    subprocess.check_call([str(PY), "run.py"], cwd=HERE)
    print("\n✅ Done. Read output/report.md, then run step5_build_website.py.")
