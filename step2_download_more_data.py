"""Step 2 (optional): download more leagues and seasons from football-data.co.uk.

The repo ships with English Premier League and Championship data, 2000/01 to
2019/20. This adds the top divisions of Spain, Germany, Italy and France and
every season up to the current one, including 2020/21, when matches were
played without crowds. Takes a few minutes. Click the green ▶ below.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

CODE = "from pathlib import Path; from markets import data; data.download(Path('data/raw'), leagues=('E0','E1','SP1','D1','I1','F1'), first=2005, last=2025)"

if __name__ == "__main__":
    subprocess.check_call([str(PY), "-c", CODE], cwd=HERE)
    print("\n✅ Downloaded. Now run step3_run_analysis.py.")
