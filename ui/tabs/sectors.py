import dash
from dash import html, dcc, dash_table
from ui.components import card, btn, inp, G
from utils import TH, apply_theme
import numpy as np
import pandas as pd
from services.telemetry_service import best_lap_df
from plotting.gps_maps import fig_mini_sector_map
from plotting.overlays import fig_corner_comparison

try:
    from core.corner_detector import detect_corners, label_segments, build_segment_map, get_segment_summary, compute_corner_deltas
    CORNER_OK = True
except ImportError:
    CORNER_OK = False

def _build_segment_table(dfs, ref_mode, mode):
    """Helper to build the segment detail DataTable."""
    t = TH(mode); C_ = card(mode)
    
    if not CORNER_OK:
        return html.Div("Corner detection module unavailable.")

    try:
        ref_best = best_lap_df(dfs[0])
        if ref_best.empty:
            return html.Div("No lap data available to build segment map.")
            
        corners = detect_corners(ref_best)
        seg_map = build_segment_map(corners)
        
        # Build summary for each driver
        all_summaries = []
        for di, df in enumerate(dfs):
            driver = df["Driver"].iloc[0] if "Driver" in df.columns else f"Driver {di+1}"
            best = best_lap_df(df)
            if best.empty:
                continue
            summary = get_segment_summary(best, seg_map)
            if not summary.empty:
                summary["Driver"] = driver
                all_summaries.append(summary)
        
        if not all_summaries:
            return html.Div("No segment summaries generated.")

        full_summary = pd.concat(all_summaries, ignore_index=True)
        
        # Merge with delta_df to get the time delta relative to reference
        delta_df, _ = compute_corner_deltas(dfs, ref_mode=ref_mode)
        if not delta_df.empty:
            delta_merge = delta_df[["segment", "driver", "delta_s"]].rename(
                columns={"segment": "Segment", "driver": "Driver", "delta_s": "Delta_s"}
            )
            full_summary = pd.merge(full_summary, delta_merge, on=["Segment", "Driver"], how="left")
            full_summary["Delta_s"] = full_summary["Delta_s"].fillna(0.0)
            full_summary["Delta"] = full_summary["Delta_s"].apply(
                lambda x: f"{x*1000:+.0f}ms" if abs(x) > 0.001 else "-"
            )
        else:
            full_summary["Delta"] = "-"
        
        display_cols = ["Driver", "Segment", "Delta", "Type", "Direction",
                        "Duration_s", "MinSpeed_kmh", "EntrySpeed_kmh",
                        "ExitSpeed_kmh", "AvgLatG", "PeakLatG",
                        "AvgBrake_%", "AvgThrottle_%"]
        display_cols = [c for c in display_cols if c in full_summary.columns]
        
        col_rename = {
            "Duration_s": "Time (s)",
            "MinSpeed_kmh": "Min Spd",
            "EntrySpeed_kmh": "Entry Spd",
            "ExitSpeed_kmh": "Exit Spd",
            "AvgLatG": "Avg G",
            "PeakLatG": "Peak G",
            "AvgBrake_%": "Brake %",
            "AvgThrottle_%": "Throttle %",
        }
        
        table_df = full_summary[display_cols].rename(columns=col_rename)

        # FASTEST IN SEGMENT HIGHLIGHTING
        # For each segment, find rows where Duration_s is the minimum
        # We'll use style_data_conditional
        conditional_styles = [
            {"if": {"filter_query": '{Type} = "Turn"'},
                "backgroundColor": "rgba(0, 212, 255, 0.05)"},
            {"if": {"filter_query": '{Type} = "Straight"'},
                "backgroundColor": "rgba(255, 255, 255, 0.02)"},
        ]

        if len(dfs) > 1:
            # Highlight the fastest driver in each segment
            for seg in full_summary["Segment"].unique():
                seg_rows = full_summary[full_summary["Segment"] == seg]
                if not seg_rows.empty:
                    min_time = seg_rows["Duration_s"].min()
                    fastest_driver = seg_rows[seg_rows["Duration_s"] == min_time]["Driver"].iloc[0]
                    # Note: DataTable filters are on display columns, so we use 'Segment' and 'Driver'
                    conditional_styles.append({
                        "if": {"filter_query": f'{{Segment}} = "{seg}" && {{Driver}} = "{fastest_driver}"',
                               "column_id": "Time (s)"},
                        "backgroundColor": "rgba(16, 185, 129, 0.2)",
                        "color": "#10B981", "fontWeight": "bold"
                    })

        return html.Div(style={**C_, "padding": "16px 20px", "marginTop": "16px"}, children=[
            html.Div("📋 Segment Details", className="section-title", style={"color": t["accent"]}),
            dash_table.DataTable(
                data=table_df.to_dict("records"),
                columns=[{"name": c, "id": c} for c in table_df.columns],
                style_header={
                    "backgroundColor": "rgba(0,0,0,0.3)",
                    "color": t["accent"],
                    "fontFamily": "var(--font-mono)",
                    "fontSize": "10px", "fontWeight": "bold",
                    "textTransform": "uppercase", "letterSpacing": "0.5px",
                },
                style_cell={
                    "backgroundColor": t["panel"], "color": t["text"],
                    "fontFamily": "var(--font-mono)", "fontSize": "11px",
                    "border": f"1px solid {t['border']}",
                    "padding": "6px 8px", "textAlign": "center",
                },
                style_data_conditional=conditional_styles,
                sort_action="native",
                page_size=20,
            ),
        ])
    except Exception as e:
        return html.Div(f"⚠️ Table Error: {e}", style={"color": t["warn"], "padding": "12px"})

