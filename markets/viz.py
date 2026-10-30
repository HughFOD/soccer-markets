"""Interactive charts for the research page.

Each chart is a small JSON spec embedded in the page. A short script (JS below)
draws it as SVG at the width of its container, so text stays full size on phones,
colours follow the page's light/dark theme, and hovering or tapping shows the
exact numbers. Every chart also has a "Show the numbers" table.

Chart types: hbar (horizontal bars), vbar (vertical bars), line, scatter.
Number formats: usd (+$5 per $100), usdk (thousands of dollars), pct, pctS (signed %), pct1.
"""
from __future__ import annotations

import html
import json

import pandas as pd

CSS = """
.chart{margin:14px 0 8px}
.chart h4{font-size:19px;line-height:1.25;font-weight:600;margin:0 0 4px;color:var(--ink);letter-spacing:-.015em}
.chart .csub{font-size:14px;color:var(--muted);margin:0 0 12px;line-height:1.4}
.chart .plot{position:relative;width:100%;touch-action:pan-y}
.chart svg{display:block;overflow:visible}
.chart svg text{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Helvetica Neue",Helvetica,Arial,sans-serif}
.chart .tip{position:absolute;pointer-events:none;background:var(--ink);color:var(--bg);font-size:13px;line-height:1.35;
  padding:7px 11px;border-radius:10px;box-shadow:0 4px 18px rgba(0,0,0,.18);white-space:nowrap;opacity:0;transition:opacity .1s;z-index:2}
.chart .tip b{font-weight:700}
.chart details{margin-top:8px}.chart summary{font-size:14px;color:var(--link);cursor:pointer}
.chart details table{font-size:.86rem}
"""

