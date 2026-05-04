"""
🎯 Driving Style Tab — Comprehensive Driver Coaching Metrics
=============================================================
Combines:
  - Corner Phase Analysis (Entry/Apex/Exit speeds)
  - Coasting & Overlap breakdown (per-lap)
  - Throttle Smoothness scoring
  - Trail Brake Scoring (0-100 per zone)
  - ABS & TC Activation Tracking
"""

import dash
from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import pandas as pd

from ui.components import card, G
from utils import TH, apply_theme, PALETTE, infer_hz

from core.corner_detector import (
    get_corner_phase_analysis,
    score_trail_braking,
    compute_driving_style_metrics,
    compute_abs_tc_events,
    compute_sector_fuel,
)


# ════════════════════════════════════════════════════════════════════════════
# FIGURES
# ════════════════════════════════════════════════════════════════════════════

def _fig_corner_phases(phase_df, mode="dark"):
    """Bar chart showing Entry/Apex/Exit speeds per turn (best lap)."""
    t = TH(mode)
    fig = go.Figure()

    if phase_df.empty:
        fig.add_annotation(text="No corner phase data available.",
                           xref="paper", yref="paper", x=0.5, y=0.5,
                           showarrow=False, font=dict(color=t["subtext"]))
        return apply_theme(fig, "🏁 Corner Phase Analysis", mode)

    # Use only best lap (lowest lap number in flying laps is usually the fastest)
    best_lap = phase_df["Lap"].min()
    best = phase_df[phase_df["Lap"] == best_lap]

    turns = best["Turn"].values
    fig.add_trace(go.Bar(
        name="Entry", x=turns, y=best["v_entry"],
        marker_color="#00D4FF", text=best["v_entry"].round(0),
        textposition="outside", textfont=dict(size=9),
    ))
    fig.add_trace(go.Bar(
        name="Apex", x=turns, y=best["v_apex"],
        marker_color="#FF3B5C", text=best["v_apex"].round(0),
        textposition="outside", textfont=dict(size=9),
    ))
    fig.add_trace(go.Bar(
        name="Exit", x=turns, y=best["v_exit"],
        marker_color="#10B981", text=best["v_exit"].round(0),
        textposition="outside", textfont=dict(size=9),
    ))

    fig.update_layout(
        barmode="group",
        xaxis_title="Turn",
        yaxis_title="Speed (km/h)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    return apply_theme(fig, f"🏁 Corner Phase Analysis — Entry / Apex / Exit (Lap {best_lap})", mode)


def _fig_brake_depth_trail(phase_df, mode="dark"):
    """Combined chart: brake depth % and trail braking % per turn."""
    t = TH(mode)
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if phase_df.empty:
        fig.add_annotation(text="No brake depth data.", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False)
        return apply_theme(fig, "🛑 Brake Depth & Trail Braking", mode)

    best_lap = phase_df["Lap"].min()
    best = phase_df[phase_df["Lap"] == best_lap]
    turns = best["Turn"].values

    fig.add_trace(go.Bar(
        name="Brake Depth %", x=turns, y=best["Brake_depth_%"],
        marker_color="rgba(239,68,68,0.7)",
        text=best["Brake_depth_%"].round(0), textposition="inside",
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        name="Trail Brake %", x=turns, y=best["Trail_%"],
        mode="markers+lines",
        marker=dict(size=10, color="#A855F7", symbol="diamond"),
        line=dict(color="#A855F7", width=2),
    ), secondary_y=True)

    fig.update_yaxes(title_text="Brake Depth (%)", secondary_y=False, range=[0, 110])
    fig.update_yaxes(title_text="Trail Brake (%)", secondary_y=True, range=[0, 110])
    fig.update_xaxes(title_text="Turn")
    return apply_theme(fig, "🛑 Brake Depth & Trail Braking per Turn", mode)


def _fig_trail_scores(zones, mode="dark"):
    """Horizontal bar chart of trail brake scores with color grades."""
    t = TH(mode)
    fig = go.Figure()

    if not zones:
        fig.add_annotation(text="No brake zones detected.", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False, font=dict(color=t["subtext"]))
        return apply_theme(fig, "🏆 Trail Brake Score Card", mode)

    grade_colors = {"A": "#10B981", "B": "#00D4FF", "C": "#FBBF24", "D": "#FF8C00", "F": "#EF4444"}
    labels = [f"Z{z['Zone']} ({z['Track_%']:.0f}%)" for z in zones]
    scores = [z["Score"] for z in zones]
    colors = [grade_colors.get(z["Grade"], "#888") for z in zones]

    fig.add_trace(go.Bar(
        x=scores, y=labels, orientation="h",
        marker_color=colors,
        text=[f"{s} ({z['Grade']})" for s, z in zip(scores, zones)],
        textposition="inside",
        textfont=dict(size=11, family="ui-monospace", color="white"),
    ))

    fig.update_layout(
        xaxis=dict(title="Score (0–100)", range=[0, 105]),
        yaxis=dict(autorange="reversed"),
        height=max(250, len(zones) * 35 + 80),
    )
    return apply_theme(fig, "🏆 Trail Brake Score Card (Best Lap)", mode)


def _fig_style_trend(style_df, mode="dark"):
    """Line chart showing coasting % and throttle smoothness across laps."""
    t = TH(mode)
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if style_df.empty:
        fig.add_annotation(text="No driving style data.", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False)
        return apply_theme(fig, "📈 Driving Style Trend", mode)

    flying = style_df[style_df["LapType"] == "Flying"]
    if flying.empty:
        flying = style_df

    fig.add_trace(go.Scatter(
        name="Coasting %", x=flying["Lap"], y=flying["Coasting_%"],
        mode="lines+markers", line=dict(color="#FF8C00", width=2),
        marker=dict(size=7),
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        name="Overlap %", x=flying["Lap"], y=flying["Overlap_%"],
        mode="lines+markers", line=dict(color="#EF4444", width=2, dash="dot"),
        marker=dict(size=6),
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        name="Throttle Smoothness", x=flying["Lap"], y=flying["Throttle_Smoothness"],
        mode="lines+markers", line=dict(color="#10B981", width=2),
        marker=dict(size=7, symbol="square"),
    ), secondary_y=True)

    fig.update_yaxes(title_text="Coasting / Overlap (%)", secondary_y=False)
    fig.update_yaxes(title_text="Smoothness Score (0–100)", secondary_y=True, range=[0, 105])
    fig.update_xaxes(title_text="Lap Number")

    return apply_theme(fig, "📈 Driving Style Trend — Lap by Lap", mode)


def _fig_sector_fuel(fuel_df, mode="dark"):
    """Bar chart showing fuel consumption per segment."""
    t = TH(mode)
    fig = go.Figure()

    if fuel_df.empty:
        fig.add_annotation(text="No sector fuel data (FuelLevel channel required).",
                           xref="paper", yref="paper", x=0.5, y=0.5,
                           showarrow=False, font=dict(color=t["subtext"]))
        return apply_theme(fig, "⛽ Sector Fuel Consumption", mode)

    colors = ["#EF4444" if r["Type"] == "Turn" else "#00D4FF" for _, r in fuel_df.iterrows()]

    fig.add_trace(go.Bar(
        x=fuel_df["Segment"], y=fuel_df["FuelUsed_ml"],
        marker_color=colors,
        text=fuel_df["FuelUsed_ml"].round(0), textposition="outside",
        textfont=dict(size=9),
    ))
    fig.update_layout(
        xaxis_title="Segment", yaxis_title="Fuel Used (ml)",
    )
    return apply_theme(fig, "⛽ Sector Fuel Consumption (Best Lap)", mode)


# ════════════════════════════════════════════════════════════════════════════
# MAIN RENDER
# ════════════════════════════════════════════════════════════════════════════

def _render_driving_style(dfs, mode="dark"):
    """Render the complete Driving Style tab."""
    t = TH(mode)
    C_ = card(mode)

    if not dfs:
        return html.Div("No data loaded.", style={"color": t["warn"], "padding": "20px"})

    primary = dfs[0]
    hz = infer_hz(primary)

    # ── Compute all metrics ──
    phase_df = get_corner_phase_analysis(primary, hz)
    trail_zones = score_trail_braking(primary, hz)
    style_df = compute_driving_style_metrics(primary, hz)
    abs_tc = compute_abs_tc_events(primary, hz)
    fuel_df = compute_sector_fuel(primary, hz)

    # ── Summary cards ──
    avg_trail = round(np.mean([z["Score"] for z in trail_zones]), 0) if trail_zones else 0
    avg_coast = round(style_df[style_df["LapType"] == "Flying"]["Coasting_%"].mean(), 1) if not style_df.empty and (style_df["LapType"] == "Flying").any() else 0
    avg_smooth = round(style_df[style_df["LapType"] == "Flying"]["Throttle_Smoothness"].mean(), 0) if not style_df.empty and (style_df["LapType"] == "Flying").any() else 0
    avg_overlap = round(style_df[style_df["LapType"] == "Flying"]["Overlap_%"].mean(), 1) if not style_df.empty and (style_df["LapType"] == "Flying").any() else 0

    def _grade_color(score):
        if score >= 80: return t["good"]
        if score >= 60: return t["accent"]
        if score >= 40: return t["warn"]
        return "#EF4444"

    def _coast_color(pct):
        if pct < 3: return t["good"]
        if pct < 6: return t["warn"]
        return "#EF4444"

    def _metric_card(label, value, color, subtitle=""):
        return html.Div(style={
            **C_, "flex": "1", "padding": "18px 20px", "textAlign": "center",
            "borderTop": f"3px solid {color}",
        }, children=[
            html.Div(label, className="metric-label", style={"marginBottom": "6px"}),
            html.Div(str(value), style={
                "fontSize": "28px", "fontWeight": "800",
                "fontFamily": "var(--font-mono)", "color": color,
            }),
            html.Div(subtitle, style={"fontSize": "11px", "color": t["subtext"], "marginTop": "4px"}) if subtitle else None,
        ])

    summary_row = html.Div(style={"display": "flex", "gap": "14px", "marginBottom": "18px"}, children=[
        _metric_card("Trail Brake Avg", f"{avg_trail:.0f}/100", _grade_color(avg_trail), "Brake zones"),
        _metric_card("Throttle Smoothness", f"{avg_smooth:.0f}", _grade_color(avg_smooth), "0=choppy 100=silk"),
        _metric_card("Coasting", f"{avg_coast:.1f}%", _coast_color(avg_coast), "Dead pedal time"),
        _metric_card("Overlap", f"{avg_overlap:.1f}%", _coast_color(avg_overlap * 10), "Gas+Brake at once"),
        _metric_card("ABS Events", str(abs_tc["abs_activations"]),
                     t["warn"] if abs_tc["abs_activations"] > 5 else t["good"],
                     f'{abs_tc["abs_duration_s"]:.1f}s total'),
        _metric_card("TC Events", str(abs_tc["tc_activations"]),
                     t["warn"] if abs_tc["tc_activations"] > 5 else t["good"],
                     f'{abs_tc["tc_duration_s"]:.1f}s total'),
    ])

    # ── Corner phase table ──
    phase_table = html.Div()
    if not phase_df.empty:
        best_lap = phase_df["Lap"].min()
        best_phase = phase_df[phase_df["Lap"] == best_lap]
        phase_table = html.Div(style={**C_, "padding": "16px 20px", "marginBottom": "16px"}, children=[
            html.Div("🏁 Corner Phase Detail (Best Lap)", className="section-title",
                     style={"color": t["gold"], "marginBottom": "10px"}),
            dash_table.DataTable(
                data=best_phase.to_dict("records"),
                columns=[{"name": c, "id": c} for c in best_phase.columns if c not in ("Driver", "Lap")],
                style_header={
                    "backgroundColor": "rgba(0,0,0,0.3)", "color": t["gold"],
                    "fontFamily": "var(--font-mono)", "fontSize": "10px",
                    "fontWeight": "bold", "textTransform": "uppercase",
                },
                style_cell={
                    "backgroundColor": t["panel"], "color": t["text"],
                    "fontFamily": "var(--font-mono)", "fontSize": "12px",
                    "border": f"1px solid {t['border']}", "padding": "8px 10px",
                    "textAlign": "center",
                },
                style_data_conditional=[
                    {"if": {"filter_query": "{Trail_%} >= 30"},
                     "color": t["good"], "fontWeight": "bold"},
                    {"if": {"filter_query": "{Trail_%} < 10"},
                     "color": "#EF4444", "fontWeight": "bold"},
                    {"if": {"filter_query": "{Coasting_%} >= 10"},
                     "color": "#EF4444"},
                ],
                sort_action="native",
                page_size=20,
            ),
        ])

    # ── Trail brake score breakdown table ──
    trail_table = html.Div()
    if trail_zones:
        tz_df = pd.DataFrame(trail_zones)
        trail_table = html.Div(style={**C_, "padding": "16px 20px", "marginBottom": "16px"}, children=[
            html.Div("🏆 Trail Brake Score Breakdown", className="section-title",
                     style={"color": t["accent"], "marginBottom": "10px"}),
            dash_table.DataTable(
                data=tz_df.to_dict("records"),
                columns=[{"name": c, "id": c} for c in tz_df.columns],
                style_header={
                    "backgroundColor": "rgba(0,0,0,0.3)", "color": t["accent"],
                    "fontFamily": "var(--font-mono)", "fontSize": "10px",
                    "fontWeight": "bold", "textTransform": "uppercase",
                },
                style_cell={
                    "backgroundColor": t["panel"], "color": t["text"],
                    "fontFamily": "var(--font-mono)", "fontSize": "12px",
                    "border": f"1px solid {t['border']}", "padding": "8px 10px",
                    "textAlign": "center",
                },
                style_data_conditional=[
                    {"if": {"filter_query": '{Grade} = "A"'}, "color": "#10B981", "fontWeight": "bold"},
                    {"if": {"filter_query": '{Grade} = "B"'}, "color": "#00D4FF"},
                    {"if": {"filter_query": '{Grade} = "D"'}, "color": "#FF8C00"},
                    {"if": {"filter_query": '{Grade} = "F"'}, "color": "#EF4444", "fontWeight": "bold"},
                ],
                sort_action="native",
            ),
        ])

    # ── Build figures ──
    fig_phases = _fig_corner_phases(phase_df, mode)
    fig_brake = _fig_brake_depth_trail(phase_df, mode)
    fig_trail = _fig_trail_scores(trail_zones, mode)
    fig_trend = _fig_style_trend(style_df, mode)
    fig_fuel = _fig_sector_fuel(fuel_df, mode)

    return html.Div(className="fade-in", children=[
        # Info bar
        html.Div(style={"display": "flex", "gap": "16px", "marginBottom": "16px"}, children=[
            html.Div(style={**C_, "padding": "16px 20px", "flex": "1"}, children=[
                html.Div("🎯 Driving Style Analysis", className="section-title",
                         style={"color": t["accent"], "fontSize": "14px"}),
                html.P("Comprehensive metrics to improve your driving technique. "
                       "Trail brake score, coasting analysis, throttle smoothness, and ABS/TC tracking.",
                       className="section-description"),
            ]),
        ]),

        # Summary cards
        summary_row,

        # Corner Phase charts
        html.Div(className="grid-2", style={"marginBottom": "16px"}, children=[
            G(fig_phases, mode, full=True),
            G(fig_brake, mode, full=True),
        ]),

        # Trail brake & Driving style
        html.Div(className="grid-2", style={"marginBottom": "16px"}, children=[
            G(fig_trail, mode, full=True),
            G(fig_trend, mode, full=True),
        ]),

        # Fuel
        html.Div(style={"marginBottom": "16px"}, children=[
            G(fig_fuel, mode, full=True),
        ]),

        # Tables
        phase_table,
        trail_table,
    ])
