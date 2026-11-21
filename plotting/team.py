import plotly.graph_objects as go
from utils import TH, apply_theme


def fig_sector_delta_heatmap(matrix, mode="dark"):
    """Sürücü × pist dilimi: en hızlıya göre kaybedilen süre."""
    t = TH(mode)
    fig = go.Figure()
    if matrix is None or matrix.empty:
        fig.add_annotation(text="Need at least one file with Time and LapDistPct", showarrow=False,
                           font=dict(color=t["subtext"]))
    else:
        fig.add_trace(go.Heatmap(
            z=matrix.values, x=list(matrix.columns), y=list(matrix.index),
            colorscale=[[0, "#16a34a"], [0.15, "#facc15"], [1, "#dc2626"]], zmin=0,
            colorbar=dict(title="s lost"),
            hovertemplate="%{y} · %{x}<br>+%{z:.3f} s<extra></extra>"))
    fig.update_layout(height=max(220, 60 * (len(matrix.index) if matrix is not None else 1) + 120))
    return apply_theme(fig, "Time lost per track slice vs fastest driver (best lap)", mode)


def fig_driver_bests(summary, mode="dark"):
    t = TH(mode)
    fig = go.Figure()
    if summary is not None and not summary.empty:
        s = summary.dropna(subset=["Gap"])
        fig.add_trace(go.Bar(x=s["Driver"], y=s["Gap"], marker_color=t["accent"],
                             hovertemplate="%{x}<br>+%{y:.3f} s<extra></extra>"))
        fig.update_yaxes(title="Gap to fastest best lap (s)")
    fig.update_layout(height=320)
    return apply_theme(fig, "Best-lap gap", mode)