JS = r"""
(function(){
const NS='http://www.w3.org/2000/svg';
function el(t,a,p){const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);if(p)p.appendChild(e);return e}
function txt(p,x,y,s,a){const t=el('text',Object.assign({x:x,y:y},a||{}),p);t.textContent=s;return t}
const ctx=document.createElement('canvas').getContext('2d');
function tw(s,size,bold){ctx.font=(bold?'700 ':'400 ')+size+'px -apple-system,BlinkMacSystemFont,"Helvetica Neue",Helvetica,Arial,sans-serif';return ctx.measureText(s).width}
function F(v,f){const r=Math.round(v),a=Math.abs(r);
  if(f==='usd')return r<0?'−$'+a:r>0?'+$'+a:'$0';
  if(f==='usdk')return r<0?'−$'+a.toLocaleString()+'k':r>0?'+$'+a.toLocaleString()+'k':'$0';
  if(f==='pct')return r+'%';
  if(f==='pctS')return r<0?'−'+a+'%':r>0?'+'+a+'%':'0%';
  if(f==='pct1')return v.toFixed(1)+'%';
  return String(v)}
function tf(f){return f==='pct1'?'pct':f}
/* nice axis: returns {lo,hi,t:[ticks]} covering [lo,hi], about n ticks, rounded outward */
function axis(lo,hi,n){if(lo===hi){hi=lo+1}const span=hi-lo;let st=Math.pow(10,Math.floor(Math.log10(span/Math.max(n,1))));
  const e=span/Math.max(n,1)/st;if(e>=7.5)st*=10;else if(e>=3.5)st*=5;else if(e>=1.5)st*=2;
  const L=Math.floor(lo/st+1e-9)*st,H=Math.ceil(hi/st-1e-9)*st,t=[];for(let v=L;v<=H+st*1e-6;v+=st)t.push(+v.toFixed(8));return {lo:L,hi:H,t}}
function col(c){return c==='b'?'var(--c2)':'var(--c1)'}
const AX=13, VAL=14, PAD=6;
function tipper(box){const tip=document.createElement('div');tip.className='tip';box.appendChild(tip);
  return {show(h,x,y){tip.innerHTML=h;tip.style.opacity=1;const W=box.clientWidth,w=tip.offsetWidth,ht=tip.offsetHeight;
      let L=x+12;if(L+w>W)L=Math.max(0,x-w-12);let T=y-ht-10;if(T<0)T=y+14;tip.style.left=L+'px';tip.style.top=T+'px'},
    hide(){tip.style.opacity=0}}}
function hover(g,svg,tp,h){g.addEventListener('pointermove',e=>{const r=svg.getBoundingClientRect();tp.show(h,e.clientX-r.left,e.clientY-r.top)});
  g.addEventListener('pointerleave',()=>tp.hide());g.addEventListener('pointerdown',e=>{const r=svg.getBoundingClientRect();tp.show(h,e.clientX-r.left,e.clientY-r.top)})}
function xTicks(svg,ax,sc,y,f,x0,x1){/* draw value ticks along a horizontal axis without overlap or clipping */
  let last=-1e9;ax.t.forEach(t=>{const s=F(t,f),w=tw(s,AX-1),X=sc(t);if(X-w/2<x0-PAD-20||X+w/2>x1+PAD+20)return;
    if(X-w/2<last+10)return;last=X+w/2;txt(svg,X,y,s,{'text-anchor':'middle','font-size':AX-1,style:'fill:var(--axis)'})})}

function hbar(svg,s,W,tp){
  const n=s.values.length,f=s.fmt;
  const labW=Math.max(...s.labels.map(l=>tw(l,AX)))+12;
  const stacked=labW>W*0.36;                       /* narrow screens: label above each bar */
  const rowH=stacked?46:(W<520?30:34),top=4;
  const lo0=Math.min(0,...s.values),hi0=Math.max(0,...s.values);
  const vw=Math.max(...s.values.map(v=>tw(F(v,f),VAL,true)))+10;
  const edge=tw(F(0,f),AX-1)/2+2,x0=Math.max((stacked?0:labW)+(lo0<0?vw:0),edge),x1=W-Math.max(hi0>0?vw+PAD:0,edge,PAD);
  const ax=axis(lo0,hi0,Math.max(2,Math.floor((x1-x0)/80)));
  const lo=Math.min(lo0,ax.lo<lo0&&lo0<0?ax.lo:lo0),hi=Math.max(hi0,ax.hi>hi0&&hi0>0?ax.hi:hi0);
  const sc=v=>x0+(v-lo)/((hi-lo)||1)*(x1-x0);
  const H=top+n*rowH+26;svg.setAttribute('height',H);
  ax.t.filter(t=>t>=lo-1e-9&&t<=hi+1e-9).forEach(t=>el('line',{x1:sc(t),x2:sc(t),y1:top,y2:top+n*rowH,style:'stroke:var(--grid)'},svg));
  xTicks(svg,{t:ax.t.filter(t=>t>=lo-1e-9&&t<=hi+1e-9)},sc,top+n*rowH+18,f,x0,x1);
  s.values.forEach((v,i)=>{const y=top+i*rowH,bh=stacked?16:rowH*0.62,by=stacked?y+rowH-bh-6:y+(rowH-bh)/2,a=sc(Math.min(v,0)),b=sc(Math.max(v,0));
    const g=el('g',{},svg);el('rect',{x:0,y:y,width:W,height:rowH,fill:'transparent'},g);
    el('rect',{x:a,y:by,width:Math.max(b-a,1.5),height:bh,rx:3,style:'fill:'+col((s.colors||[])[i])},g);
    if(stacked)txt(g,v<0?sc(0):sc(0),by-6,s.labels[i],{'text-anchor':v<0?'end':'start','font-size':AX,style:'fill:var(--ink2)'});
    else txt(g,labW-10,y+rowH/2+4.5,s.labels[i],{'text-anchor':'end','font-size':AX,style:'fill:var(--ink2)'});
    txt(g,v<0?a-6:b+6,by+bh/2+5,F(v,f),{'text-anchor':v<0?'end':'start','font-size':VAL,'font-weight':700,style:'fill:var(--ink)'});
    hover(g,svg,tp,'<b>'+s.labels[i]+'</b><br>'+F(v,f)+(s.unit?' '+s.unit:'')+(s.notes?'<br>'+s.notes[i]:''))});
  const z=sc(0);el('line',{x1:z,x2:z,y1:top-2,y2:top+n*rowH,style:'stroke:var(--ink)','stroke-width':1.2},svg)}

function vbar(svg,s,W,tp){
  const n=s.values.length,f=s.fmt,mob=W<520,H=mob?290:330,lines=Math.max(...s.labels.map(l=>l.split('\n').length));
  const bot=14+lines*16,top=26;
  const ax=axis(Math.min(0,...s.values),Math.max(0,...s.values),mob?4:5);
  const yl=Math.max(...ax.t.map(t=>tw(F(t,tf(f)),AX-1)))+10,x0=yl,x1=W-PAD;
  const sy=v=>top+(ax.hi-v)/((ax.hi-ax.lo)||1)*(H-top-bot);
  svg.setAttribute('height',H);
  ax.t.forEach(t=>{const Y=sy(t);el('line',{x1:x0,x2:x1,y1:Y,y2:Y,style:'stroke:var(--grid)'},svg);
    txt(svg,x0-8,Y+4,F(t,tf(f)),{'text-anchor':'end','font-size':AX-1,style:'fill:var(--axis)'})});
  const cw=(x1-x0)/n;
  s.values.forEach((v,i)=>{const cx=x0+cw*(i+.5),bw=Math.min(cw*0.62,72),a=sy(Math.max(v,0)),b=sy(Math.min(v,0));
    const g=el('g',{},svg);el('rect',{x:cx-cw/2,y:0,width:cw,height:H,fill:'transparent'},g);
    el('rect',{x:cx-bw/2,y:a,width:bw,height:Math.max(b-a,1.5),rx:3,style:'fill:'+col((s.colors||[])[i])},g);
    txt(g,cx,v<0?b+18:a-7,F(v,f),{'text-anchor':'middle','font-size':VAL,'font-weight':700,style:'fill:var(--ink)'});
    s.labels[i].split('\n').forEach((ln,k)=>txt(g,cx,H-bot+22+k*16,ln,{'text-anchor':'middle','font-size':AX,style:'fill:var(--ink2)'}));
    hover(g,svg,tp,'<b>'+s.labels[i].replace('\n',' ')+'</b><br>'+F(v,f)+(s.unit?' '+s.unit:'')+(s.notes?'<br>'+s.notes[i]:''))});
  const Z=sy(0);el('line',{x1:x0,x2:x1,y1:Z,y2:Z,style:'stroke:var(--ink)','stroke-width':1.2},svg)}

function line(svg,s,W,tp){
  const mob=W<520,H=mob?270:320,top=24,bot=30,n=s.x.length,f=s.fmt;
  const all=[].concat(...s.series.map(q=>q.values)).filter(v=>v!=null);
  let lo=Math.min(...all),hi=Math.max(...all);if(s.zero){lo=Math.min(lo,0);hi=Math.max(hi,0)}
  if(s.from0)lo=0;
  if(s.zero&&hi>0&&hi<(hi-lo)*0.04)hi=0;
  const ax=axis(lo,hi,mob?4:5);
  const yl=Math.max(...ax.t.map(t=>tw(F(t,tf(f)),AX-1)))+10;
  const endW=Math.max(0,...s.series.map(q=>q.name?tw(q.name,AX,true)+12:0));
  const lastTick=s.ticks.filter(t=>t).slice(-1)[0]||'';
  const markW=Math.max(0,...s.series.map(q=>(q.mark||[]).includes(n-1)?tw(F(q.values[n-1],f),VAL,true)+14:0));
  const x0=yl,x1=W-Math.max(endW,markW,tw(lastTick,AX-1)/2+PAD,PAD+4);
  const sx=i=>x0+i/(n-1)*(x1-x0),sy=v=>top+(ax.hi-v)/((ax.hi-ax.lo)||1)*(H-top-bot);
  svg.setAttribute('height',H);
  ax.t.forEach(t=>{const Y=sy(t);el('line',{x1:x0,x2:x1,y1:Y,y2:Y,style:'stroke:var(--grid)'},svg);
    txt(svg,x0-8,Y+4,F(t,tf(f)),{'text-anchor':'end','font-size':AX-1,style:'fill:var(--axis)'})});
  if(s.zero&&ax.lo<0){const Z=sy(0);el('line',{x1:x0,x2:x1,y1:Z,y2:Z,style:'stroke:var(--ink)','stroke-width':1.2},svg)}
  const cand=s.ticks.map((t,i)=>[i,t]).filter(p=>p[1]);const gap=Math.max(...cand.map(p=>tw(p[1],AX-1)))+22;
  const every=Math.max(1,Math.ceil(gap/((x1-x0)/Math.max(cand.length,1))));
  cand.forEach(([i,t],k)=>{if(k%every)return;txt(svg,sx(i),H-bot+20,t,{'text-anchor':'middle','font-size':AX-1,style:'fill:var(--axis)'})});
  const ends=[];
  s.series.forEach(q=>{let d='';q.values.forEach((v,i)=>{if(v==null)return;d+=(d?'L':'M')+sx(i).toFixed(1)+','+sy(v).toFixed(1)});
    el('path',{d:d,fill:'none','stroke-width':2.5,'stroke-linejoin':'round','stroke-linecap':'round',style:'stroke:'+col(q.color)},svg);
    if(q.name)ends.push({y:sy(q.values[n-1]),q:q});
    (q.mark||[]).forEach(i=>{const X=sx(i),Y=sy(q.values[i]);el('circle',{cx:X,cy:Y,r:4.5,style:'fill:'+col(q.color)+';stroke:var(--card)','stroke-width':2},svg);
      txt(svg,i===0?X+8:X+8,i===0?Y-10:Y+5,F(q.values[i],f),{'text-anchor':'start','font-size':VAL,'font-weight':700,style:'fill:var(--ink)'})})});
  ends.sort((a,b)=>a.y-b.y);for(let i=1;i<ends.length;i++)if(ends[i].y-ends[i-1].y<18)ends[i].y=ends[i-1].y+18;
  ends.forEach(e=>txt(svg,x1+8,e.y+4.5,e.q.name,{'font-size':AX,'font-weight':700,style:'fill:'+col(e.q.color)}));
  const cross=el('line',{y1:top,y2:H-bot,style:'stroke:var(--axis);opacity:0','stroke-dasharray':'3 3'},svg);
  const dots=s.series.map(q=>el('circle',{r:4.5,style:'fill:'+col(q.color)+';stroke:var(--card);opacity:0','stroke-width':2},svg));
  const hit=el('rect',{x:x0-6,y:0,width:x1-x0+12,height:H,fill:'transparent'},svg);
  function at(e){const r=svg.getBoundingClientRect(),px=e.clientX-r.left;
    const i=Math.max(0,Math.min(n-1,Math.round((px-x0)/(x1-x0)*(n-1)))),X=sx(i);
    cross.setAttribute('x1',X);cross.setAttribute('x2',X);cross.style.opacity=1;
    let h='<b>'+s.x[i]+'</b>';s.series.forEach((q,k)=>{const v=q.values[i];if(v==null)return;
      dots[k].setAttribute('cx',X);dots[k].setAttribute('cy',sy(v));dots[k].style.opacity=1;
      h+='<br>'+(q.name?q.name+': ':'')+F(v,f)});
    tp.show(h,X,e.clientY-r.top)}
  hit.addEventListener('pointermove',at);hit.addEventListener('pointerdown',at);
  hit.addEventListener('pointerleave',()=>{tp.hide();cross.style.opacity=0;dots.forEach(d=>d.style.opacity=0)})}

function scatter(svg,s,W,tp){
  const mob=W<520,top=10,bot=46;
  const ax=axis(0,Math.max(...s.points.map(p=>Math.max(p[0],p[1])))+3,mob?4:7),max=ax.hi;
  const yl=tw(F(max,'pct'),AX-1)+30,x0=yl,x1=W-tw(F(max,'pct'),AX-1)/2-PAD,H=Math.min(x1-x0,mob?330:420)+top+bot;
  const sx=v=>x0+v/max*(x1-x0),sy=v=>top+(max-v)/max*(H-top-bot);
  svg.setAttribute('height',H);
  ax.t.forEach(t=>{el('line',{x1:x0,x2:x1,y1:sy(t),y2:sy(t),style:'stroke:var(--grid)'},svg);
    el('line',{x1:sx(t),x2:sx(t),y1:top,y2:H-bot,style:'stroke:var(--grid)'},svg);
    txt(svg,x0-8,sy(t)+4,F(t,'pct'),{'text-anchor':'end','font-size':AX-1,style:'fill:var(--axis)'});
    txt(svg,sx(t),H-bot+18,F(t,'pct'),{'text-anchor':'middle','font-size':AX-1,style:'fill:var(--axis)'})});
  txt(svg,(x0+x1)/2,H-6,s.xlab,{'text-anchor':'middle','font-size':AX,style:'fill:var(--ink2)'});
  const yt=txt(svg,0,0,s.ylab,{'text-anchor':'middle','font-size':AX,style:'fill:var(--ink2)'});
  yt.setAttribute('transform','translate(12,'+((top+H-bot)/2)+') rotate(-90)');
  el('line',{x1:sx(0),y1:sy(0),x2:sx(max),y2:sy(max),style:'stroke:var(--axis)','stroke-dasharray':'5 4','stroke-width':1.3},svg);
  const lt=txt(svg,0,0,s.diag,{'text-anchor':'middle','font-size':AX-1,style:'fill:var(--axis)'});
  const ang=-Math.atan2(sy(0)-sy(max),sx(max)-sx(0))*180/Math.PI,mx=sx(max*0.78),my=sy(max*0.78)+16;
  lt.setAttribute('transform','translate('+mx+','+my+') rotate('+ang+')');
  s.points.forEach(p=>{const g=el('g',{},svg);el('circle',{cx:sx(p[0]),cy:sy(p[1]),r:14,fill:'transparent'},g);
    el('circle',{cx:sx(p[0]),cy:sy(p[1]),r:5.5,style:'fill:var(--c1);stroke:var(--card)','stroke-width':2},g);
    hover(g,svg,tp,s.tip.replace('{x}',F(p[0],'pct')).replace('{y}',F(p[1],'pct')).replace('{n}',(p[2]||0).toLocaleString()))})}

const KINDS={hbar,vbar,line,scatter};
function init(){document.querySelectorAll('.chart[data-spec]').forEach(c=>{
  const s=JSON.parse(document.getElementById(c.dataset.spec).textContent),box=c.querySelector('.plot'),tp=tipper(box);
  let w0=0;function draw(){const W=Math.round(box.clientWidth);if(!W||W===w0)return;w0=W;box.querySelectorAll('svg').forEach(x=>x.remove());
    const svg=el('svg',{width:W,role:'img','aria-label':s.alt||''});box.insertBefore(svg,box.firstChild);KINDS[s.type](svg,s,W,tp)}
  draw();new ResizeObserver(draw).observe(box);
  if(document.fonts)document.fonts.ready.then(()=>{w0=0;draw()})})}
init();
})();
"""


