"""docs/og.png: the picture shown when someone shares a link to the site (texts, X, Slack...).

Rebuilt every morning with that morning's numbers. Never shows a single pick: just how many bets beat what's
expected, how many matches were compared, and the record so far. Drawn with Pillow and the DejaVu fonts that
come with matplotlib, so it needs nothing extra installed.
"""
from __future__ import annotations

from pathlib import Path

W, H = 1200, 630
BG, INK, MUTED, LINE, BLUE, GREEN, RED = "#111111", "#f2f2f2", "#a8a8a8", "#333333", "#6ea8fe", "#3ecf6e", "#f08a80"


def _font(name: str, size: int):
    import matplotlib
    from PIL import ImageFont
    return ImageFont.truetype(str(Path(matplotlib.get_data_path()) / "fonts" / "ttf" / name), size)


def _usd(x: float) -> str:
    return f"{'+' if x >= 0 else '−'}${abs(x):,.0f}"


def build(path: Path, n_bets: int, n_matches: int, n_sites: int, profit: float | None, expected: float | None,
          date: str) -> None:
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    sans, bold, mono = (lambda s: _font("DejaVuSans.ttf", s)), (lambda s: _font("DejaVuSans-Bold.ttf", s)), \
        (lambda s: _font("DejaVuSansMono-Bold.ttf", s))
    d.text((72, 62), f"UPDATED {date.upper()}", font=bold(22), fill=BLUE)
    d.text((72, 98), "Today's Soccer Bets", font=bold(68), fill=INK)
    # three boxes
    top, bottom, x0, x1 = 276, 446, 72, W - 72
    d.rounded_rectangle((x0, top, x1, bottom), radius=10, outline=LINE, width=2)
    cols = [(str(n_bets), INK, ["bets paying more", "than they should"]),
            (str(n_matches), INK, ["matches compared", f"at {n_sites} sites"])]
    if profit is not None:
        cols.append((_usd(profit), GREEN if profit >= 0 else RED,
                     ["profit so far, $100 a bet", f"({_usd(expected)} expected)" if expected is not None else ""]))
    w = (x1 - x0) / len(cols)
    for i, (v, color, lab) in enumerate(cols):
        x = x0 + i * w
        if i:
            d.line((x, top, x, bottom), fill=LINE, width=2)
        d.text((x + 30, top + 26), v, font=mono(54), fill=color)
        for j, line in enumerate(lab):
            d.text((x + 30, top + 102 + j * 28), line, font=sans(21), fill=MUTED)
    d.text((72, 540), "todayssoccerbets.com", font=sans(20), fill="#8a8a8a")
    t = "21+ · 1-800-GAMBLER"
    d.text((W - 72 - d.textlength(t, font=sans(20)), 540), t, font=sans(20), fill="#8a8a8a")
    im.save(path, optimize=True)
