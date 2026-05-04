import dash
from dash import html, dcc, dash_table
from ui.components import card, btn, inp, G
from utils import TH, apply_theme
import numpy as np
from services.telemetry_service import lap_times
from plotting.gps_maps import get_plottable_channels
from plotting.overlays import fig_stacked_overlay
from config import DEFAULT_STACK_CHANNELS


def _render_overlay(dfs, mode, channels=None, selected_laps=None):
    t       = TH(mode); C_ = card(mode)
    primary = dfs[0]
    all_ch  = get_plottable_channels(primary)
    sel     = channels or [c for c in DEFAULT_STACK_CHANNELS if c in all_ch]

    # Get available lap numbers from all drivers (ALL laps including outlap/inlap)
    try:
        from core.lap_classifier import filter_flying_laps
    except ImportError:
        def filter_flying_laps(df): return df

    all_lap_info = {}  # lap_num -> lap_type
    for df in dfs:
        if "LapType" in df.columns:
            for ln in sorted(df["LapNumber"].unique()):
                ltype = df[df["LapNumber"] == ln]["LapType"].iloc[0] if not df[df["LapNumber"] == ln].empty else "Unknown"
                all_lap_info[ln] = ltype
        else:
            for ln in sorted(df["LapNumber"].unique()):
                all_lap_info[ln] = "Flying"

    # Type icons for the dropdown
    type_icons = {"Flying": "🟢", "Outlap": "🟠", "Inlap": "🔵", "DNF": "❌", "Unknown": "⚪"}

    # Lap options
    lap_options = [
        {"label": "🏆 Best Lap Only", "value": "best"},
        {"label": "📊 All Laps (Flying)", "value": "all"},
    ] + [{"label": f"{type_icons.get(ltype, '⚪')} Lap {ln} ({ltype})", "value": ln}
         for ln, ltype in sorted(all_lap_info.items())]

    # Figure out current lap selection value
    lap_value = selected_laps if selected_laps else ["best"]

    dd = dcc.Dropdown(
        id="overlay-channels-dd",
        options=[{"label":c,"value":c} for c in all_ch],
        value=sel, multi=True, clearable=False,
        style={"fontSize":"13px"},
    )

    lap_dd = dcc.Dropdown(
        id="overlay-laps-dd",
        options=lap_options,
        value=lap_value, multi=True, clearable=False,
        style={"fontSize":"13px"},
    )

    return html.Div(className="fade-in", style={"display":"flex", "gap":"16px"}, children=[
        # Left Panel: Controls
        html.Div(style={**C_,"padding":"24px","width":"240px","minWidth":"240px", "display":"flex","flexDirection":"column","gap":"12px"}, children=[
            html.Div("📈 Overlay Config", className="section-title", style={"color":t["accent"]}),
            html.Div([
                html.Label("Active Channels:", style={"fontSize":"11px","color":t["subtext"],"fontWeight":"bold","display":"block","marginBottom":"6px"}),
                dd,
            ]),
            html.Div([
                html.Label("Lap Selection:", style={"fontSize":"11px","color":t["subtext"],"fontWeight":"bold","display":"block","marginBottom":"6px"}),
                lap_dd,
            ]),
            html.P("Select channels and laps to compare. Use 'All Laps' to see every flying lap overlaid, or pick specific laps for targeted analysis.",
                   className="section-description", style={"marginTop":"12px"}),
        ]),
        # Right Panel: Large Chart
        html.Div(style={"flex":"1"}, children=[
            G(fig_stacked_overlay(dfs, sel, mode, selected_laps=lap_value), mode, full=True)
        ]),
    ])