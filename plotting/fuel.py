import plotly.graph_objects as go

from utils import apply_theme, PALETTE
from services.fuel_service import lap_fuel_table, stint_summary, pit_stops


def _name(df, i):
    return str(df["Driver"].iloc[0]) if "Driver" in df.columns and len(df) else f"Driver {i + 1}"


def _empty(title, mode, msg="No fuel data (FuelLevel channel missing)"):
    fig = go.Figure()
    fig.add_annotation(text=msg, x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)
    return apply_theme(fig, title, mode)


def fig_fuel_level(dfs, mode="dark"):
    """Yakıt seviyesi zaman içinde; pit duraklarında dikey çizgi."""
    fig = go.Figure()
    for i, df in enumerate(dfs):
        if "FuelLevel" not in df.columns:
            continue
        tc = next((c for c in ("Time_s", "Time", "SessionTime") if c in df.columns), None)
        x = (df[tc] - df[tc].iloc[0]) / 60.0 if tc else df.index / 60.0 / 60.0
        step = max(len(df) // 4000, 1)
        fig.add_trace(go.Scattergl(x=x.iloc[::step], y=df["FuelLevel"].iloc[::step], mode="lines",
                                   name=_name(df, i), line=dict(color=PALETTE[i % len(PALETTE)], width=2)))
        if tc:
            for _, st in pit_stops(df).iterrows():
                lap = df[df["LapNumber"] == st["EntryLap"]]
                if not lap.empty:
                    fig.add_vline(x=(lap[tc].iloc[-1] - df[tc].iloc[0]) / 60.0, line_dash="dot",
                                  line_color=PALETTE[i % len(PALETTE)], opacity=0.5)
    if not fig.data:
        return _empty("Fuel Level", mode)
    fig.update_layout(xaxis_title="Session time (min)", yaxis_title="Fuel (L)")
    return apply_theme(fig, "Fuel Level (dotted = pit stop)", mode)


def fig_fuel_per_lap(dfs, mode="dark"):
    """Tur başına tüketim (yalnızca geçerli ölçümler); Flying dışı turlar soluk."""
    fig = go.Figure()
    for i, df in enumerate(dfs):
        lf = lap_fuel_table(df).dropna(subset=["FuelUsed"])
        if lf.empty:
            continue
        color = PALETTE[i % len(PALETTE)]
        opac = [1.0 if t == "Flying" else 0.35 for t in lf["LapType"]]
        fig.add_trace(go.Bar(x=lf["LapNumber"], y=lf["FuelUsed"], name=_name(df, i),
                             marker=dict(color=color, opacity=opac),
                             customdata=lf[["StintNumber", "LapType"]].values,
                             hovertemplate="Lap %{x}<br>%{y:.2f} L<br>Stint %{customdata[0]} · %{customdata[1]}<extra></extra>"))
    if not fig.data:
        return _empty("Fuel per Lap", mode)
    fig.update_layout(barmode="group", xaxis_title="Lap", yaxis_title="Fuel used (L)")
    return apply_theme(fig, "Fuel per Lap (faded = non-flying lap)", mode)


def fig_stint_compare(dfs, mode="dark"):
    """Stint bazında ortalama tüketim, sürücüler yan yana."""
    fig = go.Figure()
    for i, df in enumerate(dfs):
        s = stint_summary(df).dropna(subset=["AvgFuelPerLap"]) if "FuelLevel" in df.columns else None
        if s is None or s.empty:
            continue
        fig.add_trace(go.Bar(x=[f"Stint {k}" for k in s["Stint"]], y=s["AvgFuelPerLap"], name=_name(df, i),
                             marker_color=PALETTE[i % len(PALETTE)]))
    if not fig.data:
        return _empty("Stint Comparison", mode)
    fig.update_layout(barmode="group", yaxis_title="Avg fuel per lap (L)")
    return apply_theme(fig, "Stint Comparison — average consumption", mode)
