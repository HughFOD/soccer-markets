"""Shared look for both pages: a clean, Apple-style design.

System font (San Francisco on Apple devices), white and light-grey surfaces,
large tight headlines, generous spacing, rounded tiles without borders, and a
translucent bar at the top. Light or dark follows the device setting unless the
visitor picks one with the switch in the top bar (remembered on that device).
"""
from __future__ import annotations

REPO_URL = "https://github.com/HughFOD/soccer-markets"

CSS = """
:root{--bg:#fff;--bg2:#f5f5f7;--tile:#fff;--ink:#1d1d1f;--ink2:#424245;--muted:#6e6e73;--line:#d2d2d7;--hair:#e8e8ed;
  --link:#0066cc;--blue:#0071e3;--good:#1d7c3a;--goodbg:#e9f6ec;--card:#fff;--nav:rgba(255,255,255,.72);
  --c1:#0071e3;--c2:#eb6834;--grid:#e8e8ed;--axis:#86868b;--accent:#0071e3}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#000;--bg2:#161617;--tile:#1d1d1f;--ink:#f5f5f7;--ink2:#d2d2d7;
  --muted:#a1a1a6;--line:#424245;--hair:#2c2c2e;--link:#2997ff;--blue:#0071e3;--good:#4cd964;--goodbg:#13281a;--card:#1d1d1f;
  --nav:rgba(22,22,23,.72);--c1:#2997ff;--c2:#e8590c;--grid:#2c2c2e;--axis:#86868b;--accent:#2997ff;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#000;--bg2:#161617;--tile:#1d1d1f;--ink:#f5f5f7;--ink2:#d2d2d7;
  --muted:#a1a1a6;--line:#424245;--hair:#2c2c2e;--link:#2997ff;--blue:#0071e3;--good:#4cd964;--goodbg:#13281a;--card:#1d1d1f;
  --nav:rgba(22,22,23,.72);--c1:#2997ff;--c2:#e8590c;--grid:#2c2c2e;--axis:#86868b;--accent:#2997ff;color-scheme:dark}
:root[data-theme="light"]{color-scheme:light}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.47 -apple-system,BlinkMacSystemFont,"SF Pro Text","Helvetica Neue",Helvetica,Arial,sans-serif;
  letter-spacing:-.022em;-webkit-font-smoothing:antialiased}
.wrap{max-width:980px;margin:0 auto;padding:0 22px}
a{color:var(--link);text-decoration:none}a:hover{text-decoration:underline}
h1,h2,h3,h4,.display{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Helvetica Neue",Helvetica,Arial,sans-serif}

/* top bar */
.gnav{position:sticky;top:0;z-index:10;background:var(--nav);backdrop-filter:saturate(180%) blur(20px);-webkit-backdrop-filter:saturate(180%) blur(20px);
  border-bottom:1px solid var(--hair)}
.gnav .wrap{display:flex;align-items:center;justify-content:space-between;height:48px}
.gnav .brand{font-weight:600;font-size:17px;color:var(--ink);letter-spacing:-.02em}
.gnav nav{display:flex;gap:22px;font-size:14px}.gnav nav a{color:var(--ink2)}.gnav nav a.on{color:var(--ink);font-weight:600}
.gnav nav a:hover{color:var(--ink);text-decoration:none}
.gnav .right{display:flex;align-items:center;gap:18px}
.gnav a,.gnav nav{white-space:nowrap}
@media (max-width:420px){.gnav .wrap{padding:0 14px}.gnav .brand{font-size:15px}.gnav nav{gap:12px;font-size:13px}.gnav .right{gap:8px}}
@media (max-width:370px){.gnav nav a[href^="https"]{display:none}}
.themebtn{display:flex;align-items:center;justify-content:center;width:30px;height:30px;border:0;border-radius:50%;background:transparent;
  color:var(--ink2);cursor:pointer;padding:0}
.themebtn:hover{background:var(--hair);color:var(--ink)}.themebtn svg{width:17px;height:17px;display:none}
:root:not([data-theme]) .themebtn .i-auto,:root[data-theme="light"] .themebtn .i-light,:root[data-theme="dark"] .themebtn .i-dark{display:block}

/* hero */
.hero{text-align:center;padding:72px 0 48px}
.eyebrow{font-size:17px;font-weight:600;color:#bf4800;margin:0 0 6px;letter-spacing:-.01em}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .eyebrow{color:#ff9f0a}}
:root[data-theme="dark"] .eyebrow{color:#ff9f0a}
.hero h1{font-size:clamp(40px,7vw,64px);line-height:1.06;font-weight:700;letter-spacing:-.015em;margin:0 auto 14px;max-width:860px}
.hero .lede{font-size:clamp(19px,2.4vw,24px);line-height:1.35;color:var(--muted);font-weight:500;max-width:760px;margin:0 auto;letter-spacing:.005em}
.ctas{display:flex;gap:14px;justify-content:center;flex-wrap:wrap;margin-top:26px}
.btn{display:inline-block;background:var(--blue);color:#fff;font-size:17px;padding:11px 22px;border-radius:980px}
.btn:hover{text-decoration:none;filter:brightness(1.08)}
.btn.ghost{background:transparent;color:var(--link);padding:11px 6px}.btn.ghost:after{content:" ›"}
.updated{margin-top:18px;font-size:14px;color:var(--muted)}

/* sections */
.band{background:var(--bg2);padding:64px 0}
.section{padding:64px 0}
h2{font-size:clamp(32px,4.6vw,48px);line-height:1.08;font-weight:700;letter-spacing:-.01em;margin:0 0 10px}
.sub{font-size:19px;line-height:1.42;color:var(--muted);margin:0 0 30px;max-width:720px}
h3{font-size:21px;line-height:1.2;font-weight:600;margin:0 0 6px;letter-spacing:-.015em}

/* big numbers */
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:0}
.stat{background:var(--tile);border-radius:18px;padding:24px 22px}
.band .stat{background:var(--tile)}
.stat .v{font:700 clamp(28px,3.6vw,40px)/1.05 -apple-system,BlinkMacSystemFont,"SF Pro Display",sans-serif;letter-spacing:-.02em}
.stat .l{font-size:14px;color:var(--muted);margin-top:8px;line-height:1.35}

/* tiles */
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.card{background:var(--tile);border-radius:18px;padding:28px 24px}
.card p{margin:0;color:var(--muted);font-size:16px;line-height:1.45}
.section .card,.section .stat{background:var(--bg2)}

/* tables */
.tablewrap,.tw{overflow-x:auto;background:var(--tile);border-radius:18px}
table{border-collapse:collapse;width:100%;font-size:15px}
th,td{padding:12px 16px;border-bottom:1px solid var(--hair);text-align:left;white-space:nowrap}
tr:last-child td{border-bottom:0}
th{color:var(--muted);font-weight:600;font-size:13px}
td.n,th.n,td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}

footer{background:var(--bg2);color:var(--muted);font-size:12px;line-height:1.5;padding:22px 0 34px}
footer .wrap{border-top:1px solid var(--line);padding-top:18px}
footer p{margin:0 0 6px}

@media (max-width:820px){.stats{grid-template-columns:repeat(2,1fr)}.cards{grid-template-columns:1fr}}
@media (max-width:520px){.hero{padding:48px 0 34px}.band,.section{padding:44px 0}.stat{padding:18px 16px}.gnav nav{gap:14px}
  th,td{padding:10px 10px}.card{padding:22px 18px}}
"""


