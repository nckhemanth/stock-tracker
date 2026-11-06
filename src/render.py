"""
Render the stock table as a static HTML page.
Mobile-friendly, dark theme, sortable columns, working filters.
"""

import json
from datetime import datetime
from html import escape
from pathlib import Path

from .config import OUTPUT_DIR


def render_html(stocks: list[dict], output_path: Path = None) -> str:
    """Generate the full HTML page with stock table."""
    if output_path is None:
        output_path = OUTPUT_DIR / "index.html"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    total = len(stocks)
    with_intuition = sum(1 for s in stocks if s.get("intuition_point"))
    held = sum(1 for s in stocks if s.get("i_hold"))

    rows_html = "\n".join(_render_row(s) for s in stocks)
    stocks_json = json.dumps(stocks, default=str)

    html = _HTML_TEMPLATE.format(
        now=now,
        total=total,
        with_intuition=with_intuition,
        held=held,
        table_body=rows_html,
        stocks_json=stocks_json,
    )

    output_path.write_text(html, encoding="utf-8")
    return str(output_path)


def _esc(val) -> str:
    """HTML-escape a value for use in attributes."""
    return escape(str(val), quote=True)


def _render_row(s: dict) -> str:
    """Render a single table row."""

    def pct_cell(val):
        if val is None:
            return '<td class="num">—</td>'
        color = "pos" if val > 0 else "neg" if val < 0 else ""
        sign = "+" if val > 0 else ""
        return f'<td class="num {color}">{sign}{val:.1f}%</td>'

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
    source_cls = "src-manual" if source == "user_override" else "src-auto"
    source_label = "manual" if source == "user_override" else "auto"

    held_class = "held" if s.get("i_hold") else ""
    hold_cell = '<td class="hold-yes">YES</td>' if s.get("i_hold") else '<td class="hold-no">—</td>'

    # Intuition point cell with upside coloring
    upside = s.get("upside_pct")
    if s.get("intuition_point"):
        ip_color = "neg" if upside is not None and upside < 0 else "intuition"
        intuition_cell = f'<td class="num {ip_color}">${s["intuition_point"]:.0f}<span class="source-badge {source_cls}">{source_label}</span></td>'
    else:
        intuition_cell = '<td class="num dim">—</td>'

    # Below 52W high %
    price = s.get("price", 0) or 0
    high_52w = s.get("52w_high", 0) or 0
    below_high_pct = round(((price - high_52w) / high_52w) * 100, 1) if high_52w else None

    # Recommendation badge
    rec = s.get("recommendation", "")
    rec_map = {
        "strong_buy": ("BUY", "rec-buy"),
        "buy": ("BUY", "rec-buy"),
        "hold": ("HOLD", "rec-hold"),
        "sell": ("SELL", "rec-sell"),
        "strong_sell": ("SELL", "rec-sell"),
    }
    rec_label, rec_cls = rec_map.get(rec, ("—", ""))
    rec_cell = f'<td class="num"><span class="rec {rec_cls}">{rec_label}</span></td>' if rec_cls else '<td class="num dim">—</td>'

    # Revenue growth formatting
    rev_growth = s.get("revenue_growth")
    if rev_growth is not None:
        rev_pct = rev_growth * 100  # stored as decimal
        rev_color = "pos" if rev_pct > 0 else "neg" if rev_pct < 0 else ""
        rev_cell = f'<td class="num {rev_color}">{rev_pct:+.0f}%</td>'
    else:
        rev_cell = '<td class="num dim">—</td>'

    # Profit margin formatting
    margin = s.get("profit_margin")
    if margin is not None:
        margin_pct = margin * 100
        margin_color = "pos" if margin_pct > 0 else "neg" if margin_pct < 0 else ""
        margin_cell = f'<td class="num {margin_color}">{margin_pct:.0f}%</td>'
    else:
        margin_cell = '<td class="num dim">—</td>'

    # Crossing dates (last 3)
    dates = s.get("crossing_dates", [])
    if dates:
        recent = dates[-3:] if len(dates) > 3 else dates
        dates_str = ", ".join(d[5:] for d in recent)  # strip year
        dates_cell = f'<td class="num dim" title="{_esc(", ".join(dates))}">{dates_str}</td>'
    else:
        dates_cell = '<td class="num dim">—</td>'

    # Data attributes — valid names only (lowercase, no leading digits)
    attrs = {
        "rank": s.get("rank", 999),
        "ticker": _esc(s.get("ticker", "")),
        "name": _esc(s.get("name", "")),
        "sector": _esc(s.get("sector", "")),
        "industry": _esc(s.get("industry", "")),
        "price": s.get("price", 0) or 0,
        "mcap": s.get("market_cap_b", 0) or 0,
        "wlow": s.get("52w_low", 0) or 0,
        "whigh": s.get("52w_high", 0) or 0,
        "abovelow": s.get("above_52w_low_pct", 0) or 0,
        "belowhigh": below_high_pct or 0,
        "d1": s.get("1D", 0) or 0,
        "w1": s.get("1W", 0) or 0,
        "m1": s.get("1M", 0) or 0,
        "m3": s.get("3M", 0) or 0,
        "m6": s.get("6M", 0) or 0,
        "y1": s.get("1Y", 0) or 0,
        "y3": s.get("3Y", 0) or 0,
        "y5": s.get("5Y", 0) or 0,
        "ip": s.get("intuition_point", 0) or 0,
        "upside": s.get("upside_pct", 0) or 0,
        "crosses": s.get("crossings", 0),
        "qtrs": s.get("crossing_quarters", 0),
        "pscore": s.get("personal_score", 0) or 0,
        "escore": s.get("evidence_score", 0) or 0,
        "pe": s.get("pe_ratio", 0) or 0,
        "fpe": round(s.get("forward_pe", 0) or 0, 1),
        "revgr": round((s.get("revenue_growth", 0) or 0) * 100, 1),
        "margin": round((s.get("profit_margin", 0) or 0) * 100, 1),
        "target": s.get("analyst_target", 0) or 0,
        "hold": str(s.get("i_hold", False)).lower(),
        "shares": s.get("shares_held", 0) or 0,
        "avg": s.get("avg_price", 0) or 0,
        "invested": s.get("invested", 0) or 0,
        "pnl": s.get("holding_pnl_pct", 0) or 0,
    }
    data_attrs = " ".join(f'data-{k}="{v}"' for k, v in attrs.items())

    name_esc = _esc(s.get("name", ""))
    industry_esc = _esc(s.get("industry", ""))
    sector_esc = _esc(s.get("sector", ""))

    return f"""<tr class="{held_class}" {data_attrs}>
  <td class="num">{s.get('rank', '')}</td>
  <td class="ticker">{_esc(s['ticker'])}</td>
  <td class="name" title="{name_esc}">{name_esc}</td>
  <td class="sector">{sector_esc}</td>
  <td class="industry">{industry_esc}</td>
  {num_cell(s.get('price'))}
  {num_cell(s.get('market_cap_b'), '.1f')}
  {num_cell(s.get('52w_low'))}
  {num_cell(s.get('52w_high'))}
  {pct_cell(s.get('above_52w_low_pct'))}
  {pct_cell(below_high_pct)}
  {pct_cell(s.get('1D'))}
  {pct_cell(s.get('1W'))}
  {pct_cell(s.get('1M'))}
  {pct_cell(s.get('3M'))}
  {pct_cell(s.get('6M'))}
  {pct_cell(s.get('1Y'))}
  {pct_cell(s.get('3Y'))}
  {pct_cell(s.get('5Y'))}
  {intuition_cell}
  {pct_cell(upside)}
  <td class="num">{s.get('crossings', 0)}</td>
  <td class="num">{s.get('crossing_quarters', 0)}</td>
  {dates_cell}
  {num_cell(s.get('pe_ratio'), '.1f')}
  {num_cell(s.get('forward_pe'), '.1f')}
  {rev_cell}
  {margin_cell}
  {num_cell(s.get('analyst_target'), '.0f')}
  {rec_cell}
  {score_cell(s.get('personal_score'))}
  {score_cell(s.get('evidence_score'))}
  {hold_cell}
  <td class="num">{s.get('shares_held', 0) or '—'}</td>
  {num_cell(s.get('avg_price'))}
  {num_cell(s.get('invested'), '.0f')}
  {pct_cell(s.get('holding_pnl_pct'))}
</tr>"""


