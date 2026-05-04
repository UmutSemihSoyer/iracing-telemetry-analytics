import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from utils import TH, apply_theme, PALETTE
from services.telemetry_service import lap_times

try:
    from core.corner_detector import compute_corner_deltas
    CORNER_OK = True
except ImportError:
    CORNER_OK = False

def best_lap_df(df):
    from services.telemetry_service import best_lap_df as get_best
    return get_best(df)



def fig_stacked_overlay(dfs: list, channels: list,
                         mode: str = "dark",
                         selected_laps: list = None) -> go.Figure:
    """
    Industry-standard stacked telemetry view.
    Each channel = one row, all aligned on LapDistPct.
    Multiple drivers overlaid in each row, colour-coded.
    selected_laps: list of lap numbers to show, or None/"best" for best only.
                   Use ["all"] to show all flying laps.
    """
    from scipy.ndimage import uniform_filter1d
    try:
        from core.lap_classifier import filter_flying_laps
    except ImportError:
        def filter_flying_laps(df): return df

    t = TH(mode)
    lap_colors = px.colors.qualitative.Prism + px.colors.qualitative.Vivid + px.colors.qualitative.Bold

    # Filter to channels that exist in at least one df
    avail = [c for c in channels
             if any(c in df.columns for df in dfs)]
    if not avail:
        fig = go.Figure()
        fig.add_annotation(text="No matching channels found.",
                           xref="paper",yref="paper",x=0.5,y=0.5,
                           showarrow=False,font=dict(color=t["subtext"]))
        return apply_theme(fig,"📊 Multi-Channel Overlay",mode)

    # Determine if we're in multi-lap mode
    # Priority: "all" > specific laps > "best"
    show_all = selected_laps and "all" in selected_laps
    has_specific = selected_laps and any(isinstance(v, (int, float)) for v in selected_laps)
    show_best_only = (not selected_laps) or (selected_laps == ["best"]) or ("best" in selected_laps and not show_all and not has_specific)

    n    = len(avail)
    fig  = make_subplots(
        rows=n, cols=1,
        shared_xaxes=True,
        subplot_titles=avail,
        vertical_spacing=0.02,
    )

    for row, channel in enumerate(avail, start=1):
        for di, df in enumerate(dfs):
            if channel not in df.columns: continue
            driver = df["Driver"].iloc[0]
            driver_color = PALETTE[di % len(PALETTE)]

            # Determine which laps to plot
            if show_best_only:
                laps_to_plot = [best_lap_df(df)]
                lap_labels = ["best"]
            else:
                # Get all flying laps for "all" mode
                flying_df = filter_flying_laps(df)
                if flying_df.empty:
                    flying_df = df
                all_flying_nums = sorted(flying_df["LapNumber"].unique())
                all_total_nums = sorted(df["LapNumber"].unique())

                if show_all:
                    # "All Laps" = only flying laps
                    lap_nums = all_flying_nums
                    source_df = flying_df
                else:
                    # Specific laps selected — search in ALL data (incl. outlap/inlap)
                    lap_nums = [ln for ln in selected_laps if ln in all_total_nums]
                    if not lap_nums:
                        lap_nums = all_flying_nums
                    source_df = df

                laps_to_plot = [source_df[source_df["LapNumber"] == ln] for ln in lap_nums]
                lap_labels = [f"L{ln}" for ln in lap_nums]

            # Best lap number for highlighting
            lt = lap_times(df, flying_only=True)
            best_ln = lt.iloc[0]["LapNumber"] if not lt.empty else None

            for li, (lap_df, lap_label) in enumerate(zip(laps_to_plot, lap_labels)):
                if lap_df.empty: continue

                # Smooth for display
                y = lap_df[channel].values
                if len(y) > 60:
                    y = uniform_filter1d(y, size=5)

                # Color & style logic
                is_best = (lap_label == "best") or (not show_best_only and lap_df["LapNumber"].iloc[0] == best_ln)

                if show_best_only:
                    color = driver_color
                    width = 1.6
                    trace_name = driver
                    legend_group = driver
                else:
                    # Multi-lap mode: each lap gets different color
                    if len(dfs) > 1:
                        # Multiple drivers: use driver color with varying opacity
                        color = driver_color
                        width = 2.5 if is_best else 1.2
                        trace_name = f"{'🏆 ' if is_best else ''}{driver} {lap_label}"
                        legend_group = f"{driver}_{lap_label}"
                    else:
                        # Single driver: vivid distinct colors per lap
                        color = lap_colors[li % len(lap_colors)]
                        width = 2.5 if is_best else 1.4
                        trace_name = f"{'🏆 ' if is_best else ''}{lap_label}"
                        legend_group = lap_label

                fig.add_trace(go.Scattergl(
                    x=lap_df["LapDistPct"]*100, y=y,
                    mode="lines",
                    name=trace_name,
                    line=dict(color=color, width=width),
                    opacity=1.0 if is_best else 0.7,
                    legendgroup=legend_group,
                    showlegend=(row == 1),
                    hovertemplate=f"{channel}: %{{y:.3f}}<extra>{trace_name}</extra>",
                ), row=row, col=1)

        fig.update_yaxes(title_text=channel, row=row, col=1,
                         gridcolor=t["grid"], zerolinecolor=t["zero"],
                         title_font=dict(size=10))

    fig.update_xaxes(title_text="Track Position (%)",
                     row=n, col=1, gridcolor=t["grid"])
    fig.update_layout(
        hovermode="x unified",
        height=max(300, n * 140),
        legend=dict(orientation="h", y=1.02, x=0),
    )
    title_suffix = " (All Laps)" if show_all else (" (Selected Laps)" if not show_best_only else " (Best Lap)")
    return apply_theme(fig, f"📊 Stacked Multi-Channel Overlay{title_suffix}", mode)

