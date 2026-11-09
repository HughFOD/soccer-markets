"""Shared look for every page: a sports stats sheet.

IBM Plex Sans for text and IBM Plex Mono for numbers (so odds and profits line
up), a black top bar, left-aligned headings ruled underneath, thin grid lines
and square corners. Light or dark follows the device setting unless the
visitor picks one with the switch in the top bar (remembered on that device).
"""
from __future__ import annotations

REPO_URL = "https://github.com/HughFOD/soccer-markets"
SITE_URL = "https://todayssoccerbets.com"
SITE_NAME = "Today's Soccer Bets"
ICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E"
        "%3Crect width='64' height='64' rx='14' fill='%230071e3'/%3E"
        "%3Cpath d='M14 44l12-12 8 8 16-18' fill='none' stroke='white' stroke-width='6' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")


def meta(path: str, title: str, desc: str) -> str:
    """Title, description, address, icon and link-preview tags for one page ("" is the homepage)."""
    import html as h
    url, t, d = f"{SITE_URL}/{path}", h.escape(title), h.escape(desc)
    return (f'<title>{t}</title><meta name=description content="{d}"><link rel=canonical href="{url}">'
            f'<link rel=icon href="{ICON}"><link rel=apple-touch-icon href="{SITE_URL}/icon.png">'
            f'<meta property=og:site_name content="{h.escape(SITE_NAME)}"><meta property=og:type content=website>'
            f'<meta property=og:url content="{url}"><meta property=og:title content="{t}">'
            f'<meta property=og:description content="{d}"><meta property=og:image content="{SITE_URL}/og.png">'
            f'<meta name=twitter:card content=summary_large_image>')

