from dash import html, dcc, dash_table

from ui.components import card, G, inp
from utils import TH
from services.telemetry_service import predict_fuel_strategy
from services.fuel_service import stint_summary, pit_stops, pit_window
from plotting.fuel import fig_fuel_level, fig_fuel_per_lap, fig_stint_compare


def _kpi(label, value, color, t):
    return html.Div(style={"flex": "1", "minWidth": "140px"}, children=[
        html.Div(label, style={"fontSize": "11px", "color": t["subtext"], "textTransform": "uppercase"}),
        html.Div(value, style={"fontSize": "24px", "fontWeight": "700", "color": color}),
    ])


def _table(df, mode, tid):
    t = TH(mode)
    if df is None or df.empty:
        return html.Div("—", style={"color": t["subtext"], "fontSize": "12px"})
    return dash_table.DataTable(
        id=tid, columns=[{"name": c, "id": c} for c in df.columns], data=df.round(3).to_dict("records"),
        style_header={"backgroundColor": "rgba(0,0,0,0.3)", "color": t["accent"], "fontWeight": "700", "border": "none"},
        style_cell={"backgroundColor": "transparent", "color": t["text"], "border": "none",
                    "fontSize": "12px", "padding": "6px 10px", "textAlign": "left"},
        style_table={"overflowX": "auto"})


def pit_window_children(dfs, tank, laps_left, mode="dark"):
    """Pit penceresi sonucu (callback ve ilk render tarafından ortak kullanılır)."""
    t = TH(mode)
    r = predict_fuel_strategy(dfs[0]) if dfs else None
    if not r:
        return html.Div("Not enough valid flying laps to estimate consumption.", style={"color": t["warn"]})
    w = pit_window(r["remaining"], r["recent_avg"], tank_capacity=tank, race_laps_left=laps_left)
    items = [f"Fuel on board: {r['remaining']:.1f} L at {r['recent_avg']:.2f} L/lap",
             f"Laps on fuel (0.5 lap margin): {w['laps_on_fuel']:.1f}  →  box within {w['pit_by_lap']} laps"]
    if w["fuel_needed"] is not None:
        items.append(f"Fuel needed to finish: {w['fuel_needed']:.1f} L · shortfall {w['shortfall']:.1f} L")
        if w["stops_needed"] is not None:
            items.append(f"Stops needed: {w['stops_needed']}")
    return html.Ul([html.Li(i) for i in items], style={"fontSize": "13px", "color": t["text"], "lineHeight": "1.8"})


def _render_fuel(dfs, metas=None, mode="dark"):
    """⛽ Fuel & Stints tab"""
    t = TH(mode)
    C_ = card(mode)
    if not dfs:
        return html.Div("No data loaded.", style={"color": t["warn"], "padding": "20px"})
    if not any("FuelLevel" in d.columns for d in dfs):
        return html.Div("⚠️ FuelLevel channel not found in the loaded files.", style={"color": t["warn"], "padding": "20px"})

    r = predict_fuel_strategy(dfs[0])
    kpis = [html.Div("Not enough valid flying laps for a fuel estimate.", style={"color": t["warn"]})]
    if r:
        kpis = [_kpi("Avg / lap", f"{r['avg_per_lap']:.2f} L", t["accent"], t),
                _kpi("Current stint avg", f"{r['recent_avg']:.2f} L", t["gold"], t),
                _kpi("Fuel left", f"{r['remaining']:.1f} L", t["good"], t),
                _kpi("Est. laps left", f"{r['est_laps']:.1f}", t["warn"], t),
                _kpi("Stints", str(r["stint_count"]), t["text"], t)]

    per_driver = []
    for i, d in enumerate(dfs):
        name = str(d["Driver"].iloc[0]) if "Driver" in d.columns else f"Driver {i + 1}"
        per_driver.append(html.Div(style=C_, children=[
            html.Div(f"🏁 {name} — stints", className="section-title", style={"color": t["accent"], "fontSize": "13px"}),
            _table(stint_summary(d), mode, f"fuel-stints-{i}"),
            html.Div("Pit stops", className="section-title",
                     style={"color": t["gold"], "fontSize": "13px", "marginTop": "12px"}),
            _table(pit_stops(d), mode, f"fuel-pits-{i}"),
        ]))

    return html.Div(className="fade-in", children=[
        html.Div(style={**C_, "display": "flex", "gap": "16px", "flexWrap": "wrap"}, children=kpis),
        html.Div(style=C_, children=[
            html.Div("🧮 Pit window", className="section-title", style={"color": t["accent"], "fontSize": "13px"}),
            html.Div(style={"display": "flex", "gap": "12px", "marginBottom": "8px"}, children=[
                dcc.Input(id="fuel-tank-input", type="number", min=1, placeholder="Tank (L)", style=inp("120px")),
                dcc.Input(id="fuel-laps-left-input", type="number", min=0, placeholder="Race laps left", style=inp("140px")),
            ]),
            html.Div(id="fuel-pit-window-out", children=pit_window_children(dfs, None, None, mode)),
        ]),
        G(fig_fuel_level(dfs, mode), mode, full=True, h=380),
        G(fig_fuel_per_lap(dfs, mode), mode, full=True, h=380),
        G(fig_stint_compare(dfs, mode), mode, full=True, h=340),
        *per_driver,
    ])