def fig_lap_compare(dfs, mode, unit='metric'):
    from plotly.subplots import make_subplots

    # ── Corner detection ──────────────────────────────────────────────
    try:
        from core.corner_detector import detect_corners, build_segment_map
        ref_df = dfs[0]
        # Use best lap for corner detection
        _lt = lap_times(ref_df, flying_only=True)
        if not _lt.empty:
            best_ln = _lt.iloc[0]["LapNumber"]
            ref_lap = ref_df[ref_df["LapNumber"] == best_ln]
        else:
            ref_lap = ref_df
        corners = detect_corners(ref_lap)
        seg_map = build_segment_map(corners)
        has_corners = len(corners) > 0
    except Exception:
        corners = []
        seg_map = []
        has_corners = False

    t = TH(mode)

    # ── 2-row subplot: speed trace (top, large) + corner strip (bottom, tiny)
    if has_corners:
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            row_heights=[0.88, 0.12],
            vertical_spacing=0.02,
        )
    else:
        fig = make_subplots(rows=1, cols=1)

    # Farklı turlar için geniş bir renk paleti kullanıyoruz
    lap_colors = px.colors.qualitative.Prism + px.colors.qualitative.Vivid

    for i, df in enumerate(dfs):
        driver = df["Driver"].iloc[0]
        driver_base_color = PALETTE[i % len(PALETTE)]
        lt = lap_times(df)
        if lt.empty:
            continue

        best_lap = lt.iloc[0]["LapNumber"]
        all_laps = sorted(df["LapNumber"].unique())

        for j, lap in enumerate(all_laps):
            d = df[df["LapNumber"] == lap]
            is_best = (lap == best_lap)

            # Dinamik isim
            name = f"{'🏆 ' if is_best else ''}{driver if len(dfs) > 1 else ''} L{lap}".strip()
            color = lap_colors[j % len(lap_colors)] if len(dfs) == 1 else driver_base_color

            # Mapping unit display string
            display_unit = "km/h" if unit == "metric" else ("mph" if unit == "imperial" else unit)

            fig.add_trace(go.Scattergl(
                x=d["LapDistPct"], y=d["Speed"] * 3.6, mode="lines",
                name=name,
                line=dict(
                    color=driver_base_color if (not is_best and len(dfs) > 1) else color,
                    width=3 if is_best else 1.2,
                    dash="solid",
                ),
                opacity=1.0,
                showlegend=True,
                hovertemplate="<b>%{fullData.name}</b>: %{y:.1f} " + display_unit + "<extra></extra>"
            ), row=1, col=1)

    # ── Corner strip (bottom row) ─────────────────────────────────────
    if has_corners and seg_map:
        turn_color   = "rgba(239, 68, 68, 0.55)"    # kırmızımsı
        straight_clr = "rgba(16, 185, 129, 0.25)"    # yeşilimsi
        turn_border  = "rgba(239, 68, 68, 0.8)"
        straight_brd = "rgba(16, 185, 129, 0.5)"

        x_list = []
        width_list = []
        color_list = []
        line_color_list = []
        annotations = []
        shapes = []

        for seg in seg_map:
            is_turn = seg["type"] == "Turn"
            clr = turn_color if is_turn else straight_clr
            brd = turn_border if is_turn else straight_brd

            # Bar in the corner strip
            mid_pct = (seg["start_pct"] + seg["end_pct"]) / 2
            width_pct = seg["end_pct"] - seg["start_pct"]

            x_list.append(mid_pct)
            width_list.append(width_pct)
            color_list.append(clr)
            line_color_list.append(brd)

            # Label annotation
            dir_arrow = ""
            if is_turn and seg.get("direction"):
                dir_arrow = " ↰" if seg["direction"] == "L" else " ↱"

            annotations.append(dict(
                x=mid_pct,
                y=0.5,
                text=f"<b>{seg['label']}{dir_arrow}</b>",
                showarrow=False,
                font=dict(
                    size=8 if width_pct < 0.03 else 9,
                    color="white" if is_turn else t["subtext"],
                    family="var(--font-mono), monospace",
                ),
                xref="x2", yref="y2",
                xanchor="center",
                yanchor="middle",
            ))

            # Light vrect overlays on the SPEED chart for turn zones
            if is_turn:
                shapes.append(dict(
                    type="rect",
                    x0=seg["start_pct"], x1=seg["end_pct"],
                    y0=0, y1=1,
                    xref="x", yref="y domain",
                    fillcolor="rgba(239, 68, 68, 0.06)",
                    line_width=0,
                    layer="below"
                ))

        # Add everything in batch to bypass Plotly's O(N^2) trace addition overhead
        fig.add_trace(go.Bar(
            x=x_list,
            y=[1]*len(x_list),
            width=width_list,
            marker=dict(
                color=color_list,
                line=dict(color=line_color_list, width=0.5),
            ),
            showlegend=False,
            hoverinfo="skip",
        ), row=2, col=1)

        existing_annotations = list(fig.layout.annotations) if fig.layout.annotations else []
        existing_shapes = list(fig.layout.shapes) if fig.layout.shapes else []
        fig.update_layout(
            annotations=existing_annotations + annotations,
            shapes=existing_shapes + shapes
        )

        # Clean up corner strip axes
        fig.update_yaxes(
            visible=False, range=[0, 1],
            row=2, col=1,
        )
        fig.update_xaxes(
            title_text="Lap Distance (%)",
            tickformat=".0%",
            gridcolor=t["grid"],
            range=[0, 1],
            dtick=0.1,
            row=2, col=1,
        )
        # Remove x title from top chart
        fig.update_xaxes(
            showticklabels=False,
            row=1, col=1,
        )
    else:
        fig.update_xaxes(
            title_text="Lap Distance (%)",
            tickformat=".0%",
            row=1, col=1,
        )

    display_unit = "km/h" if unit == "metric" else ("mph" if unit == "imperial" else unit)

    fig.update_yaxes(
        title_text=f"Speed ({display_unit})",
        gridcolor=t["grid"],
        row=1, col=1,
    )

    fig.update_layout(
        hovermode="x unified",
        barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=420,
    )
    return apply_theme(fig, "📊 Lap Comparison", mode)

