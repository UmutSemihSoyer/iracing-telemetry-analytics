import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from utils import TH, apply_theme, PALETTE

def best_lap_df(df):
    from services.telemetry_service import best_lap_df as get_best
    return get_best(df)



def fig_brake_shapes(df: pd.DataFrame, mode: str = "dark", unit="metric") -> go.Figure:
    """
    Overlay all brake zone shapes normalised 0→1 in time.
    Fast zones = green, slow zones = red.
    Reveals application / release asymmetry.
    """
    t       = TH(mode)
    d       = best_lap_df(df).copy().reset_index(drop=True)
    braking = (d["Brake"] > 0.05).astype(int)
    starts  = list(d.index[braking.diff() ==  1])
    ends    = list(d.index[braking.diff() == -1])

    fig  = go.Figure()
    ei   = 0
    zone_speeds = []

    for s in starts:
        while ei < len(ends) and ends[ei] <= s: ei += 1
        if ei >= len(ends): break
        e = ends[ei]
        if (e - s) < 5: continue
        seg   = d.loc[s:e, "Brake"].values
        speed = d.loc[s, "Speed"]
        zone_speeds.append(speed)
        t_norm = np.linspace(0, 1, len(seg))
        unit_str = "km/h" if unit == "metric" else "mph"
        entry_speed = speed * (3.6 if unit == "metric" else 2.23694)
        fig.add_trace(go.Scatter(
            x=t_norm, y=seg*100,
            mode="lines",
            line=dict(width=1.2, color="rgba(100,100,100,0.3)"),
            showlegend=False,
            hovertemplate=f"Entry speed: {entry_speed:.1f} {unit_str}<extra></extra>",
        ))

    # Average shape
    if zone_speeds:
        max_len = max(len(d.loc[s:e,"Brake"])
                      for s,e in zip(starts, ends) if e-s >= 5)
        shapes = []
        ei = 0
        for s in starts:
            while ei < len(ends) and ends[ei] <= s: ei += 1
            if ei >= len(ends): break
            e = ends[ei]
            if (e-s) < 5: continue
            seg = d.loc[s:e,"Brake"].values
            interp = np.interp(np.linspace(0,1,max_len),
                                np.linspace(0,1,len(seg)), seg)
            shapes.append(interp)
        avg = np.mean(shapes, axis=0)
        fig.add_trace(go.Scatter(
            x=np.linspace(0,1,len(avg)), y=avg*100,
            mode="lines", name="Average",
            line=dict(color=t["accent"], width=3),
        ))

    fig.update_layout(
        xaxis_title="Normalised Brake Zone (0=entry, 1=exit)",
        yaxis_title="Brake Pressure (%)",
        hovermode="x unified",
    )
    return apply_theme(fig, "🛑 Brake Zone Shape Overlay", mode)