def _american(dec: float) -> str:
    return f"+{100 * (dec - 1):.0f}" if dec >= 2 else f"−{100 / (dec - 1):.0f}"


def band_label(band: str) -> str:
    """Decimal odds band like '1.5–2' -> American odds label like '−200 to +100'."""
    s = band.replace("–", "-").replace("+", "").strip()
    try:
        lo, hi = (float(x) for x in s.split("-")) if "-" in s else (float(s), None)
    except ValueError:
        return band
    if hi is None:
        return f"{_american(lo)} or longer"
    if lo <= 1.01:
        return f"{_american(hi)} or shorter"
    return f"{_american(lo)} to {_american(hi)}"


def _usd(x: float) -> float:
    return round(100 * x, 2)


def _table(head: list[str], rows: list[list[str]]) -> str:
    h = "".join(f"<th{' class=num' if i else ''}>{html.escape(c)}</th>" for i, c in enumerate(head))
    b = "".join("<tr>" + "".join(f"<td{' class=num' if i else ''}>{html.escape(str(c))}</td>" for i, c in enumerate(r)) + "</tr>"
                for r in rows)
    return f"<details><summary>Show the numbers</summary><div class=tw><table><tr>{h}</tr>{b}</table></div></details>"


def chart(cid: str, title: str, sub: str, spec: dict, table: str = "") -> str:
    spec = dict(spec, alt=title)
    data = json.dumps(spec, separators=(",", ":")).replace("</", "<\\/")
    return (f'<div class=chart data-spec="spec-{cid}"><h4>{html.escape(title)}</h4><p class=csub>{html.escape(sub)}</p>'
            f'<div class=plot></div>{table}<script type="application/json" id="spec-{cid}">{data}</script></div>')


