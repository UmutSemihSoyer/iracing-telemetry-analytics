import dash
from dash import html
from ui.components import card, G
from utils import TH
from plotting.dynamics import fig_slip_angle_map, fig_understeer_scatter

def _render_dynamics(dfs, mode="dark"):
    """🏎️ Dynamics Tab — Renders Slip Angle and Balance telemetry"""
    t = TH(mode)
    C_ = card(mode)
    
    if not dfs:
        return html.Div("No data loaded.", style={"color": t["warn"], "padding": "20px"})
        
    primary = dfs[0]
    
    # Generate figures
    f_slip = fig_slip_angle_map(dfs, mode)
    f_steer = fig_understeer_scatter(dfs, mode)
    
    return html.Div(className="fade-in", children=[
        html.Div(style={"display":"flex","gap":"16px","marginBottom":"16px"}, children=[
            html.Div(style={**C_,"padding":"16px 20px","flex":"1"}, children=[
                html.Div("ℹ️ Vehicle Dynamics & Balance", className="section-title", style={"color":t["accent"],"fontSize":"13px"}),
                html.P("Slip Angle (β) reveals if the car is oversteering (sliding rear) or understeering (pushing front). "
                       "The Scatter plot compares Lateral Accel against Steering Angle (Understeer Gradient).",
                       className="section-description"),
            ]),
            html.Div(style={**C_,"padding":"16px 20px","flex":"1"}, children=[
                html.Div("📊 Channels Loaded", className="section-title", style={"color":t["gold"],"fontSize":"13px"}),
                html.P(f"VelocityX: {'✅' if 'VelocityX' in primary.columns else '❌'} | "
                       f"VelocityY: {'✅' if 'VelocityY' in primary.columns else '❌'} | "
                       f"LatAccel: {'✅' if 'LatAccel' in primary.columns else '❌'}",
                       style={"fontSize": "12px", "color": t["subtext"], "fontWeight": "bold"})
            ])
        ]),
        
        html.Div(style={"marginBottom":"16px"}, children=[
            G(f_slip, mode, full=True, h=550)
        ]),
        
        html.Div(style={"marginBottom":"16px"}, children=[
            G(f_steer, mode, full=True, h=500)
        ]),
    ])
