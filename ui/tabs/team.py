from dash import html, dcc

from ui.components import card
from utils import TH
from services.team_service import driver_summary, sector_delta_matrix, mixed_tracks, setup_diff
from plotting.team import fig_sector_delta_heatmap, fig_driver_bests
from ui.tabs.fuel import _table


def _fmt_time(s):
    if s != s:   # NaN
        return "—"
    m, sec = divmod(float(s), 60)
    return f"{int(m)}:{sec:06.3f}"


def _render_team(dfs, mode="dark", metas=None):
    """👥 Team tab — load several drivers' files for the same track to compare them."""
    t = TH(mode)
    C_ = card(mode)
    if not dfs or len(dfs) < 2:
        return html.Div("👥 Load at least two files (e.g. different drivers, same track) to compare them.",
                        style={"color": t["warn"], "padding": "20px"})
    s = driver_summary(dfs)
    show = s.copy()
    for c in ("Best", "Median"):
        show[c] = show[c].map(_fmt_time)
    show["Gap"] = show["Gap"].map(lambda g: "—" if g != g else f"+{g:.3f}")
    show["Std"] = show["Std"].map(lambda g: "—" if g != g else f"{g:.2f}")
    show["Fuel/lap"] = show["Fuel/lap"].map(lambda g: "—" if g != g else f"{g:.2f}")
    show["Top km/h"] = show["Top km/h"].map(lambda g: "—" if g != g else f"{g:.0f}")
    warn = []
    if mixed_tracks(dfs):
        warn = [html.Div("⚠️ The loaded files are from different tracks — slice deltas are not comparable.",
                         style={"color": t["warn"], "marginBottom": "10px"})]
    sd = setup_diff(dfs, metas or [])
    if sd.empty:
        setup_block = html.Div("Setup differences: no differing numeric setup values found "
                               "(or setups are not embedded in these files).",
                               style={"color": t["subtext"], "fontSize": "12px"})
    else:
        sd = sd.round(3).reset_index().rename(columns={"index": "Parameter"})
        setup_block = _table(sd, mode, "team-setup-table")
    return html.Div([
        *warn,
        html.Div(style={**C_, "padding": "16px 20px"}, children=[
            html.H4("👥 Driver comparison", style={"margin": "0 0 8px"}),
            _table(show, mode, "team-summary-table"),
            html.P("Std = lap-time consistency over flying laps (lower is better).", className="section-description"),
        ]),
        html.Div(style={**C_, "marginTop": "16px", "padding": "16px 20px"}, children=[
            html.H4("🔧 Setup differences", style={"margin": "0 0 4px"}),
            html.P("Only numeric parameters that differ between the loaded files. Descriptive: with a handful of "
                   "files this cannot show which change made the car faster.", className="section-description"),
            setup_block]),
        html.Div(style={**C_, "marginTop": "16px", "padding": "16px 20px"}, children=[
            dcc.Graph(id="team-bests-graph", figure=fig_driver_bests(s, mode))]),
        html.Div(style={**C_, "marginTop": "16px", "padding": "16px 20px"}, children=[
            dcc.Graph(id="team-heatmap-graph", figure=fig_sector_delta_heatmap(sector_delta_matrix(dfs), mode))]),
    ])
