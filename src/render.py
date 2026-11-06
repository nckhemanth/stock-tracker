"""
Render the stock table as a static HTML page.
Mobile-friendly, dark theme, sortable columns.
"""

import json
from datetime import datetime
from pathlib import Path

from .config import OUTPUT_DIR, TEMPLATES_DIR


def render_html(stocks: list[dict], output_path: Path = None) -> str:
    """Generate the full HTML page with stock table."""
    if output_path is None:
        output_path = OUTPUT_DIR / "index.html"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    total = len(stocks)
    with_intuition = sum(1 for s in stocks if s.get("intuition_point"))
    held = sum(1 for s in stocks if s.get("i_hold"))

    rows_html = []
    for s in stocks:
        rows_html.append(_render_row(s))

    table_body = "\n".join(rows_html)
    stocks_json = json.dumps(stocks, default=str)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stock Tracker | {now}</title>
<style>
:root {{
  --bg: #0d1117; --surface: #161b22; --border: #30363d;
  --text: #e6edf3; --text-dim: #8b949e; --accent: #58a6ff;
  --green: #3fb950; --red: #f85149; --yellow: #d29922;
  --hold-bg: #1a2332;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,monospace; font-size:13px; }}
.header {{ background:var(--surface); border-bottom:1px solid var(--border); padding:12px 16px; position:sticky; top:0; z-index:100; }}
.header h1 {{ font-size:16px; font-weight:600; }}
.header .meta {{ font-size:11px; color:var(--text-dim); margin-top:4px; }}
.stats {{ display:flex; gap:16px; margin-top:6px; font-size:11px; }}
.stats span {{ background:var(--border); padding:2px 8px; border-radius:4px; }}
.filters {{ padding:8px 16px; background:var(--surface); border-bottom:1px solid var(--border); display:flex; gap:8px; flex-wrap:wrap; }}
.filters input {{ background:var(--bg); border:1px solid var(--border); color:var(--text); padding:4px 8px; border-radius:4px; font-size:12px; width:200px; }}
.filters select {{ background:var(--bg); border:1px solid var(--border); color:var(--text); padding:4px 8px; border-radius:4px; font-size:12px; }}
.table-wrap {{ overflow-x:auto; }}
table {{ border-collapse:collapse; width:100%; min-width:1600px; }}
th {{ background:var(--surface); position:sticky; top:64px; z-index:50; padding:6px 8px; text-align:left;
     font-size:11px; font-weight:600; color:var(--text-dim); border-bottom:2px solid var(--border);
     cursor:pointer; white-space:nowrap; user-select:none; }}
th:hover {{ color:var(--accent); }}
th.sorted-asc::after {{ content:" ▲"; }}
th.sorted-desc::after {{ content:" ▼"; }}
td {{ padding:5px 8px; border-bottom:1px solid var(--border); white-space:nowrap; font-size:12px; }}
tr:hover {{ background:rgba(88,166,255,0.05); }}
tr.held {{ background:var(--hold-bg); }}
.ticker {{ font-weight:700; color:var(--accent); }}
.name {{ color:var(--text-dim); max-width:160px; overflow:hidden; text-overflow:ellipsis; }}
.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
.pct {{ text-align:right; font-variant-numeric:tabular-nums; }}
.pos {{ color:var(--green); }}
.neg {{ color:var(--red); }}
.hold-yes {{ color:var(--green); font-weight:700; }}
.hold-no {{ color:var(--text-dim); }}
.score {{ display:inline-block; padding:1px 6px; border-radius:3px; font-weight:600; font-size:11px; }}
.score-high {{ background:rgba(63,185,80,0.15); color:var(--green); }}
.score-mid {{ background:rgba(210,153,34,0.15); color:var(--yellow); }}
.score-low {{ background:rgba(248,81,73,0.15); color:var(--red); }}
.intuition {{ color:var(--yellow); font-weight:600; }}
.source-badge {{ font-size:9px; padding:1px 4px; border-radius:2px; margin-left:4px; }}
.source-user {{ background:rgba(63,185,80,0.2); color:var(--green); }}
.source-algo {{ background:rgba(88,166,255,0.2); color:var(--accent); }}
.sector {{ font-size:10px; color:var(--text-dim); }}
@media (max-width:768px) {{
  .header h1 {{ font-size:14px; }}
  td, th {{ padding:4px 6px; font-size:11px; }}
  table {{ min-width:1200px; }}
}}
</style>
</head>
<body>

<div class="header">
  <h1>Stock Tracker</h1>
  <div class="meta">Last refresh: {now} | Next: auto-scheduled</div>
  <div class="stats">
    <span>{total} stocks</span>
    <span>{with_intuition} with intuition points</span>
    <span>{held} held in portfolio</span>
  </div>
</div>

<div class="filters">
  <input type="text" id="search" placeholder="Search ticker or name..." oninput="filterTable()">
  <select id="holdFilter" onchange="filterTable()">
    <option value="all">All stocks</option>
    <option value="held">Held only</option>
    <option value="not-held">Not held</option>
  </select>
  <select id="sectorFilter" onchange="filterTable()">
    <option value="all">All sectors</option>
  </select>
</div>

<div class="table-wrap">
<table id="stockTable">
<thead>
<tr>
  <th data-col="rank" class="num">#</th>
  <th data-col="ticker">Ticker</th>
  <th data-col="name">Name</th>
  <th data-col="sector">Sector</th>
  <th data-col="price" class="num">Price</th>
  <th data-col="market_cap_b" class="num">MCap $B</th>
  <th data-col="52w_low" class="num">52W Low</th>
  <th data-col="52w_high" class="num">52W High</th>
  <th data-col="above_52w_low_pct" class="num">Above Low%</th>
  <th data-col="1D" class="num">1D%</th>
  <th data-col="1W" class="num">1W%</th>
  <th data-col="1M" class="num">1M%</th>
  <th data-col="3M" class="num">3M%</th>
  <th data-col="6M" class="num">6M%</th>
  <th data-col="1Y" class="num">1Y%</th>
  <th data-col="intuition_point" class="num">Intuition $</th>
  <th data-col="upside_pct" class="num">Upside%</th>
  <th data-col="crossings" class="num">Crosses</th>
  <th data-col="crossing_quarters" class="num">Qtrs</th>
  <th data-col="personal_score" class="num">Personal</th>
  <th data-col="evidence_score" class="num">Evidence</th>
  <th data-col="i_hold">Hold?</th>
  <th data-col="shares_held" class="num">Shares</th>
  <th data-col="avg_price" class="num">Avg$</th>
  <th data-col="holding_pnl_pct" class="num">P&L%</th>
</tr>
</thead>
<tbody>
{table_body}
</tbody>
</table>
</div>

<script>
const DATA = {stocks_json};

// Populate sector filter
const sectors = [...new Set(DATA.map(s => s.sector).filter(Boolean))].sort();
const sf = document.getElementById('sectorFilter');
sectors.forEach(s => {{ const o = document.createElement('option'); o.value = s; o.textContent = s; sf.appendChild(o); }});

// Sort
let sortCol = 'rank', sortDir = 1;
document.querySelectorAll('th[data-col]').forEach(th => {{
  th.addEventListener('click', () => {{
    const col = th.dataset.col;
    if (sortCol === col) sortDir *= -1;
    else {{ sortCol = col; sortDir = 1; }}
    document.querySelectorAll('th').forEach(h => h.classList.remove('sorted-asc','sorted-desc'));
    th.classList.add(sortDir === 1 ? 'sorted-asc' : 'sorted-desc');
    sortTable();
  }});
}});

function sortTable() {{
  const tbody = document.querySelector('#stockTable tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  rows.sort((a, b) => {{
    let av = a.dataset[sortCol] || '';
    let bv = b.dataset[sortCol] || '';
    const an = parseFloat(av), bn = parseFloat(bv);
    if (!isNaN(an) && !isNaN(bn)) return (an - bn) * sortDir;
    return av.localeCompare(bv) * sortDir;
  }});
  rows.forEach(r => tbody.appendChild(r));
}}

