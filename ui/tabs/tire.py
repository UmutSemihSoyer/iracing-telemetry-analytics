import dash
from dash import html, dcc, dash_table
from ui.components import card, btn, inp, G
from utils import TH, apply_theme
import numpy as np

try:
    from core.tire_analysis import TireAnalyzer
    TIRE_OK = True
except ImportError:
    TIRE_OK = False


def _render_tire_tab(dfs, mode, tire_type=None, unit="metric"):
    t  = TH(mode); C_ = card(mode)
    
    if not TIRE_OK:
        return html.Div(style={**C_,"padding":"20px"}, children=[
            html.P("⚠️  tire_analysis.py module not found.",
                   style={"color":t["warn"],"fontSize":"13px"}),
        ])

    primary = dfs[0]
    
    # Tire Type Selector (Manual Override)
    # tire_type=None means auto-detect
    tyre_dd = dcc.Dropdown(
        id="tire-type-dd",
        options=[
            {"label": "🔍 Auto (Telemetry)", "value": None},
            {"label": "☀️ Dry (Slick)", "value": "Dry"},
            {"label": "🌧️ Wet (Rain)", "value": "Wet"}
        ],
        value=tire_type,
        clearable=False,
        style={"fontSize": "13px", "backgroundColor": "#1E2028", "color": "#C9CDD6", "border": "none"}
    )

    try:
        # Pass manual tire_type and unit to analyzer
        ta = TireAnalyzer(primary, tire_type=tire_type, unit=unit)
        
        if not ta.has_real_tire_data():
            return html.Div(style={**C_,"padding":"24px", "textAlign":"center"}, children=[
                html.P(f"No tire temperature telemetry found for this vehicle.",
                       style={"color":t["warn"],"fontSize":"14px","marginBottom":"10px"}),
                html.P("Some iRacing cars only provide carcass (internal) or surface temps. We try to fallback automatically.",
                       className="section-description"),
            ])
            
        f_surf = ta.fig_surface_temps(mode)
        f_win  = ta.fig_operating_window(mode)
        f_deg  = ta.fig_degradation(mode)
        f_grip = ta.fig_grip_map(mode)
        f_fade = ta.fig_fade_analysis(mode)
        f_wear = ta.fig_wear(mode)
        
        summ_df = ta.corner_summary()
        
        table = dash_table.DataTable(
            data=summ_df.to_dict("records"),
            columns=[{"name":c,"id":c} for c in summ_df.columns],
            style_header={"backgroundColor":"rgba(0,0,0,0.3)","color":t["gold"],
                           "fontFamily":"var(--font-mono)","fontSize":"10px",
                           "fontWeight":"bold","textTransform":"uppercase"},
            style_cell={"backgroundColor":t["panel"],"color":t["text"],
                        "fontFamily":"var(--font-mono)","fontSize":"12px",
                        "border":f"1px solid {t['border']}","padding":"8px 12px",
                        "textAlign":"center"},
        )
        
        import dash_bootstrap_components as dbc
        
        # Build Pressure Optimizer Widget
        pressures = ta.calculate_optimal_cold_pressures(24.0)
        pressure_widget = html.Div(style={**C_,"padding":"16px 20px","flex":"1.5"}, children=[
            html.Div("⚖️ Pressure Optimizer (Target: 24.0 PSI)", className="section-title", style={"color":t["accent"],"fontSize":"13px"}),
        ])
        if pressures:
            boxes = []
            for corner in ["FL", "FR", "RL", "RR"]:
                adj = pressures['adjustments'].get(corner, 0)
                color = t["good"] if abs(adj) < 0.3 else (t["warn"] if abs(adj) < 1.0 else "#EF4444")
                sign = "+" if adj > 0 else ""
                boxes.append(html.Div(style={"flex":"1", "textAlign":"center", "background":"var(--panel-bg)", "padding":"8px", "borderRadius":"6px", "border":f"1px solid {t['border']}"}, children=[
                    html.Div(corner, style={"fontSize":"11px", "color":t["subtext"], "fontWeight":"bold"}),
                    html.Div(f"{pressures['current_hot'].get(corner, 0):.1f}", style={"fontSize":"14px", "fontWeight":"bold", "color":t["text"]}),
                    html.Div(f"{sign}{adj} PSI", style={"fontSize":"12px", "color":color, "fontWeight":"bold", "marginTop":"4px"})
                ]))
            
            pressure_widget.children.append(html.Div(style={"display":"flex","gap":"10px","marginTop":"8px"}, children=boxes))
        else:
            pressure_widget.children.append(html.P("Pressure data not available in telemetry.", style={"color":t["subtext"],"fontSize":"12px"}))


        return html.Div(className="fade-in", children=[
            # Config Row
            html.Div(style={"display":"flex","gap":"16px","marginBottom":"16px"}, children=[
                html.Div(style={**C_,"padding":"16px 20px","flex":"1"}, children=[
                    html.Label("Tire Configuration:", style={"fontSize":"11px","color":t["subtext"],"fontWeight":"bold","display":"block","marginBottom":"6px"}),
                    html.Div(style={"width":"180px"}, children=[tyre_dd]),
                    html.P(f"Current: {ta.tire_type}", 
                           style={"fontSize":"12px","color":t["gold"],"marginTop":"8px","fontWeight":"600"}),
                ]),
                pressure_widget
            ]),

            html.Div(className="grid-2", style={"marginBottom":"16px"}, children=[
                G(f_win, mode, full=True),
                G(f_fade, mode, full=True),
            ]),
            html.Div(style={"marginBottom":"16px"}, children=[
                G(f_surf, mode, full=True, h=500),
            ]),
            html.Div(className="grid-2", style={"marginBottom":"16px"}, children=[
                G(f_deg, mode, full=True),
                G(f_grip, mode, full=True),
            ]),
            html.Div(style={"marginBottom":"16px"}, children=[
                G(f_wear, mode, full=True, h=350),
            ]),
            html.Div(style={**C_,"padding":"16px 20px"}, children=[
                html.Div("📊 Corner Summary & Camber Advice",
                        className="section-title", style={"color":t["gold"]}),
                table
            ]),
        ])
    except Exception as e:
        return html.Div(style={**C_,"padding":"20px"}, children=[
            html.P(f"Error rendering tire analysis: {e}",
                   style={"color":"#EF4444","fontSize":"13px"}),
        ])