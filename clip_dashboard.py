#!/usr/bin/env python3
"""
Build output/clips/dashboard.html from every output/clips/<video_id>/ folder
(clips.json + snippets.json written by clip_picker.py). Re-run after each batch.

Open the HTML file directly in a browser. Decisions (keep/skip/maybe + notes) are
saved in the browser and can be exported to JSON with the Export button.
"""
import glob
import json
import os
import sqlite3

OUT_ROOT = "./output/clips"
DB = "./output/competitive_analysis.db"


def titles():
    try:
        c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        return {v: (t, w) for v, t, w in c.execute("select video_id,title,view_count from videos")}
    except Exception:
        return {}


def main():
    meta = titles()
    videos = []
    for d in sorted(glob.glob(os.path.join(OUT_ROOT, "*", "clips.json"))):
        vid = os.path.basename(os.path.dirname(d))[-11:]  # folders are <date>_<title>_<id>
        sn = os.path.join(os.path.dirname(d), "snippets.json")
        if not os.path.exists(sn):
            continue
        title, views = meta.get(vid, (vid, None))
        videos.append({"id": vid, "title": title, "views": views,
                       "clips": json.load(open(d, encoding="utf-8")),
                       "snips": json.load(open(sn, encoding="utf-8"))})
    data = json.dumps(videos, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.replace("/*DATA*/[]", data)
    out = os.path.join(OUT_ROOT, "dashboard.html")
    open(out, "w", encoding="utf-8").write(html)
    print(f"Wrote {out} ({len(videos)} videos)")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Clip Review</title>
<style>
:root{--bg:#f7f7f5;--panel:#fff;--ink:#1b1b1a;--mute:#6b6b66;--line:#e2e2dc;--accent:#1f5fd1;
--keep:#1d7a46;--skip:#b3382c;--maybe:#a8741a;--hl:#fff3c4}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#151514;--panel:#1e1e1c;--ink:#ecece8;
--mute:#9a9a92;--line:#2f2f2b;--accent:#6ea0ff;--keep:#4cc585;--skip:#ef7c70;--maybe:#e0b04f;--hl:#4a3f12}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif}
.app{display:grid;grid-template-columns:280px 1fr;min-height:100vh}
@media(max-width:800px){.app{grid-template-columns:1fr}}
aside{border-right:1px solid var(--line);padding:16px;overflow:auto;max-height:100vh;position:sticky;top:0}
@media(max-width:800px){aside{max-height:none;position:static;border:0}}
h1{font-size:16px;margin:0 0 12px}
.vid{padding:8px 10px;border-radius:8px;cursor:pointer;margin-bottom:4px;border:1px solid transparent}
.vid:hover{background:var(--panel)}.vid.on{background:var(--panel);border-color:var(--line)}
.vid b{display:block;font-weight:600;font-size:13px}.vid small{color:var(--mute)}
main{padding:20px 24px;max-width:980px}
.bar{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 16px;align-items:center}
button,.btn{font:inherit;font-size:13px;padding:5px 11px;border-radius:7px;border:1px solid var(--line);
background:var(--panel);color:var(--ink);cursor:pointer;text-decoration:none}
button:hover{border-color:var(--accent)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:12px}
.card.keep{border-left:4px solid var(--keep)}.card.skip{border-left:4px solid var(--skip);opacity:.7}
.card.maybe{border-left:4px solid var(--maybe)}
.hook{font-weight:650;font-size:16px;margin:2px 0}.meta{color:var(--mute);font-size:12px}
.txt{margin:8px 0;white-space:pre-wrap}
.row{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.row .sel.keep{background:var(--keep);color:#fff;border-color:var(--keep)}
.row .sel.skip{background:var(--skip);color:#fff;border-color:var(--skip)}
.row .sel.maybe{background:var(--maybe);color:#fff;border-color:var(--maybe)}
textarea{width:100%;margin-top:8px;font:inherit;font-size:13px;padding:6px 8px;border-radius:7px;
border:1px solid var(--line);background:var(--bg);color:var(--ink);resize:vertical}
h2{font-size:14px;margin:24px 0 8px;color:var(--mute);text-transform:uppercase;letter-spacing:.04em}
.script{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;max-height:60vh;overflow:auto}
.ln{display:flex;gap:10px;padding:1px 0}.ln i{color:var(--mute);font-style:normal;font-size:12px;min-width:44px;padding-top:2px}
.ln.hl{background:var(--hl);border-radius:4px}
.empty{color:var(--mute);padding:40px 0}
</style></head><body>
<div class="app"><aside><h1>Clip review</h1><div id="list"></div></aside>
<main id="main"></main></div>
<script>
const DATA=/*DATA*/[];
const KEY="clipReview.v1";
let store={};try{store=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(store))}catch(e){}};
const k=(v,i)=>v.id+"#"+i;
const fmt=t=>{t=Math.floor(t);const h=Math.floor(t/3600),m=Math.floor(t/60)%60,s=t%60;
 return (h?h+":":"")+String(m).padStart(h?2:1,"0")+":"+String(s).padStart(2,"0")};
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
let cur=0;
function counts(v){let c={keep:0,skip:0,maybe:0};v.clips.forEach((_,i)=>{const d=(store[k(v,i)]||{}).d;if(d)c[d]++});return c}
function renderList(){
 document.getElementById("list").innerHTML=DATA.map((v,n)=>{const c=counts(v),done=c.keep+c.skip+c.maybe;
  return `<div class="vid ${n==cur?"on":""}" onclick="cur=${n};render()"><b>${esc(v.title)}</b>
  <small>${v.views??"?"} views · ${done}/${v.clips.length} reviewed · ${c.keep} keep</small></div>`}).join("")
  ||'<div class="empty">No clips yet. Run clip_picker.py, then clip_dashboard.py.</div>'}
function render(){
 renderList();const v=DATA[cur];const m=document.getElementById("main");
 if(!v){m.innerHTML="";return}
 const hl=new Set();
 v.snips.forEach((s,j)=>v.clips.forEach(c=>{if(s.end>c.start&&s.start<c.end)hl.add(j)}));
 m.innerHTML=`<h1 style="font-size:20px">${esc(v.title)}</h1>
 <div class="bar"><a class="btn" target="_blank" href="https://youtu.be/${v.id}">Open video</a>
 <button onclick="exportJson()">Export decisions</button>
 <span class="meta">Decisions save in this browser. Export to keep a copy or to render the kept clips.</span></div>
 ${v.clips.map((c,i)=>{const s=store[k(v,i)]||{};
  return `<div class="card ${s.d||""}" id="c${i}"><div class="meta">Moment ${i+1} · ${fmt(c.start)} to ${fmt(c.end)} · ${c.dur}s · heuristic ${c.score}</div>
  ${c.hook?`<div class="hook">${esc(c.hook)}</div>`:""}${c.why?`<div class="meta">${esc(c.why)}</div>`:""}
  <div class="txt">${esc(c.text)}</div>
  <div class="row">
   <a class="btn" target="_blank" href="https://youtu.be/${v.id}?t=${Math.floor(c.start)}">Watch from here</a>
   <button onclick="jump(${i})">Show in script</button>
   ${["keep","maybe","skip"].map(d=>`<button class="sel ${s.d==d?d:""}" onclick="setD(${i},'${d}')">${d[0].toUpperCase()+d.slice(1)}</button>`).join("")}
   <button onclick="copyCmd(${i})">Copy render command</button></div>
  <textarea rows="2" placeholder="What do you think? Better hook, trim, why skip..." oninput="setN(${i},this.value)">${esc(s.n||"")}</textarea></div>`}).join("")}
 <h2>Script (chosen moments highlighted)</h2>
 <div class="script" id="script">${v.snips.map((s,j)=>`<div class="ln ${hl.has(j)?"hl":""}" data-t="${s.start}"><i>${fmt(s.start)}</i><span>${esc(s.text)}</span></div>`).join("")}</div>`}
function setD(i,d){const v=DATA[cur],key=k(v,i);store[key]=store[key]||{};store[key].d=store[key].d==d?"":d;save();const y=scrollY;render();scrollTo(0,y)}
function setN(i,n){const v=DATA[cur],key=k(v,i);store[key]=store[key]||{};store[key].n=n;save()}
function jump(i){const c=DATA[cur].clips[i],box=document.getElementById("script");
 const el=[...box.children].find(e=>+e.dataset.t>=c.start-0.5);if(el){box.scrollTop=el.offsetTop-box.offsetTop-20;scrollTo(0,box.offsetTop-60)}}
function copyCmd(i){const v=DATA[cur];const t=`python clip_picker.py ${v.id} --render SOURCE.mp4 --pick ${i+1}`;
 navigator.clipboard&&navigator.clipboard.writeText(t)}
function exportJson(){const out=[];DATA.forEach(v=>v.clips.forEach((c,i)=>{const s=store[k(v,i)];
 if(s&&(s.d||s.n))out.push({video_id:v.id,title:v.title,moment:i+1,start:c.start,end:c.end,hook:c.hook||"",decision:s.d||"",note:s.n||""})}));
 const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,1)],{type:"application/json"}));
 a.download="clip_decisions.json";a.click()}
render();
</script></body></html>"""

if __name__ == "__main__":
    main()