function filterTable() {{
  const search = document.getElementById('search').value.toLowerCase();
  const hold = document.getElementById('holdFilter').value;
  const sector = document.getElementById('sectorFilter').value;
  document.querySelectorAll('#stockTable tbody tr').forEach(tr => {{
    const ticker = (tr.dataset.ticker || '').toLowerCase();
    const name = (tr.dataset.name || '').toLowerCase();
    const iHold = tr.dataset.i_hold;
    const sec = tr.dataset.sector || '';
    let show = true;
    if (search && !ticker.includes(search) && !name.includes(search)) show = false;
    if (hold === 'held' && iHold !== 'true') show = false;
    if (hold === 'not-held' && iHold === 'true') show = false;
    if (sector !== 'all' && sec !== sector) show = false;
    tr.style.display = show ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    return str(output_path)


def _render_row(s: dict) -> str:
    """Render a single table row."""
    def pct_cell(val, cls="pct"):
        if val is None:
            return f'<td class="{cls}">—</td>'
        color = "pos" if val > 0 else "neg" if val < 0 else ""
        sign = "+" if val > 0 else ""
        return f'<td class="{cls} {color}">{sign}{val:.1f}%</td>'

    def num_cell(val, fmt=".2f"):
        if val is None or val == 0:
            return '<td class="num">—</td>'
        return f'<td class="num">{val:{fmt}}</td>'

    def score_cell(val):
        if val is None:
            return '<td class="num">—</td>'
        cls = "score-high" if val >= 8 else "score-mid" if val >= 6 else "score-low"
        return f'<td class="num"><span class="score {cls}">{val:.1f}</span></td>'

    source = s.get("intuition_source", "algorithm")
    source_badge = '<span class="source-badge source-user">manual</span>' if source == "user_override" else '<span class="source-badge source-algo">auto</span>'

    held_class = "held" if s.get("i_hold") else ""
    hold_cell = '<td class="hold-yes">YES</td>' if s.get("i_hold") else '<td class="hold-no">no</td>'

    intuition_cell = f'<td class="num intuition">${s["intuition_point"]:.0f}{source_badge}</td>' if s.get("intuition_point") else '<td class="num">—</td>'

    # Data attributes for sorting/filtering
    data_attrs = " ".join([
        f'data-{k}="{v}"' for k, v in {
            "rank": s.get("rank", 999),
            "ticker": s.get("ticker", ""),
            "name": s.get("name", ""),
            "sector": s.get("sector", ""),
            "price": s.get("price", 0),
            "market_cap_b": s.get("market_cap_b", 0),
            "52w_low": s.get("52w_low", 0),
            "52w_high": s.get("52w_high", 0),
            "above_52w_low_pct": s.get("above_52w_low_pct", 0) or 0,
            "1D": s.get("1D", 0) or 0,
            "1W": s.get("1W", 0) or 0,
            "1M": s.get("1M", 0) or 0,
            "3M": s.get("3M", 0) or 0,
            "6M": s.get("6M", 0) or 0,
            "1Y": s.get("1Y", 0) or 0,
            "intuition_point": s.get("intuition_point", 0) or 0,
            "upside_pct": s.get("upside_pct", 0) or 0,
            "crossings": s.get("crossings", 0),
            "crossing_quarters": s.get("crossing_quarters", 0),
            "personal_score": s.get("personal_score", 0),
            "evidence_score": s.get("evidence_score", 0),
            "i_hold": str(s.get("i_hold", False)).lower(),
            "shares_held": s.get("shares_held", 0),
            "avg_price": s.get("avg_price", 0),
            "holding_pnl_pct": s.get("holding_pnl_pct", 0) or 0,
        }.items()
    ])

    return f"""<tr class="{held_class}" {data_attrs}>
  <td class="num">{s.get('rank', '')}</td>
  <td class="ticker">{s['ticker']}</td>
  <td class="name" title="{s.get('name', '')}">{s.get('name', '')}</td>
  <td class="sector">{s.get('sector', '')}</td>
  {num_cell(s.get('price'))}
  {num_cell(s.get('market_cap_b'), '.1f')}
  {num_cell(s.get('52w_low'))}
  {num_cell(s.get('52w_high'))}
  {pct_cell(s.get('above_52w_low_pct'))}
  {pct_cell(s.get('1D'))}
  {pct_cell(s.get('1W'))}
  {pct_cell(s.get('1M'))}
  {pct_cell(s.get('3M'))}
  {pct_cell(s.get('6M'))}
  {pct_cell(s.get('1Y'))}
  {intuition_cell}
  {pct_cell(s.get('upside_pct'))}
  <td class="num">{s.get('crossings', 0)}</td>
  <td class="num">{s.get('crossing_quarters', 0)}</td>
  {score_cell(s.get('personal_score'))}
  {score_cell(s.get('evidence_score'))}
  {hold_cell}
  <td class="num">{s.get('shares_held', 0) or '—'}</td>
  {num_cell(s.get('avg_price'))}
  {pct_cell(s.get('holding_pnl_pct'))}
</tr>"""
