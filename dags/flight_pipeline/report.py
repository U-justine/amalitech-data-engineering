"""Builds the KPI report (data/reports/kpi_report.html) after every run.

It reads the KPI tables from Postgres and makes one html page with charts.
I drew the charts as plain SVG so the page works offline (for the
presentation) and I don't need an extra library.

What's on the page:
  - the main numbers (rows loaded/rejected, airlines, avg fare, peak vs regular)
  - avg fare by airline
  - fares per season (peak seasons vs regular)
  - bookings by airline
  - top 10 routes
  - all of it again as tables, if you want the exact numbers
"""
from __future__ import annotations

import html
import json
import logging
import os
from datetime import datetime, timezone

import pandas as pd

from . import db
from .schema import PG_SCHEMA

log = logging.getLogger(__name__)

REPORT_NAME = "kpi_report.html"


# --- data ---
def fetch_report_data(pg_conn) -> dict:
    """get the 4 KPI tables and the last run from Postgres"""
    q = lambda sql: db.fetch_df(pg_conn, sql)  # noqa: E731
    run = q(f"SELECT batch_id, rows_in_file, rows_valid, rows_rejected, rows_loaded, loaded_at "
            f"FROM {PG_SCHEMA}.pipeline_run_log ORDER BY loaded_at DESC LIMIT 1")
    return {
        "avg_fare": q(f"SELECT airline, booking_count, avg_total_fare, median_total_fare, min_total_fare, "
                      f"max_total_fare, fare_rank FROM {PG_SCHEMA}.kpi_avg_fare_by_airline ORDER BY fare_rank"),
        "seasonal": q(f"SELECT grouping_level, season_label, is_peak_season, booking_count, avg_total_fare, "
                      f"pct_diff_vs_baseline FROM {PG_SCHEMA}.kpi_seasonal_fare_variation"),
        "bookings": q(f"SELECT airline, booking_count, booking_share_pct, booking_rank "
                      f"FROM {PG_SCHEMA}.kpi_booking_count_by_airline ORDER BY booking_rank, airline"),
        "routes": q(f"SELECT route_rank, route, source_name, destination_name, booking_count, avg_total_fare "
                    f"FROM {PG_SCHEMA}.kpi_popular_routes WHERE is_top_route ORDER BY route_rank"),
        "overall_avg": float(db.fetch_scalar(pg_conn, f"SELECT COALESCE(AVG(total_fare),0) FROM {PG_SCHEMA}.fact_flight_prices")),
        "run": run.iloc[0].to_dict() if not run.empty else {},
    }


# --- formatting ---
def _e(v) -> str:
    return html.escape(str(v), quote=True)


def _num(v, decimals=0) -> str:
    try:
        return f"{float(v):,.{decimals}f}"
    except (TypeError, ValueError):
        return "–"


def _bdt(v) -> str:
    return f"{_num(v)} BDT"


def _nice_max(v: float) -> float:
    """round the axis max up to a nice number, e.g. 179,420 -> 200,000"""
    if v <= 0:
        return 1.0
    exp = 10 ** (len(str(int(v))) - 1)
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * exp:
            return m * exp
    return 10 * exp


def _short(v: float) -> str:
    if v >= 1_000_000:
        return f"{v / 1_000_000:g}M"
    if v >= 1_000:
        return f"{v / 1_000:g}k"
    return f"{v:g}"


