"""Step 4 (optional): tests for the margin methods, calibration maths and the no-look-ahead rule. Click the green ▶ below."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

if __name__ == "__main__":
    sys.exit(subprocess.call([str(PY), "-m", "pytest", "-v"], cwd=HERE))