CSS = """
:root{--bg:#fff;--bg2:#f4f4f1;--tile:#fff;--ink:#141414;--ink2:#333;--muted:#666;--line:#cfcfc8;--hair:#e4e4de;
  --link:#0b5394;--blue:#0b5394;--good:#137333;--goodbg:#e6f4ea;--warn:#8a5a00;--warnbg:#fff4d6;--bad:#c5221f;--card:#fff;--nav:#141414;
  --c1:#0b5394;--c2:#d9480f;--grid:#e4e4de;--axis:#888;--accent:#0b5394;--hi:#f2b705;--r:3px;
  --sans:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#111;--bg2:#1a1a1a;--tile:#151515;--ink:#ececec;--ink2:#cfcfcf;
  --muted:#9a9a9a;--line:#333;--hair:#262626;--link:#7cb2f0;--blue:#2f6fb5;--good:#5cc97b;--goodbg:#14281a;--warn:#e0b04a;--warnbg:#2a2210;--bad:#f28b82;--card:#151515;
  --nav:#000;--c1:#7cb2f0;--c2:#f08c4a;--grid:#262626;--axis:#888;--accent:#7cb2f0;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#111;--bg2:#1a1a1a;--tile:#151515;--ink:#ececec;--ink2:#cfcfcf;
  --muted:#9a9a9a;--line:#333;--hair:#262626;--link:#7cb2f0;--blue:#2f6fb5;--good:#5cc97b;--goodbg:#14281a;--warn:#e0b04a;--warnbg:#2a2210;--bad:#f28b82;--card:#151515;
  --nav:#000;--c1:#7cb2f0;--c2:#f08c4a;--grid:#262626;--axis:#888;--accent:#7cb2f0;color-scheme:dark}
:root[data-theme="light"]{color-scheme:light}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 var(--sans);-webkit-font-smoothing:antialiased}
.wrap{max-width:980px;margin:0 auto;padding:0 22px}
a{color:var(--link);text-decoration:none}a:hover{text-decoration:underline}
h1,h2,h3,h4,.display{font-family:var(--sans)}

/* top bar */
.gnav{position:sticky;top:0;z-index:10;background:var(--nav);border-bottom:1px solid #000}
.gnav .wrap{display:flex;align-items:center;justify-content:space-between;height:48px}
.gnav .brand{font-weight:700;font-size:17px;color:#fff;margin-right:16px}.gnav .brand:hover{text-decoration:none}
.gnav nav{display:flex;gap:22px;font-size:14px}.gnav nav a{color:#bbb;padding:3px 0;border-bottom:2px solid transparent}
.gnav nav a.on{color:#fff;font-weight:600;border-bottom-color:var(--hi)}
.gnav nav a:hover{color:#fff;text-decoration:none}
.gnav .right{display:flex;align-items:center;gap:18px}
.gnav a,.gnav nav{white-space:nowrap}
@media (max-width:500px){.gnav .wrap{padding:0 14px}.gnav .brand{font-size:15px}.gnav nav{gap:12px;font-size:13px}.gnav .right{gap:8px}}
@media (max-width:620px){.gnav nav a[href^="https"],.gnav nav a[href="search.html"]{display:none}}
@media (max-width:500px){.gnav .wrap{position:relative}.gnav .themebtn{position:absolute;top:6px;right:10px}.gnav .brand{margin-right:10px}}
@media (max-width:620px){.gnav .wrap{min-width:0}.gnav .right{min-width:0;flex:1;justify-content:flex-end}.gnav nav{overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch;padding-right:2px}.gnav nav::-webkit-scrollbar{display:none}}
@media (max-width:500px){.gnav .wrap{flex-wrap:wrap;height:auto;padding:8px 14px 0}.gnav .brand{margin:0}.gnav .right{flex:1 0 100%;justify-content:flex-start}.gnav nav{flex:1;justify-content:space-between;gap:8px;padding:6px 0 8px;font-size:14px}}
.themebtn{display:flex;align-items:center;justify-content:center;width:30px;height:30px;border:0;border-radius:50%;background:transparent;
  color:#bbb;cursor:pointer;padding:0}
.themebtn:hover{background:#2a2a2a;color:#fff}.themebtn svg{width:17px;height:17px;display:none}
:root:not([data-theme]) .themebtn .i-auto,:root[data-theme="light"] .themebtn .i-light,:root[data-theme="dark"] .themebtn .i-dark{display:block}

/* hero */
.hero{padding:40px 0 22px;border-bottom:1px solid var(--line)}
.eyebrow{font-size:13px;font-weight:600;color:var(--link);margin:0 0 6px;text-transform:uppercase;letter-spacing:.06em}
.hero h1{font-size:clamp(28px,4.4vw,38px);line-height:1.15;font-weight:700;letter-spacing:-.01em;margin:0 0 10px}
.hero .lede{font-size:clamp(16px,2vw,18px);line-height:1.45;color:var(--muted);font-weight:500;margin:0}
.ctas{display:flex;gap:14px;flex-wrap:wrap;margin-top:20px}
.btn{display:inline-block;background:var(--blue);color:#fff;font-size:15px;font-weight:500;padding:9px 18px;border-radius:var(--r)}
.btn:hover{text-decoration:none;filter:brightness(1.08)}
.btn.ghost{background:transparent;color:var(--link);padding:9px 4px}.btn.ghost:after{content:" ›"}
.updated{margin-top:16px;font-size:13px;color:var(--muted);font-family:var(--mono)}
@media (max-width:520px){.hero h1{font-size:27px}.hero .lede{font-size:15px}.ctas{margin-top:14px;gap:10px}.updated{margin-top:10px;font-size:12px}}

/* sections */
.band{background:var(--bg);padding:22px 0}
.section{padding:40px 0}
h2{font-size:clamp(20px,2.6vw,24px);line-height:1.2;font-weight:700;margin:0 0 12px;padding-bottom:6px;border-bottom:2px solid var(--ink)}
.sub{font-size:16px;line-height:1.55;color:var(--ink2);margin:0 0 22px}
h3{font-size:17px;line-height:1.3;font-weight:600;margin:0 0 6px}

/* big numbers */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1px;margin:0;background:var(--line);border:1px solid var(--line)}
.stat{background:var(--tile);border-radius:0;padding:14px 16px}
.band .stat{background:var(--tile)}
.stat .v{font:600 clamp(22px,2.8vw,28px)/1.1 var(--mono);letter-spacing:-.02em}
.stat .l{font-size:12.5px;color:var(--muted);margin-top:6px;line-height:1.35}
a.stat:hover{background:var(--bg2)}

/* tiles */
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.card{background:var(--tile);border:1px solid var(--line);border-radius:var(--r);padding:22px 20px}
.card p{margin:0;color:var(--muted);font-size:16px;line-height:1.45}
.section .card,.section .stat{background:var(--tile)}

/* tables */
.tablewrap,.tw{overflow-x:auto;background:var(--tile);border:1px solid var(--line);border-radius:var(--r)}
table{border-collapse:collapse;width:100%;font-size:15px}
th,td{padding:9px 14px;border-bottom:1px solid var(--hair);text-align:left;white-space:nowrap}
tbody tr:nth-child(even) td,table tr:nth-child(even) td{background:var(--bg2)}
tr:last-child td{border-bottom:0}
th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em;background:var(--bg2)}
td.n,th.n,td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}td.n,td.num{font-family:var(--mono);font-size:14px}

footer{background:var(--bg);color:var(--muted);font-size:12px;line-height:1.5;padding:22px 0 34px}
footer .wrap{border-top:1px solid var(--line);padding-top:18px}
footer p{margin:0 0 6px}

@media (max-width:820px){.cards{grid-template-columns:1fr}}
@media (max-width:520px){.hero{padding:28px 0 18px}.band{padding:16px 0}.section{padding:30px 0}.stat{padding:12px 12px}
  th,td{padding:10px 10px}.card{padding:22px 18px}}
"""


