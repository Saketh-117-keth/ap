"""
app.py - AP Grid Quantum Optimiser (Flask version, read-only dashboard)

Reads results.json and serves a dark control-room dashboard. It does NOT run the
QAOA solver, so it is fast and fits on free hosting. Money is shown in Indian rupees.

Local:   python app.py          ->  http://127.0.0.1:5000
Deploy:  gunicorn -b 0.0.0.0:7860 app:app
"""
import json
import os

from flask import Flask, jsonify, Response, abort

APP_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_PATH = os.path.join(APP_DIR, "results.json")

# ---- Edit these labels to match your engine (schedule rows = units, columns = blocks) ----
GEN_NAMES = ["Unit 1", "Unit 2", "Unit 3", "Unit 4"]
BLOCKS = ["00-06", "06-12", "12-18", "18-24"]
SCENARIO_LABELS = {"base": "Base", "heat": "Heat wave", "cloudy": "Cloudy"}

app = Flask(__name__)


def load_results():
    """Read results.json fresh each time so an updated file shows without a restart."""
    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def inr_lakh(v):
    """Rs lakh -> readable rupees, e.g. 541.65 -> 'Rs 541.65 L (Rs 5.42 Cr)'."""
    s = f"₹{v:,.2f} L"
    if v >= 100:
        s += f" (₹{v / 100:,.2f} Cr)"
    return s


@app.route("/")
def index():
    return Response(PAGE, mimetype="text/html")


@app.route("/health")
def health():
    return jsonify(status="ok")


@app.route("/api/meta")
def api_meta():
    res = load_results()
    return jsonify(gens=GEN_NAMES, blocks=BLOCKS,
                   scenarios=[{"key": k, "label": SCENARIO_LABELS.get(k, k.title())} for k in res])


@app.route("/api/summary")
def api_summary():
    """All scenarios with money pre-formatted in rupees."""
    res = load_results()
    out = {}
    for k, v in res.items():
        out[k] = dict(v)
        out[k]["cost_inr"] = inr_lakh(v["cost_lakh"])
        out[k]["milp_inr"] = inr_lakh(v["milp_lakh"])
        out[k]["extra_over_milp_inr"] = inr_lakh(v["cost_lakh"] - v["milp_lakh"])
    return jsonify(out)


@app.route("/api/scenario/<name>")
def api_scenario(name):
    res = load_results()
    if name not in res:
        abort(404, description=f"Unknown scenario '{name}'. Available: {', '.join(res)}")
    return jsonify(res[name])


PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AP Grid Quantum Optimiser</title>
<style>
:root{--bg:#0a0c10;--panel:#0d1117;--line:#1e2a38;--fg:#e2e8f0;--mut:#8b949e;
--blue:#388bfd;--green:#3fb950;--amber:#d29922;--red:#f85149}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-family:Inter,system-ui,Segoe UI,Arial,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:16px}
.banner{background:linear-gradient(135deg,#0d1117,#161b22 60%,#0d1b2a);border:1px solid var(--line);
border-radius:12px;padding:20px 24px;margin-bottom:16px}
.banner h1{margin:0;font-size:1.5rem}.banner p{margin:4px 0 0;color:var(--mut);font-size:.8rem}
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}
.tab{background:var(--panel);color:var(--mut);border:1px solid var(--line);border-radius:8px;
padding:8px 16px;cursor:pointer;font-size:.85rem}
.tab.on{color:#f0f6fc;border-color:var(--blue)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:16px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.kpi .l{font-size:.7rem;color:var(--mut);letter-spacing:.8px;text-transform:uppercase}
.kpi .v{font-size:1.5rem;font-weight:700;font-family:Consolas,monospace;margin-top:4px}
.kpi .d{font-size:.72rem;margin-top:4px;color:var(--mut)}
.good{color:var(--green)}.warn{color:var(--amber)}.bad{color:var(--red)}
h2{font-size:.75rem;color:var(--mut);letter-spacing:1.2px;text-transform:uppercase;
border-bottom:1px solid var(--line);padding-bottom:6px;margin:22px 0 12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.85rem}
th{color:var(--mut);font-size:.68rem;letter-spacing:.8px;text-transform:uppercase;text-align:left;
padding:8px 12px;border-bottom:1px solid var(--line)}
td{padding:8px 12px;border-bottom:1px solid #161b22;font-family:Consolas,monospace}
tr.cur td{background:#0f1f0f}
.pill{display:inline-block;border-radius:20px;padding:2px 12px;font-size:.72rem;font-weight:600}
.on{background:#1a3624;color:var(--green);border:1px solid #196c2e}
.off{background:#161b22;color:#6e7681;border:1px solid #30363d}
.note{color:var(--mut);font-size:.78rem;margin-top:18px;line-height:1.5}
.err{background:#1c0e0e;border:1px solid #5c1212;color:#f85149;padding:12px;border-radius:8px}
svg text{fill:#c9d1d9;font-size:11px;font-family:Consolas,monospace}
</style></head><body><div class="wrap">
<div class="banner"><h1>&#9889; AP Grid Quantum Optimiser</h1>
<p>Hybrid QAOA unit commitment &middot; benchmarked against classical MILP &middot; all amounts in Indian rupees</p></div>
<div class="tabs" id="tabs"></div>
<div id="app">Loading&hellip;</div>
<p class="note">Cost = QAOA schedule + LP dispatch. Gap = how much more it costs than the exact MILP optimum;
0% means the quantum schedule matched the classical best. At this problem size there is no quantum-advantage claim.
1 lakh = 100,000; 100 lakh = 1 crore.</p>
</div>
<script>
let META=null, DATA=null, CUR=null;
const fmt=(n,d=2)=>Number(n).toLocaleString('en-IN',{minimumFractionDigits:d,maximumFractionDigits:d});
const rs=v=>'₹'+fmt(v)+' L'+(v>=100?' (₹'+fmt(v/100)+' Cr)':'');
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

async function init(){
  try{
    const [m,d]=await Promise.all([fetch('/api/meta').then(r=>r.json()),fetch('/api/summary').then(r=>r.json())]);
    META=m;DATA=d;CUR=m.scenarios[0].key;
    document.getElementById('tabs').innerHTML=m.scenarios.map(s=>
      `<div class="tab" data-k="${esc(s.key)}">${esc(s.label)}</div>`).join('');
    document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{CUR=t.dataset.k;render()});
    render();
  }catch(e){document.getElementById('app').innerHTML='<div class="err">Could not load results.json: '+esc(e)+'</div>'}
}
function label(k){return META.scenarios.find(s=>s.key===k).label}
function render(){
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('on',t.dataset.k===CUR));
  const s=DATA[CUR], base=DATA[META.scenarios[0].key];
  const gapCls=s.gap_pct<0.5?'good':(s.gap_pct<3?'warn':'bad');
  const unCls=s.unserved_mwh===0?'good':'bad';
  const dBase=CUR===META.scenarios[0].key?'reference scenario':
    ((s.cost_lakh-base.cost_lakh)>=0?'+':'')+fmt(s.cost_lakh-base.cost_lakh)+' L vs '+label(META.scenarios[0].key);
  let h=`<div class="kpis">
   <div class="kpi"><div class="l">QAOA + LP cost</div><div class="v">₹${fmt(s.cost_lakh)} L</div><div class="d">${s.cost_lakh>=100?'₹'+fmt(s.cost_lakh/100)+' crore &middot; ':''}${dBase}</div></div>
   <div class="kpi"><div class="l">Classical MILP</div><div class="v">₹${fmt(s.milp_lakh)} L</div><div class="d">exact benchmark</div></div>
   <div class="kpi"><div class="l">Gap to MILP</div><div class="v ${gapCls}">${fmt(s.gap_pct)}%</div><div class="d">extra ₹${fmt(s.cost_lakh-s.milp_lakh)} L</div></div>
   <div class="kpi"><div class="l">CO₂ emissions</div><div class="v">${fmt(s.emissions_t,0)} t</div><div class="d">across all blocks</div></div>
   <div class="kpi"><div class="l">Unserved</div><div class="v ${unCls}">${fmt(s.unserved_mwh,0)} MWh</div><div class="d">curtailed ${fmt(s.curtail_mwh,0)} MWh</div></div>
  </div>`;
  // schedule
  h+=`<h2>Unit commitment schedule &mdash; ${esc(label(CUR))}</h2><div class="card"><table><thead><tr><th>Unit</th>`+
     META.blocks.map(b=>`<th>${esc(b)}</th>`).join('')+`</tr></thead><tbody>`;
  s.schedule.forEach((row,i)=>{
    h+=`<tr><td><b>${esc(META.gens[i]||('Unit '+(i+1)))}</b></td>`+
       row.map(v=>`<td><span class="pill ${v?'on':'off'}">${v?'ON':'off'}</span></td>`).join('')+`</tr>`;
  });
  h+=`</tbody></table></div>`;
  // chart
  h+=`<h2>Cost by scenario (₹ lakh): QAOA vs MILP</h2><div class="card">${chart()}</div>`;
  // comparison table
  h+=`<h2>All scenarios</h2><div class="card"><table><thead><tr><th>Scenario</th><th>QAOA cost</th><th>MILP cost</th><th>Gap</th><th>CO₂ (t)</th><th>Unserved (MWh)</th></tr></thead><tbody>`;
  META.scenarios.forEach(sc=>{const r=DATA[sc.key];
    h+=`<tr class="${sc.key===CUR?'cur':''}"><td><b>${esc(sc.label)}</b></td><td>${rs(r.cost_lakh)}</td><td>${rs(r.milp_lakh)}</td><td>${fmt(r.gap_pct)}%</td><td>${fmt(r.emissions_t,0)}</td><td>${fmt(r.unserved_mwh,0)}</td></tr>`});
  h+=`</tbody></table></div>`;
  document.getElementById('app').innerHTML=h;
}
function chart(){
  const sc=META.scenarios, W=640,H=240,L=54,B=34,T=14, mx=Math.max(...sc.map(x=>Math.max(DATA[x.key].cost_lakh,DATA[x.key].milp_lakh)))*1.1;
  const gw=(W-L-10)/sc.length, bw=gw*0.28, y=v=>T+(H-T-B)*(1-v/mx);
  let g='';
  for(let i=0;i<=4;i++){const v=mx*i/4;g+=`<line x1="${L}" x2="${W-10}" y1="${y(v)}" y2="${y(v)}" stroke="#1e2a38"/><text x="${L-6}" y="${y(v)+4}" text-anchor="end">${fmt(v,0)}</text>`}
  sc.forEach((x,i)=>{const r=DATA[x.key],cx=L+gw*i+gw/2;
    g+=`<rect x="${cx-bw-2}" y="${y(r.cost_lakh)}" width="${bw}" height="${H-B-y(r.cost_lakh)}" fill="#388bfd"><title>${esc(x.label)} QAOA ₹${fmt(r.cost_lakh)} L</title></rect>
        <rect x="${cx+2}" y="${y(r.milp_lakh)}" width="${bw}" height="${H-B-y(r.milp_lakh)}" fill="#3fb950"><title>${esc(x.label)} MILP ₹${fmt(r.milp_lakh)} L</title></rect>
        <text x="${cx}" y="${H-B+16}" text-anchor="middle">${esc(x.label)}</text>`});
  g+=`<rect x="${L}" y="${H-12}" width="10" height="10" fill="#388bfd"/><text x="${L+14}" y="${H-3}">QAOA + LP</text>
      <rect x="${L+100}" y="${H-12}" width="10" height="10" fill="#3fb950"/><text x="${L+114}" y="${H-3}">Classical MILP</text>`;
  return `<svg viewBox="0 0 ${W} ${H+4}" width="100%" role="img" aria-label="Cost by scenario">${g}</svg>`;
}
init();
</script></body></html>"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=False)
