import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from utils import apply_theme

def fig_slip_angle_map(dfs, mode="dark"):
    """Shows GPS track colored by Slip Angle (degrees)"""
    if not dfs: return go.Figure()
    
    # Use best lap from primary driver, or just all flying laps of primary
    df = dfs[0]
    
    from core.lap_classifier import filter_flying_laps
    df_f = filter_flying_laps(df)
    if df_f.empty: df_f = df
    
    # Need Lat, Lon to plot MAP
    if "Lat" not in df_f.columns or "Lon" not in df_f.columns:
        fig = go.Figure()
        fig.add_annotation(text="No GPS Data (Lat/Lon)", x=0.5, y=0.5, showarrow=False)
        return apply_theme(fig, "Slip Angle Map", mode)

    # Need SlipAngle
    if "SlipAngle" not in df_f.columns:
        fig = go.Figure()
        fig.add_annotation(text="No SlipAngle Data (Requires VelocityX/Y)", x=0.5, y=0.5, showarrow=False)
        return apply_theme(fig, "Slip Angle Map", mode)

    # Pick the fastest lap for clarity
    if "LapTime_s" in df_f.columns:
        best_lap = df_f.groupby("LapNumber")["LapTime_s"].first().idxmin()
        d = df_f[df_f["LapNumber"] == best_lap]
    else:
        d = df_f
        
    d = d.dropna(subset=["SlipAngle", "Lat", "Lon"])
    if d.empty: return go.Figure()

    # Limit slip angle visualization to -15 to +15 degrees for better color scale
    slip = np.clip(d["SlipAngle"], -15, 15)
    
    fig = go.Figure(go.Scattermapbox(
        lat=d["Lat"], lon=d["Lon"],
        mode="markers",
        marker=dict(
            size=6,
            color=slip,
            colorscale="RdBu",  # Blue = understeer/negative slip? Red = oversteer/positive slip?
            cmin=-10, cmax=10,
            showscale=True,
            colorbar=dict(title="Slip Angle (°)", thickness=10, outlinewidth=0)
        ),
        text=d["SlipAngle"].round(1),
        hovertemplate="Slip Angle: %{text}°<br>Lat/Lon: %{lat:.5f}, %{lon:.5f}<extra></extra>"
    ))
    
    center_lat = d["Lat"].mean()
    center_lon = d["Lon"].mean()

    fig.update_layout(
        mapbox=dict(
            style="carto-darkmatter" if mode=="dark" else "carto-positron",
            center=dict(lat=center_lat, lon=center_lon),
            zoom=14.5
        ),
        margin=dict(l=0, r=0, t=30, b=0),
    )
    return apply_theme(fig, f"🏎️ Dynamic Slip Angle Map (Lap {int(d['LapNumber'].iloc[0])})", mode)


def fig_understeer_scatter(dfs, mode="dark"):
    """Scatter plot: LatAccel vs Steer to detect understeer gradient"""
    if not dfs: return go.Figure()
    
    df = dfs[0]
    from core.lap_classifier import filter_flying_laps
    d = filter_flying_laps(df)
    if d.empty: d = df
    
    if "LatAccel" not in d.columns or "Steer" not in d.columns:
        fig = go.Figure()
        fig.add_annotation(text="No LatAccel or Steer Data", x=0.5, y=0.5, showarrow=False)
        return apply_theme(fig, "Understeer Gradient", mode)

    # Downsample points for scatter performance if large
    if len(d) > 5000:
        d = d.iloc[::max(1, len(d)//5000)]
        
    color_var = d["SlipAngle"] if "SlipAngle" in d.columns else d["Speed"] * 3.6
    colorscale = "RdBu" if "SlipAngle" in d.columns else "Viridis"
    cmin = -10 if "SlipAngle" in d.columns else None
    cmax = 10 if "SlipAngle" in d.columns else None
    col_str = "Slip Angle (°)" if "SlipAngle" in d.columns else "Speed (km/h)"

    fig = go.Figure(go.Scatter(
        x=d["LatAccel"] / 9.81, # Convert to Gs
        y=d["SteeringWheelAngle"] if "SteeringWheelAngle" in d.columns else d["Steer"] * 180, # approximate degrees
        mode="markers",
        marker=dict(
            size=4,
            opacity=0.6,
            color=color_var,
            colorscale=colorscale,
            cmin=cmin, cmax=cmax,
            showscale=True,
            colorbar=dict(title=col_str, thickness=10, outlinewidth=0)
        ),
        hovertemplate="LatG: %{x:.2f}G<br>Steer: %{y:.1f}°<extra></extra>"
    ))
    
    fig.update_layout(
        xaxis_title="Lateral Accel (G)",
        yaxis_title="Steering Angle (°)",
        margin=dict(l=40, r=10, t=30, b=30),
    )
    return apply_theme(fig, "🏎️ Vehicle Balance: Steer vs LatG", mode)