def nav(active: str) -> str:
    def a(href, label, key):
        return f'<a href="{href}"{" class=on" if key == active else ""}>{label}</a>'
    return (f'<header class=gnav><div class=wrap><a class=brand href="index.html">{SITE_NAME}</a><div class=right><nav>'
            f'{a("index.html", "Bets", "week")}{a("results.html", "Results", "results")}{a("best-prices.html", "Odds", "prices")}{a("search.html", "Search", "search")}{a("research.html", "Research", "research")}{a("about.html", "About", "about")}'
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


# Pages are built once a day. When opened later, this hides games that have kicked off, renames the
# day tabs (Today / Tomorrow) from the current date, drops past days and updates the counts.
FRESH_JS = """<script>(function(){var now=Date.now(),f=new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York'}),
today=f.format(new Date(now)),a=today.split('-'),tom=new Date(Date.UTC(+a[0],a[1]-1,+a[2]+1)).toISOString().slice(0,10);
[].forEach.call(document.querySelectorAll('[data-ko]'),function(el){if(Date.parse(el.dataset.ko)<=now)el.remove()});
[].forEach.call(document.querySelectorAll('.daypane[data-date]'),function(p){
 var t=document.querySelector('.daytab[data-day="'+p.dataset.day+'"]'),d=p.dataset.date,n=p.querySelectorAll('[data-ko]').length;
 if(d<today||(!n&&!p.querySelector('ol.bets,.empty:not(.nomatch)'))){p.remove();if(t)t.remove();return}
 var lab=d===today?'Today':d===tom?'Tomorrow':p.dataset.label;
 if(t){t.firstChild.nodeValue=lab;var s=t.querySelector('span');if(s)s.textContent=n}
 var h=p.querySelector('.dayhead');if(h)h.textContent=lab;
 var k=0;[].forEach.call(p.querySelectorAll('.rank'),function(r){r.textContent=++k});
 var few=p.querySelector('.few'),ol=p.querySelector('ol.bets');
 if(ol&&!n){ol.remove();if(few)few.remove();var e=document.createElement('div');e.className='empty';
  e.textContent='Every bet listed for this day has kicked off.';p.appendChild(e)}
 else if(few){if(n>=5)few.remove();else few.textContent='Only '+n+' bet'+(n===1?' beats':'s beat')+" what's expected. The rest are expected to lose money, so they're left out."}});
if(!document.querySelector('.daytab[aria-selected=true]')){var t=document.querySelector('.daytab');
 if(t){t.setAttribute('aria-selected','true');[].forEach.call(document.querySelectorAll('.daypane'),function(p){p.hidden=p.dataset.day!==t.dataset.day})}}
})();</script>"""


def footer() -> str:
    return (f'<footer><div class=wrap><p>Odds from The Odds API. Match history from football-data.co.uk. '
            f'Prices move constantly, so check the site before acting.</p>'
            f'<p>A data science project in Python by Hugh O’Donnell. This is a study of pricing, not betting advice. '
            f'<a href="about.html">About</a> · <a href="{REPO_URL}">Code on GitHub</a></p></div></footer>')


HEAD = """<meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<meta name=color-scheme content="light dark">
<link rel=preconnect href="https://fonts.googleapis.com"><link rel=preconnect href="https://fonts.gstatic.com" crossorigin>
<link rel=stylesheet href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap">
<script>try{var t=localStorage.getItem('theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t}catch(e){}</script>"""
