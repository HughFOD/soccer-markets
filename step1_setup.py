"""Step 1 (once): create .venv and install everything. Click the green ▶ next to
`if __name__ == "__main__":` at the bottom."""
import subprocess
import sys
import venv
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

if __name__ == "__main__":
    if sys.version_info < (3, 10):
        sys.exit("Needs Python 3.10 or newer.")
    if not PY.exists():
        venv.create(HERE / ".venv", with_pip=True)
    subprocess.check_call([str(PY), "-m", "pip", "install", "-q", "--upgrade", "pip"])
    subprocess.check_call([str(PY), "-m", "pip", "install", "-r", str(HERE / "requirements.txt")])
    print("\n✅ Setup complete. Now run step2_download_more_data.py (optional) or step3_run_analysis.py.")