# --- bar chart (svg) ---
def hbar_chart(rows: list[dict], *, value_key: str, label_key: str, title: str,
               tip, label_value, color_key=None, ticks: int = 4, label_rows=None) -> str:
    """Horizontal bar chart, bars in the order of rows.

    tip(row)         -> text for the hover tooltip
    label_value(row) -> the number shown at the end of the bar
    color_key(row)   -> css colour variable (blue by default)
    label_rows       -> which bars get a number (None = all of them)
    """
    bar_h, gap, label_w, right_pad, top, axis_h = 18, 10, 190, 90, 8, 22
    width = 760
    plot_w = width - label_w - right_pad
    height = top + len(rows) * (bar_h + gap) + axis_h
    vmax = _nice_max(max((float(r[value_key] or 0) for r in rows), default=1))
    x = lambda v: label_w + (float(v) / vmax) * plot_w  # noqa: E731

    parts = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{_e(title)}">']
    # light grid lines + the numbers under the axis
    for i in range(ticks + 1):
        v = vmax * i / ticks
        gx = x(v)
        parts.append(f'<line class="grid" x1="{gx:.1f}" x2="{gx:.1f}" y1="{top - 4}" y2="{height - axis_h + 2}"/>')
        parts.append(f'<text class="tick" x="{gx:.1f}" y="{height - 6}" text-anchor="middle">{_short(v)}</text>')
    # the axis line on the left
    parts.append(f'<line class="axis" x1="{label_w}" x2="{label_w}" y1="{top - 4}" y2="{height - axis_h + 2}"/>')

    for i, r in enumerate(rows):
        y = top + i * (bar_h + gap)
        w = max(x(r[value_key] or 0) - label_w, 0.5)
        rad = min(4, w)
        color = color_key(r) if color_key else "--series-1"
        # bar shape: straight on the left, rounded corners on the right
        d = (f"M{label_w},{y} h{w - rad:.1f} a{rad},{rad} 0 0 1 {rad},{rad} v{bar_h - 2 * rad} "
             f"a{rad},{rad} 0 0 1 {-rad},{rad} h{-(w - rad):.1f} z")
        tip_txt = _e(tip(r))
        parts.append(f'<g class="mark" tabindex="0" data-tip="{tip_txt}">'
                     f'<rect class="hit" x="0" y="{y - gap / 2}" width="{width}" height="{bar_h + gap}"/>'
                     f'<path d="{d}" style="fill:var({color})"/>'
                     f'<text class="label" x="{label_w - 10}" y="{y + bar_h / 2}" dy="0.35em" text-anchor="end">'
                     f'{_e(r[label_key])}</text>')
        if label_rows is None or i in label_rows:
            parts.append(f'<text class="value" x="{label_w + w + 8:.1f}" y="{y + bar_h / 2}" dy="0.35em">'
                         f'{_e(label_value(r))}</text>')
        parts.append(f'<title>{tip_txt}</title></g>')
    parts.append("</svg>")
    return "".join(parts)


