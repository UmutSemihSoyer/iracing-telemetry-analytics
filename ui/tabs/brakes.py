import dash
from dash import html, dcc, dash_table
from ui.components import card, btn, inp, G
from utils import TH, apply_theme
import numpy as np
from services.telemetry_service import best_lap_df
from plotting.brakes import analyse_brake_zones, fig_brake_shapes, fig_multi_brake_comparison, fig_brake_consistency, fig_brake_trail_map

try:
    from core.corner_detector import detect_corners, build_segment_map
    CORNER_OK = True
except ImportError:
    CORNER_OK = False


def _render_brakes(dfs, mode):
    from utils import infer_hz
    t  = TH(mode); C_ = card(mode)
    primary = dfs[0]
    hz      = infer_hz(primary)
    zones   = analyse_brake_zones(primary, hz=hz)
    
    hz_badge = html.Span(f"Fidelity: {hz}Hz", style={
        "fontSize": "10px", "backgroundColor": "rgba(16, 185, 129, 0.15)",
        "color": "#10B981", "padding": "2px 8px", "borderRadius": "12px",
        "marginLeft": "12px", "verticalAlign": "middle", "fontWeight": "bold"
    })
    
    # Get turns for selector
    turn_options = []
    if CORNER_OK:
        best = best_lap_df(primary)
        if not best.empty:
            corners = detect_corners(best)
            seg_map = build_segment_map(corners)
            turns = [s["label"] for s in seg_map if s["type"] == "Turn"]
            turn_options = [{"label": f"🔄 {tn}", "value": tn} for tn in turns]

    turn_selector = dcc.Dropdown(
        id="brakes-turn-selector",
        options=turn_options,
        value=turn_options[0]["value"] if turn_options else None,
        clearable=False,
        style={"fontSize": "13px", "backgroundColor": "#1E2028", "color": "#C9CDD6", "border": "none"}
    )

    notes = html.Div(style={**C_,"padding":"16px 20px"}, children=[
        html.Div([
            html.Span("🛑 Brake Analysis", className="section-title", style={"color":t["bad"]}),
            hz_badge
        ]),
        html.P("Application Rate = how quickly brake pressure builds. "
               "Trail Brake % = overlap with steering. "
               "Release Rate = how quickly pressure drops off.",
               className="section-description"),
    ])

    if zones.empty:
        return html.Div(className="fade-in", children=[notes,
                         html.Div("No brake zones detected.",
                                  style={"color":t["warn"],"padding":"20px"})])

    return html.Div(className="fade-in", children=[
        html.Div(style={"display": "flex", "gap": "16px", "marginBottom": "16px"}, children=[
             # Left Config
             html.Div(style={**C_,"padding":"24px","width":"240px","minWidth":"240px", "display":"flex","flexDirection":"column","gap":"12px"}, children=[
                html.Div("🎯 Brake Point Analysis", className="section-title", style={"color":t["bad"]}),
                html.Div([
                    html.Label("Select Turn:", style={"fontSize":"11px","color":t["subtext"],"fontWeight":"bold","display":"block","marginBottom":"6px"}),
                    turn_selector,
                ]),
                html.P("Compare braking profiles across all drivers (up to 6) for a specific turn. X-axis uses distance in meters for precision.",
                       className="section-description", style={"marginTop":"12px"}),
            ]),
            # Comparison Graph
            html.Div(style={"flex": "1"}, children=[
                G(fig_multi_brake_comparison(dfs, turn_label=turn_options[0]["value"] if turn_options else "T1", mode=mode), 
                  mode, full=True, id="brakes-multi-comparison-graph")
            ])
        ]),

        html.Div(className="grid-2", children=[
            # Summary Table
            html.Div(style={**C_,"padding":"16px 20px"}, children=[
                html.Div(f"Brake Zone Summary — {primary['Driver'].iloc[0]}", className="section-title",
                        style={"color":t["gold"],"fontSize":"14px"}),
                dash_table.DataTable(
                    data=zones.to_dict("records"),
                    columns=[{"name":c.replace("_"," "),"id":c} for c in zones.columns],
                    style_header={"backgroundColor":"rgba(0,0,0,0.3)","color":t["gold"],
                                   "fontFamily":"var(--font-mono)","fontSize":"10px",
                                   "fontWeight":"bold","textTransform":"uppercase"},
                    style_cell={"backgroundColor":t["panel"],"color":t["text"],
                                "fontFamily":"var(--font-mono)","fontSize":"12px",
                                "border":f"1px solid {t['border']}","padding":"8px 12px",
                                "textAlign":"center"},
                    sort_action="native", page_size=10,
                )
            ]),
            G(fig_brake_shapes(primary,mode),      mode, full=True),
        ]),
        
        html.Div(className="grid-2", style={"marginTop": "16px"}, children=[
            G(fig_brake_consistency(zones,mode),   mode, full=True),
            G(fig_brake_trail_map(primary,mode),   mode, full=True),
        ]),
    ])