import dash
from dash import html, dcc, dash_table
from ui.components import card, btn, inp, G
from utils import TH, apply_theme
import numpy as np
from plotting.gps_maps import get_plottable_channels, fig_channel_on_gps


def _render_channel_gps(dfs, mode, channel=None):
    t       = TH(mode); C_ = card(mode)
    primary = dfs[0]
    channels= get_plottable_channels(primary)
    channel = channel or (channels[0] if channels else "Speed")

    dd = dcc.Dropdown(
        id="channel-gps-dd",
        options=[{"label":c,"value":c} for c in channels],
        value=channel, clearable=False,
        style={"fontSize":"13px", "backgroundColor": "#1E2028", "color": "#C9CDD6", "border": "none"}
    )

    return html.Div(className="fade-in", style={"display":"flex", "gap":"16px"}, children=[
        # Left Panel: Controls
        html.Div(style={**C_,"padding":"24px","width":"240px","minWidth":"240px", "display":"flex","flexDirection":"column","gap":"12px"}, children=[
            html.Div("📡 Channel Map", className="section-title", style={"color":t["accent"]}),
            html.Div([
                html.Label("Channel Selector:", style={"fontSize":"11px","color":t["subtext"],"fontWeight":"bold","display":"block","marginBottom":"6px"}),
                dd,
            ]),
            html.P("Select any numeric channel to visualize it on the track map. Perfect for identifying exactly where on track you were slow or aggressive.",
                   className="section-description", style={"marginTop":"12px"}),
        ]),
        # Right Panel: Large Map
        html.Div(style={"flex":"1"}, children=[
            G(fig_channel_on_gps(primary, channel, mode), mode, full=True, h=540)
        ]),
    ])