def _table(df: pd.DataFrame, columns: dict) -> str:
    head = "".join(f"<th>{_e(h)}</th>" for h in columns.values())
    body = []
    for _, r in df.iterrows():
        cells = []
        for col, hdr in columns.items():
            v = r[col]
            try:
                fv = float(v)
                txt = _num(fv, 2 if ("pct" in col or "share" in col) else 0)
                cells.append(f'<td class="num">{txt}</td>')
            except (TypeError, ValueError):
                cells.append(f"<td>{_e(v)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f'<table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'


# --- the page ---
CSS = """
.viz-root{color-scheme:light;--page:#f9f9f7;--surface-1:#fcfcfb;--text-primary:#0b0b0b;--text-secondary:#52514e;
--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;--border:rgba(11,11,11,.10);--series-1:#2a78d6;--series-2:#eb6834;--good:#006300}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])) .viz-root{color-scheme:dark;--page:#0d0d0d;
--surface-1:#1a1a19;--text-primary:#f0efec;--text-secondary:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;
--border:rgba(255,255,255,.10);--series-1:#3987e5;--series-2:#d95926;--good:#0ca30c}}
:root[data-theme="dark"] .viz-root{color-scheme:dark;--page:#0d0d0d;--surface-1:#1a1a19;--text-primary:#f0efec;
--text-secondary:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);
--series-1:#3987e5;--series-2:#d95926;--good:#0ca30c}
*{box-sizing:border-box}
body{margin:0;background:var(--page)}
.viz-root{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--page);color:var(--text-primary);
min-height:100vh;padding:24px 16px 48px}
.wrap{max-width:860px;margin:0 auto}
header{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap;margin-bottom:20px}
h1{font-size:22px;margin:0 0 4px}
.sub{color:var(--text-secondary);font-size:13px;margin:0}
.toggle{font:inherit;font-size:13px;color:var(--text-secondary);background:var(--surface-1);border:1px solid var(--border);
border-radius:8px;padding:6px 10px;cursor:pointer}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:20px}
.tile{background:var(--surface-1);border:1px solid var(--border);border-radius:12px;padding:14px 16px}
.tile .k{font-size:12px;color:var(--text-secondary);margin-bottom:6px}
.tile .v{font-size:24px;font-weight:600}
.tile .n{font-size:12px;color:var(--muted);margin-top:4px}
.up{color:var(--good)}
section.card{background:var(--surface-1);border:1px solid var(--border);border-radius:12px;padding:16px 16px 8px;margin-bottom:16px}
section.card h2{font-size:16px;margin:0 0 2px}
section.card p.desc{font-size:13px;color:var(--text-secondary);margin:0 0 12px}
.legend{display:flex;gap:16px;font-size:12px;color:var(--text-secondary);margin:0 0 8px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
svg.chart{width:100%;height:auto;display:block;overflow:visible}
svg .grid{stroke:var(--grid);stroke-width:1}
svg .axis{stroke:var(--axis);stroke-width:1}
svg .tick{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}
svg .label{fill:var(--text-primary);font-size:12px}
svg .value{fill:var(--text-secondary);font-size:12px;font-variant-numeric:tabular-nums}
svg .hit{fill:transparent}
svg .mark:hover path,svg .mark:focus path{opacity:.8}
svg .mark:focus{outline:none}
#tip{position:fixed;pointer-events:none;background:var(--surface-1);color:var(--text-primary);border:1px solid var(--border);
border-radius:8px;padding:6px 10px;font-size:12px;box-shadow:0 4px 16px rgba(0,0,0,.12);display:none;max-width:320px;z-index:10}
details{margin:24px 0 0}
summary{cursor:pointer;color:var(--text-secondary);font-size:14px}
table{border-collapse:collapse;width:100%;font-size:12px;margin:10px 0 18px}
th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--grid)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
h3{font-size:13px;margin:14px 0 0;color:var(--text-secondary)}
footer{color:var(--muted);font-size:12px;margin-top:24px}
"""

JS = """
(function(){const tip=document.getElementById('tip');
function show(e,el){tip.textContent=el.getAttribute('data-tip');tip.style.display='block';move(e);}
function move(e){if(!e||e.clientX===undefined)return;const pad=14;let x=e.clientX+pad,y=e.clientY+pad;
const r=tip.getBoundingClientRect();if(x+r.width>innerWidth-8)x=e.clientX-r.width-pad;if(y+r.height>innerHeight-8)y=e.clientY-r.height-pad;
tip.style.left=x+'px';tip.style.top=y+'px';}
document.querySelectorAll('[data-tip]').forEach(el=>{el.addEventListener('mouseenter',e=>show(e,el));
el.addEventListener('mousemove',move);el.addEventListener('mouseleave',()=>tip.style.display='none');
el.addEventListener('focus',()=>{const b=el.getBoundingClientRect();show({clientX:b.right,clientY:b.top},el);});
el.addEventListener('blur',()=>tip.style.display='none');});
const btn=document.getElementById('theme');const root=document.documentElement;
btn.addEventListener('click',()=>{const dark=root.getAttribute('data-theme')==='dark'||(!root.getAttribute('data-theme')&&matchMedia('(prefers-color-scheme: dark)').matches);
root.setAttribute('data-theme',dark?'light':'dark');});})();
"""


def render_html(data: dict, generated_at: datetime | None = None) -> str:
    """make the html from the KPI data (no db in here, so I can test it)"""
    generated_at = generated_at or datetime.now(timezone.utc)
    run = data.get("run") or {}
    avg, seas, book, routes = data["avg_fare"], data["seasonal"], data["bookings"], data["routes"]

    season_rows = seas[seas["grouping_level"] == "season"].sort_values("avg_total_fare", ascending=False)
    peak_row = seas[(seas["grouping_level"] == "peak_flag") & (seas["season_label"] == "Peak")]
    uplift = float(peak_row["pct_diff_vs_baseline"].iloc[0]) if not peak_row.empty else None

    # numbers at the top
    tiles = [
        ("Rows loaded", _num(run.get("rows_loaded")), f"of {_num(run.get('rows_in_file'))} in the file"),
        ("Rows rejected", _num(run.get("rows_rejected")), "failed data-quality rules"),
        ("Airlines", _num(len(avg)), f"{_num(len(routes))} top routes shown"),
        ("Average total fare", _num(data.get("overall_avg")), "BDT, all bookings"),
    ]
    if uplift is not None:
        tiles.append(("Peak-season fares", f'<span class="up">{uplift:+.1f}%</span>', "vs regular season"))
    tiles_html = "".join(f'<div class="tile"><div class="k">{_e(k)}</div><div class="v">{v}</div>'
                         f'<div class="n">{_e(n)}</div></div>' for k, v, n in tiles)

    # the 4 charts
    avg_rows = avg.to_dict("records")
    last = len(avg_rows) - 1
    chart_avg = hbar_chart(
        avg_rows, value_key="avg_total_fare", label_key="airline", title="Average total fare by airline",
        tip=lambda r: f"{r['airline']}: avg {_bdt(r['avg_total_fare'])} · median {_bdt(r['median_total_fare'])} · "
                      f"{_num(r['booking_count'])} bookings",
        label_value=lambda r: _num(r["avg_total_fare"]), label_rows={0, last})

    seas_rows = season_rows.to_dict("records")
    chart_seas = hbar_chart(
        seas_rows, value_key="avg_total_fare", label_key="season_label", title="Average fare by season",
        tip=lambda r: f"{r['season_label']}: avg {_bdt(r['avg_total_fare'])} · {_num(r['booking_count'])} bookings · "
                      f"{float(r['pct_diff_vs_baseline'] or 0):+.1f}% vs Regular",
        label_value=lambda r: (f"{_num(r['avg_total_fare'])}  ({float(r['pct_diff_vs_baseline'] or 0):+.1f}%)"
                               if bool(r["is_peak_season"]) else f"{_num(r['avg_total_fare'])}  (baseline)"),
        color_key=lambda r: "--series-2" if bool(r["is_peak_season"]) else "--series-1")

    book_rows = book.to_dict("records")
    chart_book = hbar_chart(
        book_rows, value_key="booking_count", label_key="airline", title="Bookings by airline",
        tip=lambda r: f"{r['airline']}: {_num(r['booking_count'])} bookings · {float(r['booking_share_pct']):.1f}% share",
        label_value=lambda r: f"{_num(r['booking_count'])} ({float(r['booking_share_pct']):.1f}%)",
        label_rows={0, len(book_rows) - 1})

    route_rows = routes.to_dict("records")
    for r in route_rows:
        r["label"] = f"{r['route_rank']}. {r['route']}"
    chart_routes = hbar_chart(
        route_rows, value_key="booking_count", label_key="label", title="Top routes by bookings",
        tip=lambda r: f"{r['route']}: {r['source_name']} → {r['destination_name']} · "
                      f"{_num(r['booking_count'])} bookings · avg {_bdt(r['avg_total_fare'])}",
        label_value=lambda r: _num(r["booking_count"]))

    # same data as tables
    tables = (
        "<h3>Average fare by airline (BDT)</h3>" + _table(avg, {"fare_rank": "Rank", "airline": "Airline",
            "avg_total_fare": "Average", "median_total_fare": "Median", "min_total_fare": "Min",
            "max_total_fare": "Max", "booking_count": "Bookings"})
        + "<h3>Seasonal fare variation</h3>" + _table(seas.sort_values(["grouping_level", "avg_total_fare"], ascending=[False, False]),
            {"grouping_level": "Level", "season_label": "Season", "booking_count": "Bookings",
             "avg_total_fare": "Average fare (BDT)", "pct_diff_vs_baseline": "% vs regular"})
        + "<h3>Bookings by airline</h3>" + _table(book, {"booking_rank": "Rank", "airline": "Airline",
            "booking_count": "Bookings", "booking_share_pct": "Share %"})
        + "<h3>Top routes</h3>" + _table(routes, {"route_rank": "Rank", "route": "Route", "source_name": "From",
            "destination_name": "To", "booking_count": "Bookings", "avg_total_fare": "Average fare (BDT)"})
    )

    loaded_at = run.get("loaded_at")
    if loaded_at is not None:
        ts = pd.Timestamp(loaded_at)
        ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
        loaded_txt = ts.strftime("%Y-%m-%d %H:%M")
    else:
        loaded_txt = "–"
    meta = (f"Run <code>{_e(run.get('batch_id', '–'))}</code> · loaded {_e(loaded_txt)} UTC · "
            f"report generated {generated_at.strftime('%Y-%m-%d %H:%M')} UTC")

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Flight Price KPIs</title><style>{CSS}</style></head>
<body><div class="viz-root"><div class="wrap">
<header><div><h1>Flight Price Analysis — Bangladesh</h1><p class="sub">{meta}</p></div>
<button class="toggle" id="theme" type="button">Light / dark</button></header>
<div class="tiles">{tiles_html}</div>

<section class="card"><h2>Average fare by airline</h2>
<p class="desc">Mean Total Fare (BDT) per airline, highest first. Hover a bar for the median and booking count.</p>
{chart_avg}</section>

<section class="card"><h2>Seasonal fare variation</h2>
<p class="desc">Average Total Fare per season. Peak seasons compared with the Regular season (baseline).</p>
<div class="legend"><span><i style="background:var(--series-1)"></i>Regular (non-peak)</span>
<span><i style="background:var(--series-2)"></i>Peak season</span></div>
{chart_seas}</section>

<section class="card"><h2>Booking count by airline</h2>
<p class="desc">Number of bookings per airline and share of all bookings.</p>
{chart_book}</section>

<section class="card"><h2>Most popular routes</h2>
<p class="desc">Top {len(route_rows)} source → destination pairs by number of bookings.</p>
{chart_routes}</section>

<details><summary>Show the numbers as tables</summary>{tables}</details>
<footer>Built by the Airflow DAG <code>flight_price_pipeline</code> (task <code>load.build_kpi_report</code>) from the
PostgreSQL <code>analytics</code> schema.</footer>
</div><div id="tip" role="tooltip"></div></div>
<script>{JS}</script></body></html>"""


def write_report(pg_conn, out_dir: str) -> dict:
    """get the data, build the page, save it. writes to a .tmp file first and then renames it, so the file is never half written"""
    data = fetch_report_data(pg_conn)
    page = render_html(data)
    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, REPORT_NAME)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(page)
    os.replace(tmp, target)
    log.info("KPI report written to %s (%s bytes)", target, len(page))
    return {"path": target, "bytes": len(page), "airlines": len(data["avg_fare"]), "routes": len(data["routes"])}
