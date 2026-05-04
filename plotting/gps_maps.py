import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.ndimage import gaussian_filter1d
from utils import TH, apply_theme

try:
    from core.corner_detector import compute_corner_deltas
    CORNER_OK = True
except ImportError:
    CORNER_OK = False

def best_lap_df(df):
    from services.telemetry_service import best_lap_df as get_best
    return get_best(df)

def _add_track_layout_features(fig, df_full, df_best, mode="dark"):
    """Adds pit lane (grey) and start/finish line (checkerboard) to the GPS map."""
    # 1. Pit Lane
    if "OnPitRoad" in df_full.columns and "Lat" in df_full.columns:
        pits = df_full[df_full["OnPitRoad"] == 1]
        if not pits.empty:
            p_lat = gaussian_filter1d(pits["Lat"].values, 2)
            p_lon = gaussian_filter1d(pits["Lon"].values, 2)
            fig.add_trace(go.Scattergl(
                x=p_lon, y=p_lat, mode="lines",
                line=dict(color="rgba(251,146,60,0.7)", width=6, dash="dash"),
                name="Pit Lane", hoverinfo="skip", showlegend=False
            ))

    # 2. Start/Finish Line
    if "LapDistPct" in df_best.columns and len(df_best) > 10:
        idx = (df_best["LapDistPct"] - 0.003).abs().idxmin()
        target_idx = df_best.index.get_loc(idx)
        p1_idx = df_best.index[max(0, target_idx - 3)]
        p2_idx = df_best.index[min(len(df_best)-1, target_idx + 3)]
        lat1, lon1 = df_best.loc[p1_idx, "Lat"], df_best.loc[p1_idx, "Lon"]
        lat2, lon2 = df_best.loc[p2_idx, "Lat"], df_best.loc[p2_idx, "Lon"]
        v_y, v_x = lat2 - lat1, lon2 - lon1
        mag = np.sqrt(v_x**2 + v_y**2)
        if mag > 0:
            nx, ny = -v_y / mag, v_x / mag
            scale = 0.00018
            x_pts = [lon1 + nx*scale, lon1 - nx*scale]
            y_pts = [lat1 + ny*scale, lat1 - ny*scale]
            fig.add_trace(go.Scatter(
                x=x_pts, y=y_pts, mode="lines",
                line=dict(color="#FFFFFF", width=25),
                name="Start/Finish", hoverinfo="skip", showlegend=False
            ))
            fig.add_trace(go.Scatter(
                x=x_pts, y=y_pts, mode="lines",
                line=dict(color="#000000", width=25, dash="dash"),
                name="Checkerboard", hoverinfo="skip", showlegend=False
            ))