def fig_multi_brake_comparison(dfs: list, turn_label: str = "T1", mode: str = "dark") -> go.Figure:
    """
    Overlays brake pressure curves for all drivers in a specific turn.
    X-axis is distance (meters), allowing for direct brake point comparison.
    """
    t = TH(mode)
    fig = go.Figure()

    if not dfs:
        return apply_theme(fig, "No data loaded", mode)

    # We need a reference distance range for the X-axis
    # Let's find the turn window from the first driver
    ref_df = best_lap_df(dfs[0])
    if ref_df.empty or "Segment" not in ref_df.columns:
        fig.add_annotation(text="Layout detection required (best lap not found)",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return apply_theme(fig, f"🛑 Multi-Driver Brake Comparison — {turn_label}", mode)

    turn_data = ref_df[ref_df["Segment"] == turn_label]
    if turn_data.empty:
        fig.add_annotation(text=f"Turn {turn_label} not found in this layout",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return apply_theme(fig, f"🛑 Multi-Driver Brake Comparison — {turn_label}", mode)

    # Use a window: start_pct - 0.02 to end_pct + 0.01 to see the braking zone before the turn
    start_pct = turn_data["LapDistPct"].min()
    end_pct = turn_data["LapDistPct"].max()
    window_start = max(0, start_pct - 0.03) # 3% before
    window_end = min(1.0, end_pct + 0.01)   # 1% after

    for di, df in enumerate(dfs[:6]): # Limit to 6 drivers
        driver = df["Driver"].iloc[0] if "Driver" in df.columns else f"Driver {di+1}"
        best = best_lap_df(df)
        if best.empty: continue
        
        color = PALETTE[di % len(PALETTE)]
        
        # Filter for the window
        mask = (best["LapDistPct"] >= window_start) & (best["LapDistPct"] <= window_end)
        d_win = best[mask].copy()
        if d_win.empty: continue
        
        # Distance calculation (meters)
        # Fallback to a better guess if LapDist missing (Standard track ~5km if missing)
        dist_x = d_win["LapDist"].values if "LapDist" in d_win.columns else d_win["LapDistPct"].values * 5000
        
        # Brake Point Detection
        bp_mask = d_win["Brake"] > 0.05
        if bp_mask.any():
            bp_idx = d_win[bp_mask].index[0]
            bp_dist = d_win.loc[bp_idx, "LapDist"] if "LapDist" in d_win.columns else d_win.loc[bp_idx, "LapDistPct"] * 1000
            
            # Vertical line for brake point
            fig.add_vline(x=bp_dist, line=dict(color=color, width=1, dash="dot"), 
                          annotation_text=f"{driver} BP", annotation_position="top")

        fig.add_trace(go.Scatter(
            x=dist_x, y=d_win["Brake"] * 100,
            mode="lines",
            name=driver,
            line=dict(color=color, width=2),
            hovertemplate=f"<b>{driver}</b><br>Brake: %{{y:.1f}}%<br>Dist: %{{x:.0f}}m<extra></extra>"
        ))

    fig.update_layout(
        xaxis_title="Distance (m)",
        yaxis_title="Brake Pressure (%)",
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"),
    )
    
    return apply_theme(fig, f"🛑 Brake Point Comparison — {turn_label}", mode)

def analyse_brake_zones(df: pd.DataFrame, hz: float = 60.0) -> pd.DataFrame:
    """
    Extract every braking event and measure:
    - Peak pressure
    - Application rate (0→peak, bar/s)
    - Release rate (peak→0, bar/s)
    - Duration (s)
    - Trail-brake depth (% of event with steer > threshold)
    - Entry speed
    """
    d       = best_lap_df(df).copy().reset_index(drop=True)
    braking = (d["Brake"] > 0.05).astype(int)
    starts  = list(d.index[braking.diff() ==  1])
    ends    = list(d.index[braking.diff() == -1])

    zones = []
    ei    = 0
    for s in starts:
        while ei < len(ends) and ends[ei] <= s: ei += 1
        if ei >= len(ends): break
        e   = ends[ei]
        if (e - s) < 5: continue
        seg = d.loc[s:e]

        peak_idx     = seg["Brake"].idxmax()
        peak_val     = seg.loc[peak_idx, "Brake"]
        # Samples from start to peak, peak to end
        ramp_samples = max(1, peak_idx - s)
        release_samples = max(1, e - peak_idx)

        app_rate = (peak_val / ramp_samples)   * hz   # bar/s proxy
        rel_rate = (peak_val / release_samples)* hz

        trail = 0.0
        if "Steer" in d.columns:
            trail = (seg["Steer"].abs() > 0.08).mean() * 100

        zones.append({
            "Zone":           len(zones)+1,
            "Track_Pos_%":    round(d.loc[s,"LapDistPct"]*100, 1),
            "Entry_Speed":    round(d.loc[s,"Speed"], 1),
            "Peak_Brake_%":   round(peak_val*100, 1),
            "App_Rate":       round(app_rate, 2),
            "Release_Rate":   round(rel_rate, 2),
            "Duration_s":     round((e-s)/hz, 3),
            "Trail_Brake_%":  round(trail, 1),
            "LapNumber":      d.loc[s,"LapNumber"] if "LapNumber" in d.columns else 1,
        })

    return pd.DataFrame(zones)

from scipy.ndimage import gaussian_filter1d

def fig_brake_consistency(zones_df: pd.DataFrame, mode: str='dark') -> go.Figure:
    'Scatter: track position vs peak brake pressure — consistency view.'
    t = TH(mode)
    fig = make_subplots(rows=1, cols=2, subplot_titles=['Peak Brake vs Track Position', 'Application Rate vs Entry Speed'])
    if zones_df.empty:
        return apply_theme(fig, '🛑 Brake Analysis', mode)
    fig.add_trace(go.Scatter(x=zones_df['Track_Pos_%'], y=zones_df['Peak_Brake_%'], mode='markers+text', marker=dict(color=t['accent'], size=10, opacity=0.8, symbol='triangle-down'), text=[f'Z{z}' for z in zones_df['Zone']], textposition='top center', textfont=dict(size=8), name='Peak Brake'), row=1, col=1)
    fig.add_trace(go.Scatter(x=(zones_df['Entry_Speed'] * 3.6), y=zones_df['App_Rate'], mode='markers', marker=dict(size=12, color=zones_df['App_Rate'], colorscale='RdYlGn_r', showscale=True, colorbar=dict(title='App Rate', len=0.5, x=1.05)), text=[f'Z{z} Trail:{tr:.0f}%' for (z, tr) in zip(zones_df['Zone'], zones_df['Trail_Brake_%'])], hovertemplate='%{text}<extra></extra>', name='App Rate'), row=1, col=2)
    fig.update_xaxes(title_text='Track Position (%)', row=1, col=1)
    fig.update_yaxes(title_text='Peak Brake (%)', row=1, col=1)
    fig.update_xaxes(title_text='Entry Speed (km/h)', row=1, col=2)
    fig.update_yaxes(title_text='Application Rate', row=1, col=2)
    fig.update_layout(hovermode='closest')
    return apply_theme(fig, '🛑 Brake Consistency & Aggression', mode)

def fig_brake_trail_map(df: pd.DataFrame, mode: str='dark') -> go.Figure:
    'GPS map showing trail-braking depth (% of brake zone with steering).'
    t = TH(mode)
    fig = go.Figure()
    if (('Lat' not in df.columns) or ('Steer' not in df.columns)):
        fig.add_annotation(text='GPS + Steering channels required.', xref='paper', yref='paper', x=0.5, y=0.5, showarrow=False, font=dict(color=t['subtext']))
        return apply_theme(fig, '🗺️ Trail Braking Map', mode)
    d = best_lap_df(df).copy()
    lat_s = gaussian_filter1d(d['Lat'].values, 2)
    lon_s = gaussian_filter1d(d['Lon'].values, 2)
    trail = ((d['Brake'] > 0.1) & (d['Steer'].abs() > 0.08)).values.astype(float)
    trail_colorscale = [[0.0, 'rgb(100,100,80)'], [1.0, 'rgb(168,0,200)']]
    fig.add_trace(go.Scattergl(x=lon_s, y=lat_s, mode='markers', marker=dict(size=4, color=trail, colorscale=trail_colorscale, showscale=False), showlegend=False, hoverinfo='skip'))
    fig.update_yaxes(scaleanchor='x', scaleratio=1, showticklabels=False, showgrid=False, zeroline=False)
    fig.update_xaxes(showticklabels=False, showgrid=False, zeroline=False)
    return apply_theme(fig, '🗺️ Trail Braking Depth Map  (🟣 = trail braking)', mode)