def _sd(v: float) -> str:
    r = round(v)
    return f"−${-r}" if r < 0 else (f"+${r}" if r > 0 else "$0")


# ---------------- the eight research charts ----------------

def calibration(table: list) -> str:
    t = pd.DataFrame(table)
    pts = [[round(100 * a, 1), round(100 * b, 1), int(n)] for a, b, n in
           zip(t["priced"], t["happened"], t.get("n", pd.Series([0] * len(t))))]
    mx = 10 * (int(max(max(p[0], p[1]) for p in pts) // 10) + 1)
    rows = [[f"{p[0]:.0f}%", f"{p[1]:.0f}%", f"{p[2]:,}"] for p in pts]
    return chart("calibration", "When the odds say 40%, it happens about 40% of the time",
                 "Each dot is a group of results with similar odds. Dots on the dashed line mean the odds were exactly right.",
                 {"type": "scatter", "points": pts, "max": mx, "xlab": "chance the odds gave it", "ylab": "how often it happened",
                  "diag": "odds exactly right", "tip": "Odds said <b>{x}</b><br>Happened <b>{y}</b> of the time<br>{n} results"},
                 _table(["Odds said", "Happened", "Results"], rows))


def longshot(avg: list) -> str:
    t = pd.DataFrame(avg)
    labels = [band_label(b) for b in t["odds"]]
    vals = [_usd(r) for r in t["return"]]
    notes = [f"{int(n):,} bets" for n in t["bets"]] if "bets" in t else None
    return chart("longshot", "The longer the odds, the more you lose",
                 "Average result of a $100 bet on every result in each odds range, at a typical bookmaker's price",
                 {"type": "hbar", "labels": labels, "values": vals, "fmt": "usd", "unit": "per $100 bet", "notes": notes},
                 _table(["Odds", "Won or lost per $100"], [[l, _sd(v)] for l, v in zip(labels, vals)]))


def margins(mg: list) -> str:
    t = pd.DataFrame(mg)
    y = [round(100 * v, 2) for v in t["avg_margin"]]
    seasons = [f"{s[:4]}/{s[-2:]}" for s in t["season"]]
    return chart("margins", f"Bookmakers' cut has fallen from {y[0]:.0f}% to {y[-1]:.0f}%",
                 "The bookmaker's built-in cut on an average match, by season",
                 {"type": "line", "x": seasons, "ticks": [s[:4] for s in t["season"]], "fmt": "pct1",
                  "series": [{"values": y, "color": "a", "mark": [0, len(y) - 1]}]},
                 _table(["Season", "Cut"], [[s, f"{v:.1f}%"] for s, v in zip(seasons, y)]))


def longshot_by_season(table: list) -> str:
    t = pd.DataFrame(table)
    worse = int((t["longshot_return"] < t["fav_return"]).sum())
    sm = lambda c: [round(v, 1) for v in (100 * t[c]).rolling(3, center=True, min_periods=2).mean()]
    seasons = [f"{s[:4]}/{s[-2:]}" for s in t["season"]]
    return chart("longshot-seasons", f"Long shots were the worse bet in {worse} of {len(t)} seasons",
                 "Result of a $100 bet on every heavy favorite or every long shot (smoothed over 3 seasons)",
                 {"type": "line", "x": seasons, "ticks": [s[:4] for s in t["season"]], "fmt": "usd", "zero": True,
                  "series": [{"name": "favorites", "values": sm("fav_return"), "color": "a"},
                             {"name": "long shots", "values": sm("longshot_return"), "color": "b"}]},
                 _table(["Season", "Favorites", "Long shots"],
                        [[s, _sd(100 * a), _sd(100 * b)] for s, a, b in zip(seasons, t["fav_return"], t["longshot_return"])]))


def line_moves(moves: list, threshold: float = 0.03) -> str:
    t = pd.DataFrame(moves)
    t = t[(t["threshold"] - threshold).abs() < 1e-9].set_index("direction")
    labels = ["Chance rose", "Chance fell"]
    vals = [_usd(t.loc["shortened", "return"]), _usd(t.loc["drifted", "return"])]
    notes = [f"{int(t.loc[d, 'bets']):,} bets" for d in ("shortened", "drifted")] if "bets" in t else None
    return chart("line-moves", "Betting early pays off when the price later moves your way",
                 f"Result of a $100 bet at the opening price, split by whether the chance moved {100 * threshold:.0f}+ points before kick-off",
                 {"type": "hbar", "labels": labels, "values": vals, "colors": ["a", "b"], "fmt": "usd",
                  "unit": "per $100 bet", "notes": notes},
                 _table(["Before kick-off", "Won or lost per $100"], [[l, _sd(v)] for l, v in zip(labels, vals)]))


def value_bets(curve: pd.DataFrame) -> str:
    c = curve.copy()
    c["date"] = pd.to_datetime(c["date"])
    m = c.groupby(c["date"].dt.to_period("M")).last().reset_index(drop=True)
    x = [d.strftime("%b %Y") for d in m["date"]]
    tk = [d.strftime("%Y") if d.month == 1 else "" for d in m["date"]]
    series = [{"name": name, "values": [round(v / 10, 1) for v in m[col]], "color": color}
              for col, name, color in (("best", "best price", "b"), ("avg", "typical price", "a")) if col in m]
    end = {s["name"]: s["values"][-1] for s in series}
    return chart("value-bets", "My model's picks lost money over time",
                 "Running total from a $100 bet on every result my model rated 5%+ more likely than the odds",
                 {"type": "line", "x": x, "ticks": tk, "fmt": "usdk", "zero": True, "series": series},
                 _table(["Price", "Running total at the end"], [[k, f"{_sd(v)}k"] for k, v in end.items()]))


def score_effects(se: list) -> str:
    t = pd.DataFrame(se).sort_values("margin")
    names = {-2: "down 2+", -1: "down 1", 0: "level", 1: "up 1", 2: "up 2+"}
    labels = [names.get(int(m), str(m)).replace(" ", "\n", 1) for m in t["margin"]]
    vals = [round(100 * (r - 1), 1) for r in t["ratio"]]
    return chart("half-time", "At half-time, teams that are behind score more than expected",
                 "Second-half goals compared with what the pre-match odds predicted, by the team's score at half-time",
                 {"type": "vbar", "labels": labels, "values": vals, "colors": ["b" if v > 0 else "a" for v in vals],
                  "fmt": "pctS", "unit": "goals vs expected"},
                 _table(["At half-time", "Goals vs expected"],
                        [[l.replace("\n", " "), f"{v:+.0f}%"] for l, v in zip(labels, vals)]))


def score_checks(rb: list) -> str:
    t = pd.DataFrame(rb)
    vals = [round(100 * (r - 1), 1) for r in t["ratio"]]
    n_pos = sum(v > 0 for v in vals)
    title = "The pattern holds in every check" if n_pos == len(vals) else f"The pattern holds in {n_pos} of {len(vals)} checks"
    return chart("checks", title,
                 "How much more of the second-half scoring the trailing team got than the odds expected",
                 {"type": "hbar", "labels": list(t["check"]), "values": vals, "fmt": "pctS", "unit": "more than expected"},
                 _table(["Check", "Extra share"], [[c, f"{v:+.0f}%"] for c, v in zip(t["check"], vals)]))
