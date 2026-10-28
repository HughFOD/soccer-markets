"""Step 5: rebuild docs/index.html (the project website) from output/. Click the green ▶ below."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

if __name__ == "__main__":
    subprocess.check_call([str(PY), "-m", "markets.website"], cwd=HERE)
    print("\n✅ Website written to docs/index.html. Open it in a browser.")