# ── HTML template (not an f-string — uses .format()) ──────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stock Tracker | {now}</title>
<style>
:root {{
  --bg: #0d1117; --surface: #161b22; --border: #30363d;
  --text: #e6edf3; --dim: #8b949e; --accent: #58a6ff;
  --green: #3fb950; --red: #f85149; --yellow: #d29922; --orange: #db6d28;
  --hold-bg: #1a2332;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,monospace; font-size:13px; }}

/* Header */
.header {{ background:var(--surface); border-bottom:1px solid var(--border); padding:12px 16px; }}
.header h1 {{ font-size:18px; font-weight:700; letter-spacing:-0.3px; }}
.header .meta {{ font-size:11px; color:var(--dim); margin-top:3px; }}
.stats {{ display:flex; gap:12px; margin-top:8px; font-size:11px; flex-wrap:wrap; }}
.stats span {{ background:var(--border); padding:3px 10px; border-radius:4px; }}

/* Filters */
.filters {{ padding:8px 16px; background:var(--surface); border-bottom:1px solid var(--border); display:flex; gap:8px; flex-wrap:wrap; align-items:center; }}
.filters input {{ background:var(--bg); border:1px solid var(--border); color:var(--text); padding:5px 10px; border-radius:4px; font-size:12px; width:200px; }}
.filters select {{ background:var(--bg); border:1px solid var(--border); color:var(--text); padding:5px 8px; border-radius:4px; font-size:12px; }}
.filters label {{ font-size:11px; color:var(--dim); display:flex; align-items:center; gap:4px; cursor:pointer; }}
.filters input[type=checkbox] {{ accent-color:var(--accent); }}
.col-toggle {{ font-size:10px; color:var(--accent); cursor:pointer; padding:3px 8px; border:1px solid var(--border); border-radius:4px; background:var(--bg); }}
.col-toggle:hover {{ border-color:var(--accent); }}

/* Table */
.table-wrap {{ overflow-x:auto; }}
table {{ border-collapse:collapse; width:100%; min-width:2400px; }}
thead {{ position:sticky; top:0; z-index:50; }}
th {{ background:var(--surface); padding:6px 8px; text-align:right;
     font-size:10px; font-weight:600; color:var(--dim); border-bottom:2px solid var(--border);
     cursor:pointer; white-space:nowrap; user-select:none; }}
th:first-child, th:nth-child(2), th:nth-child(3), th:nth-child(4), th:nth-child(5) {{ text-align:left; }}
th:hover {{ color:var(--accent); }}
th.sorted-asc::after {{ content:" ▲"; color:var(--accent); }}
th.sorted-desc::after {{ content:" ▼"; color:var(--accent); }}
td {{ padding:4px 8px; border-bottom:1px solid var(--border); white-space:nowrap; font-size:12px; }}
tr:hover {{ background:rgba(88,166,255,0.06); }}
tr.held {{ background:var(--hold-bg); }}

/* Column group headers */
.col-group {{ font-size:9px; text-transform:uppercase; letter-spacing:0.5px; color:var(--accent); background:var(--bg); border-bottom:1px solid var(--border); padding:3px 8px; }}

/* Cell styles */
.ticker {{ font-weight:700; color:var(--accent); text-align:left; }}
.name {{ color:var(--dim); max-width:150px; overflow:hidden; text-overflow:ellipsis; text-align:left; }}
.sector {{ text-align:left; font-size:11px; }}
.industry {{ text-align:left; font-size:10px; color:var(--dim); max-width:120px; overflow:hidden; text-overflow:ellipsis; }}
.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
.dim {{ color:var(--dim); }}
.pos {{ color:var(--green); }}
.neg {{ color:var(--red); }}
.hold-yes {{ color:var(--green); font-weight:700; }}
.hold-no {{ color:var(--dim); }}

/* Scores */
.score {{ display:inline-block; padding:1px 6px; border-radius:3px; font-weight:600; font-size:11px; }}
.score-high {{ background:rgba(63,185,80,0.15); color:var(--green); }}
.score-mid {{ background:rgba(210,153,34,0.15); color:var(--yellow); }}
.score-low {{ background:rgba(248,81,73,0.15); color:var(--red); }}

/* Intuition & source */
.intuition {{ color:var(--yellow); font-weight:600; }}
.source-badge {{ font-size:8px; padding:1px 3px; border-radius:2px; margin-left:3px; vertical-align:super; }}
.src-manual {{ background:rgba(63,185,80,0.2); color:var(--green); }}
.src-auto {{ background:rgba(88,166,255,0.15); color:var(--accent); }}

/* Recommendation */
.rec {{ font-size:9px; padding:1px 5px; border-radius:2px; font-weight:600; }}
.rec-buy {{ background:rgba(63,185,80,0.15); color:var(--green); }}
.rec-hold {{ background:rgba(210,153,34,0.15); color:var(--yellow); }}
.rec-sell {{ background:rgba(248,81,73,0.15); color:var(--red); }}

/* Responsive */
@media (max-width:768px) {{
  .header h1 {{ font-size:14px; }}
  td, th {{ padding:3px 5px; font-size:10px; }}
  table {{ min-width:1800px; }}
  .filters input {{ width:140px; }}
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
    <option value="negative">Negative upside</option>
  </select>
  <select id="sectorFilter" onchange="filterTable()">
    <option value="all">All sectors</option>
  </select>
  <select id="recFilter" onchange="filterTable()">
    <option value="all">All ratings</option>
    <option value="buy">Buy / Strong Buy</option>
    <option value="hold">Hold</option>
    <option value="sell">Sell</option>
  </select>
  <label><input type="checkbox" id="showFundamentals" onchange="toggleCols('fund')" checked> Fundamentals</label>
  <label><input type="checkbox" id="showHoldings" onchange="toggleCols('hold')" checked> Holdings</label>
</div>

<div class="table-wrap">
<table id="stockTable">
<thead>
<tr>
  <th data-col="rank">#</th>
  <th data-col="ticker">Ticker</th>
  <th data-col="name">Name</th>
  <th data-col="sector">Sector</th>
  <th data-col="industry" class="fund">Industry</th>
  <th data-col="price">Price</th>
  <th data-col="mcap">MCap $B</th>
  <th data-col="wlow">52W Low</th>
  <th data-col="whigh">52W High</th>
  <th data-col="abovelow">Above Low%</th>
  <th data-col="belowhigh">Below High%</th>
  <th data-col="d1">1D%</th>
  <th data-col="w1">1W%</th>
  <th data-col="m1">1M%</th>
  <th data-col="m3">3M%</th>
  <th data-col="m6">6M%</th>
  <th data-col="y1">1Y%</th>
  <th data-col="y3">3Y%</th>
  <th data-col="y5">5Y%</th>
  <th data-col="ip">Intuition $</th>
  <th data-col="upside">Upside%</th>
  <th data-col="crosses">Crosses</th>
  <th data-col="qtrs">Qtrs</th>
  <th data-col="dates">Recent Dates</th>
  <th data-col="pe" class="fund">PE</th>
  <th data-col="fpe" class="fund">Fwd PE</th>
  <th data-col="revgr" class="fund">Rev Gr%</th>
  <th data-col="margin" class="fund">Margin%</th>
  <th data-col="target" class="fund">Target$</th>
  <th data-col="rec" class="fund">Rating</th>
  <th data-col="pscore">Personal</th>
  <th data-col="escore">Evidence</th>
  <th data-col="hold" class="holdcol">Hold?</th>
  <th data-col="shares" class="holdcol">Shares</th>
  <th data-col="avg" class="holdcol">Avg$</th>
  <th data-col="invested" class="holdcol">Invested$</th>
  <th data-col="pnl" class="holdcol">P&amp;L%</th>
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
sectors.forEach(s => {{
  const o = document.createElement('option');
  o.value = s;
  o.textContent = s;
  sf.appendChild(o);
}});

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
  const rec = document.getElementById('recFilter').value;
  document.querySelectorAll('#stockTable tbody tr').forEach(tr => {{
    const ticker = (tr.dataset.ticker || '').toLowerCase();
    const name = (tr.dataset.name || '').toLowerCase();
    const industry = (tr.dataset.industry || '').toLowerCase();
    const isHeld = tr.dataset.hold;
    const sec = tr.dataset.sector || '';
    const upside = parseFloat(tr.dataset.upside || '0');
    let show = true;
    if (search && !ticker.includes(search) && !name.includes(search) && !industry.includes(search)) show = false;
    if (hold === 'held' && isHeld !== 'true') show = false;
    if (hold === 'not-held' && isHeld === 'true') show = false;
    if (hold === 'negative' && upside >= 0) show = false;
    if (sector !== 'all' && sec !== sector) show = false;
    if (rec !== 'all') {{
      const rating = DATA.find(d => d.ticker === tr.dataset.ticker);
      if (rating) {{
        const r = rating.recommendation || '';
        if (rec === 'buy' && !r.includes('buy')) show = false;
        if (rec === 'hold' && r !== 'hold') show = false;
        if (rec === 'sell' && !r.includes('sell')) show = false;
      }}
    }}
    tr.style.display = show ? '' : 'none';
  }});
  updateCount();
}}

function updateCount() {{
  const visible = document.querySelectorAll('#stockTable tbody tr:not([style*="display: none"])').length;
  document.getElementById('visCount').textContent = visible + ' shown';
}}

function toggleCols(group) {{
  const cls = group === 'fund' ? 'fund' : 'holdcol';
  const checked = document.getElementById(group === 'fund' ? 'showFundamentals' : 'showHoldings').checked;
  document.querySelectorAll('.' + cls).forEach(el => {{
    el.style.display = checked ? '' : 'none';
  }});
  // Also toggle data cells
  const ths = document.querySelectorAll('th.' + cls);
  const indices = Array.from(ths).map(th => Array.from(th.parentNode.children).indexOf(th));
  document.querySelectorAll('#stockTable tbody tr').forEach(tr => {{
    indices.forEach(i => {{
      if (tr.children[i]) tr.children[i].style.display = checked ? '' : 'none';
    }});
  }});
}}

// Add visible count to stats
const statsDiv = document.querySelector('.stats');
const countSpan = document.createElement('span');
countSpan.id = 'visCount';
countSpan.textContent = '{total} shown';
statsDiv.appendChild(countSpan);
</script>
</body>
</html>"""