def nav(active: str) -> str:
    def a(href, label, key):
        return f'<a href="{href}"{" class=on" if key == active else ""}>{label}</a>'
    return (f'<header class=gnav><div class=wrap><a class=brand href="index.html">Soccer Odds</a><div class=right><nav>'
            f'{a("index.html", "Bets", "week")}{a("best-prices.html", "Prices", "prices")}{a("research.html", "Research", "research")}'
            f'{a(REPO_URL, "Code", "code")}</nav>{THEME_BUTTON}</div></div></header>{THEME_SCRIPT}')


# Light/dark switch: cycles Automatic (follow the device) -> Light -> Dark. The choice is kept in
# this browser's localStorage; if storage is unavailable the switch still works for the visit.
THEME_BUTTON = (
    '<button class=themebtn type=button aria-label="Appearance: automatic" title="Appearance: automatic">'
    '<svg class=i-auto viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/>'
    '<path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor"/></svg>'
    '<svg class=i-light viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/>'
    '<path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
    '<svg class=i-dark viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round">'
    '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg></button>')
THEME_SCRIPT = """<script>(function(){var r=document.documentElement,b=document.querySelector('.themebtn'),
order=['auto','light','dark'],names={auto:'automatic',light:'light',dark:'dark'};
function label(m){b.setAttribute('aria-label','Appearance: '+names[m]);b.title='Appearance: '+names[m]+' (click to change)'}
var cur=r.dataset.theme||'auto';label(cur);
b.addEventListener('click',function(){cur=order[(order.indexOf(cur)+1)%3];
if(cur==='auto')delete r.dataset.theme;else r.dataset.theme=cur;label(cur);
try{cur==='auto'?localStorage.removeItem('theme'):localStorage.setItem('theme',cur)}catch(e){}})})();</script>"""


def footer() -> str:
    return (f'<footer><div class=wrap><p>Odds from The Odds API. Match history from football-data.co.uk. '
            f'Prices move constantly, so check the site before acting.</p>'
            f'<p>A data science project in Python by Hugh. This is a study of pricing, not betting advice. '
            f'<a href="{REPO_URL}">Code on GitHub</a></p></div></footer>')


HEAD = """<meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<meta name=color-scheme content="light dark">
<script>try{var t=localStorage.getItem('theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t}catch(e){}</script>"""
