import dash
from dash import html, dcc, dash_table
from ui.components import card, btn, inp, G
from utils import TH, apply_theme
import numpy as np

try:
    from services.ai_feedback import generate_feedback, generate_comparison_feedback, generate_trend_feedback
    AI_OK = True
except ImportError:
    AI_OK = False


def _render_ai_engineer(dfs, mode):
    """⚙️ Algorithmic Race Engineer — algorithmic driving feedback tab."""
    t  = TH(mode); C_ = card(mode)

    if not AI_OK:
        return html.Div(style={**C_,"padding":"20px"}, children=[
            html.P("⚠️  ai_feedback.py module not found.",
                   style={"color":t["warn"],"fontSize":"13px"}),
        ])

    primary = dfs[0]
    
    # 1. Per-corner feedback (existing)
    items = generate_feedback(primary)
    
    # 2. Trend analysis (new — Items 14)
    try:
        trend_items = generate_trend_feedback(primary)
        items.extend(trend_items)
    except Exception:
        pass
    
    # 3. Multi-driver comparison (new — Item 13)
    comparison_items = []
    if len(dfs) >= 2:
        try:
            comparison_items = generate_comparison_feedback(dfs)
        except Exception:
            pass

    # Combine and sort
    all_items = items + comparison_items
    priority_order = {"critical": 0, "warning": 1, "good": 2, "info": 3}
    all_items.sort(key=lambda x: priority_order.get(x.get("priority","info"), 9))

    def _make_card(item):
        border_color = item.get("color", t["accent"])
        prio = item.get("priority","info")
        bg = {"critical":"rgba(239,68,68,0.06)","warning":"rgba(251,146,60,0.06)",
              "good":"rgba(16,185,129,0.06)","info":"rgba(0,212,255,0.04)"}.get(prio,"transparent")
        return html.Div(style={
            "background": bg,
            "borderRadius": "10px",
            "border": f"1px solid {border_color}30",
            "borderLeft": f"4px solid {border_color}",
            "padding": "16px 20px",
            "marginBottom": "10px",
            "transition": "all 0.2s ease",
        }, children=[
            html.Div(style={"display":"flex","alignItems":"center","gap":"10px",
                            "marginBottom":"6px"}, children=[
                html.Span(item.get("icon","ℹ️"),
                          style={"fontSize":"20px"}),
                html.Span(item.get("title",""),
                          style={"fontSize":"14px","fontWeight":"700",
                                 "color":border_color}),
            ]),
            html.P(item.get("detail",""),
                   style={"color":t["subtext"],"fontSize":"12px",
                          "margin":"0","lineHeight":"1.6"}),
        ])

    feedback_cards = [_make_card(item) for item in all_items]

    n_critical = sum(1 for i in all_items if i.get("priority") == "critical")
    n_warning  = sum(1 for i in all_items if i.get("priority") == "warning")
    n_good     = sum(1 for i in all_items if i.get("priority") == "good")

    # Section labels
    sections = []
    
    # Header
    sections.append(html.Div(style={**C_,"padding":"18px 22px","display":"flex",
                    "justifyContent":"space-between","alignItems":"center",
                    "marginBottom":"12px"}, children=[
        html.Div([
            html.Div("⚙️ Algorithmic Race Engineer", className="section-title",
                     style={"color":t["gold"],"marginBottom":"4px"}),
            html.P(f"Driver: {primary['Driver'].iloc[0]}" + 
                   (f" vs {dfs[1]['Driver'].iloc[0]}" if len(dfs) >= 2 else ""),
                   style={"color":t["subtext"],"fontSize":"12px","margin":"0"}),
        ]),
        html.Div(style={"display":"flex","gap":"16px","alignItems":"center"}, children=[
            html.Div(style={"textAlign":"center"}, children=[
                html.Div(f"{n_critical}", style={"fontSize":"20px","fontWeight":"800","color":"#EF4444"}),
                html.Div("Critical", className="metric-label"),
            ]),
            html.Div(style={"textAlign":"center"}, children=[
                html.Div(f"{n_warning}", style={"fontSize":"20px","fontWeight":"800","color":"#FB923C"}),
                html.Div("Warning", className="metric-label"),
            ]),
            html.Div(style={"textAlign":"center"}, children=[
                html.Div(f"{n_good}", style={"fontSize":"20px","fontWeight":"800","color":"#10B981"}),
                html.Div("Good", className="metric-label"),
            ]),
        ]),
    ]))
    
    # Trend section header (if any trend items)
    trend_only = [i for i in all_items if i.get("icon") in ("📈", "📉", "🟠") and "Consistency" not in i.get("title","") or "Consistency" in i.get("title","") or "Throttle Control" in i.get("title","")]
    if trend_items:
        sections.append(html.Div(style={"marginTop": "8px", "marginBottom": "8px"}, children=[
            html.Div("📊 Session Trend Analysis", style={
                "fontSize": "13px", "fontWeight": "700", "color": t["accent"],
                "padding": "8px 0", "borderBottom": f"1px solid {t['border']}",
            }),
        ]))
        for item in trend_items:
            sections.append(_make_card(item))
    
    # Comparison section header
    if comparison_items:
        sections.append(html.Div(style={"marginTop": "12px", "marginBottom": "8px"}, children=[
            html.Div("🔄 Driver Comparison", style={
                "fontSize": "13px", "fontWeight": "700", "color": "#A855F7",
                "padding": "8px 0", "borderBottom": f"1px solid {t['border']}",
            }),
        ]))
        for item in comparison_items:
            sections.append(_make_card(item))

    # Per-corner section
    corner_items = [i for i in items if i not in trend_items]
    if corner_items:
        sections.append(html.Div(style={"marginTop": "12px", "marginBottom": "8px"}, children=[
            html.Div("🏁 Per-Corner Analysis", style={
                "fontSize": "13px", "fontWeight": "700", "color": t["gold"],
                "padding": "8px 0", "borderBottom": f"1px solid {t['border']}",
            }),
        ]))
        corner_items.sort(key=lambda x: priority_order.get(x.get("priority","info"), 9))
        for item in corner_items:
            sections.append(_make_card(item))

    return html.Div(className="fade-in", children=sections)