def fig_mini_sector_map(dfs: list, n_sectors: int = 20, mode: str = "dark", ref_mode: str = "best_of_each", unit: str = "metric") -> go.Figure:
    t   = TH(mode)
    fig = go.Figure()
    
    is_multi_driver = len(dfs) > 1
    title_suffix = {
        "best_of_each": "Driver vs Driver",
        "individual_optimal": "Best Lap vs Other Laps",
        "collective_optimal": "Collective vs Session Best",
    }.get(ref_mode, "")

    if not any("Lat" in df.columns for df in dfs):
        return apply_theme(fig, "GPS Data Required", mode)

    df_base = best_lap_df(dfs[0])
    if df_base.empty: df_base = dfs[0]
    df_base = _filter_gps_jumps(df_base)
    
    if len(df_base) < 10 or "Lat" not in df_base.columns:
        fig.add_annotation(text="Not enough GPS data.", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False, font=dict(color=t["subtext"]))
        return apply_theme(fig, "🗺️ Corner Map", mode)
    
    lat_s   = gaussian_filter1d(df_base["Lat"].values, 4)
    lon_s   = gaussian_filter1d(df_base["Lon"].values, 4)
    
    # Grey track outline (background)
    fig.add_trace(go.Scattergl(
        x=lon_s, y=lat_s, mode="lines",
        line=dict(color=t["border"], width=8),
        showlegend=False, hoverinfo="skip", name="Track"
    ))

    # ── Try corner detection ──
    has_delta = False
    delta_df = pd.DataFrame()
    seg_map = []
    if CORNER_OK:
        delta_df, seg_map = compute_corner_deltas(dfs, ref_mode=ref_mode)
        # Check if delta data is meaningful (not all zeros)
        if not delta_df.empty and delta_df["delta_s"].abs().max() > 0.001:
            has_delta = True

    pct = df_base["LapDistPct"].values

    if has_delta and seg_map:
        # ═══════════════════════════════════════════════════════
        # MODE: Delta coloring (multi-driver OR lap-vs-lap)
        # ═══════════════════════════════════════════════════════
        max_delta = delta_df["delta_s"].abs().max() + 1e-9
        target_driver = dfs[-1]["Driver"].iloc[0]
        driver_deltas = delta_df[delta_df["driver"] == target_driver]

        for seg in seg_map:
            seg_label = seg["label"]
            seg_type  = seg["type"]
            
            if seg["end_pct"] >= 0.99:
                mask = (pct >= seg["start_pct"]) & (pct <= seg["end_pct"])
            else:
                mask = (pct >= seg["start_pct"]) & (pct < seg["end_pct"])
            if not mask.any(): continue
            
            seg_delta_row = driver_deltas[driver_deltas["segment"] == seg_label]
            delta = float(seg_delta_row["delta_s"].iloc[0]) if not seg_delta_row.empty else 0
            avg_spd = float(seg_delta_row["avg_speed_kmh"].iloc[0]) if not seg_delta_row.empty else 0
            if unit == "imperial": avg_spd *= 0.621371
            
            norm = np.clip(delta / max_delta, -1, 1)
            if norm <= 0:  # Faster → Green
                r = int(50 + 205 * (1 + norm)); g = 220; b = int(80 + 40 * (1 + norm))
            else:  # Slower → Red
                r = 255; g = int(100 * (1 - norm)); b = int(50 * (1 - norm))
                
            min_spd = float(seg_delta_row["min_speed_kmh"].iloc[0]) if not seg_delta_row.empty else 0
            duration = float(seg_delta_row["time_s"].iloc[0]) if not seg_delta_row.empty else 0
            if unit == "imperial": min_spd *= 0.621371

            type_icon = "🔄" if seg_type == "Turn" else "➡️"
            unit_str = "km/h" if unit == "metric" else ("mph" if unit == "imperial" else unit)
            hover_txt = (f"<b>{target_driver}</b><br>{type_icon} {seg_label} ({seg_type})<br>"
                         f"Delta: {delta:+.3f}s<br>Time: {duration:.2f}s<br>"
                         f"Avg Speed: {avg_spd:.1f} {unit_str}<br>Min Speed: {min_spd:.1f} {unit_str}")
                         
            fig.add_trace(go.Scatter(
                x=lon_s[mask], y=lat_s[mask], mode="lines",
                line=dict(width=7, color=f"rgb({r},{g},{b})"),
                name=seg_label, hovertext=hover_txt, hoverinfo="text",
                showlegend=False,
            ))
        
        title_text = f"🗺️ Corner Map — {title_suffix}"
    else:
        # ═══════════════════════════════════════════════════════
        # MODE: Speed colorscale (single driver fallback)
        # ═══════════════════════════════════════════════════════
        if "Speed" in df_base.columns:
            spd = df_base["Speed"].values * 3.6
            if unit == "imperial": spd *= 0.621371
            unit_str = "km/h" if unit == "metric" else "mph"
            fig.add_trace(go.Scattergl(
                x=lon_s, y=lat_s, mode="markers",
                marker=dict(size=5, color=spd, colorscale="RdYlGn",
                            showscale=True,
                            colorbar=dict(title=f"Speed ({unit_str})", len=0.6)),
                showlegend=False,
                hovertemplate=f"Speed: %{{marker.color:.1f}} {unit_str}<extra></extra>",
            ))
        title_text = f"🗺️ Corner Map — Speed (single driver)"

    # ── Add Turn labels only (not Straights — reduces clutter) ──
    if seg_map:
        for seg in seg_map:
            if seg["type"] != "Turn":
                continue  # Skip straight labels
            mid_pct = (seg["start_pct"] + seg["end_pct"]) / 2
            dists = np.abs(pct - mid_pct)
            if len(dists) == 0: continue
            mid_idx = np.argmin(dists)
            dir_txt = ""
            if seg["direction"] == "L": dir_txt = " ⟵"
            elif seg["direction"] == "R": dir_txt = " ⟶"
            
            fig.add_trace(go.Scatter(
                x=[lon_s[mid_idx]], y=[lat_s[mid_idx]], mode="text",
                text=[f"{seg['label']}{dir_txt}"],
                textfont=dict(size=10, color=t["accent"],
                              family="ui-monospace, monospace"),
                showlegend=False, hoverinfo="skip",
            ))

    _add_track_layout_features(fig, dfs[0], df_base, mode)
    fig.update_yaxes(scaleanchor="x", scaleratio=1, showticklabels=False, showgrid=False, zeroline=False)
    fig.update_xaxes(showticklabels=False, showgrid=False, zeroline=False)
    fig.update_layout(hovermode="closest", showlegend=False)
    return apply_theme(fig, title_text, mode)

# NOTE: fig_corner_comparison lives in plotting/overlays.py — removed duplicate from here

def get_plottable_channels(df: pd.DataFrame) -> list:
    skip = {"Lat","Lon","Alt","LapDistPct","LapNumber","Driver",
            "Driver_State","Micro_Sector","_sec","TrackName"}
    return [c for c in df.columns if c not in skip and pd.api.types.is_numeric_dtype(df[c]) and df[c].std() > 0]

