"""Step 6: this week's fair prices. Downloads the latest odds for upcoming matches from
football-data.co.uk, prices every match, and writes docs/this-week.html. Run it whenever
you want fresh prices (the site updates them twice a week). Click the green ▶ below."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

if __name__ == "__main__":
    subprocess.check_call([str(PY), "-m", "markets.weekly"], cwd=HERE)
    print("\n✅ Open docs/this-week.html in a browser.")