def _render_sectors(dfs, mode, ref_mode="best_of_each"):
    t  = TH(mode); C_ = card(mode)
    
    # Selector for the Sectors tab specifically
    ref_selector = dcc.Dropdown(
        id="sectors-mini-sector-ref-mode",
        options=[
            {"label": "🚗 Driver vs Driver", "value": "best_of_each"},
            {"label": "🏆 Individual Optimal", "value": "individual_optimal"},
            {"label": "🌐 Collective Optimal", "value": "collective_optimal"},
        ],
        value=ref_mode,
        clearable=False,
        searchable=False,
        style={"fontSize":"13px", "backgroundColor": "#1E2028", "color": "#C9CDD6", "border": "none"}
    )

    # Initial table load
    seg_table_content = html.Div(id="sectors-mini-sector-table-container", 
                                 children=_build_segment_table(dfs, ref_mode, mode))

    # Corner count info
    n_corners = 0
    n_straights = 0
    if CORNER_OK:
        try:
            ref_best = best_lap_df(dfs[0])
            corners = detect_corners(ref_best) if not ref_best.empty else []
            seg_map = build_segment_map(corners)
            n_corners = len([s for s in seg_map if s["type"] == "Turn"])
            n_straights = len([s for s in seg_map if s["type"] == "Straight"])
        except Exception:
            pass

    return html.Div(className="fade-in", children=[
        html.Div(style={"display": "flex", "gap": "16px"}, children=[
            # Left Panel: Controls
            html.Div(style={**C_, "padding": "24px", "width": "260px", "minWidth": "260px",
                            "display": "flex", "flexDirection": "column", "gap": "12px"}, children=[
                html.Div("🏁 Corner Analysis", className="section-title", style={"color": t["accent"]}),
                html.Div([
                    html.Label("Reference Selection:", style={
                        "fontSize": "11px", "color": t["subtext"],
                        "fontWeight": "bold", "display": "block", "marginBottom": "6px"}),
                    ref_selector,
                ]),
                html.Hr(style={"borderColor": t["border"], "opacity": "0.3"}),
                html.Div([
                    html.Div(style={"display": "flex", "justifyContent": "space-between", "marginBottom": "8px"}, children=[
                        html.Span("🔄 Turns:", style={"fontSize": "12px", "color": t["subtext"]}),
                        html.Span(str(n_corners), style={"fontSize": "13px", "color": t["accent"], "fontWeight": "bold"}),
                    ]),
                    html.Div(style={"display": "flex", "justifyContent": "space-between"}, children=[
                        html.Span("➡️ Straights:", style={"fontSize": "12px", "color": t["subtext"]}),
                        html.Span(str(n_straights), style={"fontSize": "13px", "color": t["text"], "fontWeight": "bold"}),
                    ]),
                ]),
                html.Hr(style={"borderColor": t["border"], "opacity": "0.3"}),
                html.P("Track is auto-segmented into turns and straights using steering angle analysis. "
                       "Each segment is colored by time delta (🟢 faster → 🔴 slower).",
                       className="section-description", style={"marginTop": "4px", "lineHeight": "1.5"}),
            ]),
            # Right Panel: Map
            html.Div(style={"flex": "1"}, children=[
                dcc.Graph(id="sectors-mini-sector-graph",
                          figure=fig_mini_sector_map(dfs, mode=mode, ref_mode=ref_mode),
                          config={"displayModeBar": True},
                          style={"height": "520px"}),
            ]),
        ]),
        # Delta Comparison Bar Chart
        html.Div(style={**C_, "marginTop": "16px", "padding": "16px 20px"}, children=[
            dcc.Graph(id="sectors-corner-comparison",
                      figure=fig_corner_comparison(dfs, mode=mode, ref_mode=ref_mode),
                      config={"displayModeBar": True}),
        ]),
        # Segment Details Table
        seg_table_content,
    ])