def fig_channel_on_gps(df: pd.DataFrame, channel: str, mode: str = "dark") -> go.Figure:
    t = TH(mode)
    fig = go.Figure()
    if "Lat" not in df.columns or channel not in df.columns:
        fig.add_annotation(text=f"GPS or channel '{channel}' not available.",
                           xref="paper",yref="paper",x=0.5,y=0.5,
                           showarrow=False,font=dict(color=t["subtext"]))
        return apply_theme(fig, f"🗺️ GPS — {channel}", mode)

    d = best_lap_df(df).copy()
    d = _filter_gps_jumps(d)
    if len(d) < 10:
        fig.add_annotation(text="Not enough clean GPS data (active reset?).",
                           xref="paper",yref="paper",x=0.5,y=0.5,
                           showarrow=False,font=dict(color=t["subtext"]))
        return apply_theme(fig, f"🗺️ GPS — {channel}", mode)
    lat_s = gaussian_filter1d(d["Lat"].values, 2)
    lon_s = gaussian_filter1d(d["Lon"].values, 2)
    vals = d[channel].values
    vmin = np.percentile(vals, 5); vmax = np.percentile(vals, 95)
    custom_data = np.column_stack((vals,))
    fig.add_trace(go.Scattergl(
        x=lon_s, y=lat_s, mode="markers", customdata=custom_data,
        marker=dict(size=4, color=vals, colorscale="Plasma", cmin=vmin, cmax=vmax, showscale=False),
        name=df["Driver"].iloc[0],
        hovertemplate=f"<b>%{{fullData.name}}</b><br>{channel}: %{{customdata[0]:.2f}}<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode="markers",
        marker=dict(colorscale="Plasma", cmin=vmin, cmax=vmax,
            colorbar=dict(title=channel, len=0.55, tickvals=[vmin, (vmin+vmax)/2, vmax],
                           ticktext=[f"{vmin:.1f}",f"{(vmin+vmax)/2:.1f}",f"{vmax:.1f}"]),
            showscale=True, size=0), showlegend=False,
    ))
    fig.update_yaxes(scaleanchor="x", scaleratio=1, showticklabels=False, showgrid=False, zeroline=False)
    fig.update_xaxes(showticklabels=False, showgrid=False, zeroline=False)
    return apply_theme(fig, f"🗺️ GPS — {channel}", mode)

def _filter_gps_jumps(df: pd.DataFrame) -> pd.DataFrame:
    """Remove GPS teleportation jumps caused by active reset.
    
    Detects sudden large jumps in Lat/Lon and removes those points
    to prevent broken map rendering.
    """
    if "Lat" not in df.columns or len(df) < 10:
        return df
    lat = df["Lat"].values
    lon = df["Lon"].values
    dlat = np.abs(np.diff(lat, prepend=lat[0]))
    dlon = np.abs(np.diff(lon, prepend=lon[0]))
    dist = np.sqrt(dlat**2 + dlon**2)
    # Threshold: any jump larger than 10x the median step is a teleport
    median_step = np.median(dist[dist > 0]) if (dist > 0).any() else 1e-6
    threshold = max(median_step * 10, 1e-4)
    clean_mask = dist < threshold
    # Also remove a few points after a jump (settling noise)
    jump_indices = np.where(~clean_mask)[0]
    for idx in jump_indices:
        end = min(idx + 5, len(clean_mask))
        clean_mask[idx:end] = False
    return df[clean_mask].copy() if clean_mask.sum() > 10 else df


def fig_gps_speed(dfs, mode,unit='metric'):
    fig = go.Figure()
    for df in dfs:
        if "Lat" not in df.columns: continue
        d = best_lap_df(df)
        d = _filter_gps_jumps(d)
        if len(d) < 10:
            continue
        lat_s = gaussian_filter1d(d["Lat"].values, 2)
        lon_s = gaussian_filter1d(d["Lon"].values, 2)
        spd = d["Speed"].values * 3.6
        display_unit = "km/h" if unit == "metric" else ("mph" if unit == "imperial" else unit)
        fig.add_trace(go.Scattergl(
            x=lon_s, y=lat_s, mode="markers",
            marker=dict(size=3, color=spd, colorscale="RdYlGn", showscale=False),
            name=df["Driver"].iloc[0], showlegend=False,
            hovertemplate=f"<b>%{{fullData.name}}</b><br>Speed: %{{marker.color:.1f}} {display_unit}<extra></extra>"
        ))
    if dfs:
        d_best = best_lap_df(dfs[0])
        d_best = _filter_gps_jumps(d_best)
        _add_track_layout_features(fig, dfs[0], d_best, mode)
    display_unit = "km/h" if unit == "metric" else ("mph" if unit == "imperial" else unit)
    fig.update_yaxes(scaleanchor="x", scaleratio=1, showticklabels=False, showgrid=False, zeroline=False)
    fig.update_xaxes(showticklabels=False, showgrid=False, zeroline=False)
    return apply_theme(fig, f"🗺️ GPS — Speed ({display_unit})", mode)