def fig_corner_comparison(dfs: list, mode: str = "dark",
                           ref_mode: str = "best_of_each") -> go.Figure:
    """
    Bar chart comparing segment times between drivers.
    Each bar = one segment (T1, S1, T2, S2, ...),
    colored by delta (green=faster, red=slower).
    """
    t = TH(mode)
    fig = go.Figure()

    if not CORNER_OK:
        fig.add_annotation(text="Corner detector not available.",
                           xref="paper", yref="paper", x=0.5, y=0.5,
                           showarrow=False, font=dict(color=t["subtext"]))
        return apply_theme(fig, "📊 Corner Comparison", mode)

    delta_df, seg_map = compute_corner_deltas(dfs, ref_mode=ref_mode)

    if delta_df.empty:
        fig.add_annotation(text="No data to compare.",
                           xref="paper", yref="paper", x=0.5, y=0.5,
                           showarrow=False, font=dict(color=t["subtext"]))
        return apply_theme(fig, "📊 Corner Comparison", mode)

    # Ordered segment labels
    seg_order = [s["label"] for s in seg_map]

    drivers = delta_df["driver"].unique()
    max_delta = delta_df["delta_s"].abs().max() + 1e-9

    for di, driver in enumerate(drivers):
        d_data = delta_df[delta_df["driver"] == driver].copy()
        # Reorder by segment map order
        d_data["_order"] = d_data["segment"].apply(lambda s: seg_order.index(s) if s in seg_order else 999)
        d_data = d_data.sort_values("_order")

        # Color each bar by delta
        colors = []
        for _, row in d_data.iterrows():
            norm = np.clip(row["delta_s"] / max_delta, -1, 1)
            if norm <= 0:
                r = int(255 * (1 + norm)); g = 212; b = 100
            else:
                r = 255; g = int(212 * (1 - norm)); b = int(100 * (1 - norm))
            colors.append(f"rgb({r},{g},{b})")

        # Add type indicators to labels
        display_labels = []
        for seg_label in d_data["segment"]:
            seg_info = next((s for s in seg_map if s["label"] == seg_label), None)
            if seg_info:
                icon = "🔄" if seg_info["type"] == "Turn" else "➡️"
                display_labels.append(f"{icon} {seg_label}")
            else:
                display_labels.append(seg_label)

        fig.add_trace(go.Bar(
            x=display_labels,
            y=d_data["delta_s"].values * 1000,  # milliseconds
            marker_color=colors,
            name=driver,
            text=[f"{d*1000:+.0f}ms" if abs(d) > 0.005 else "" for d in d_data["delta_s"].values],
            textposition="auto",
            textangle=-90,
            textfont=dict(size=9),
            hovertemplate=(
                "<b>%{x}</b><br>"
                f"<b>{driver}</b><br>"
                "Delta: %{y:+.0f}ms<br>"
                "<extra></extra>"
            ),
        ))

    fig.update_layout(
        barmode="group",
        xaxis_title="Segment",
        yaxis_title="Delta (ms)",
        xaxis=dict(tickangle=-45),
        hovermode="x unified",
        height=380,
        legend=dict(orientation="h", y=1.05, x=0),
    )
    fig.add_hline(y=0, line=dict(color=t["subtext"], width=1, dash="dash"))

    return apply_theme(fig, "📊 Corner-by-Corner Delta Comparison", mode)