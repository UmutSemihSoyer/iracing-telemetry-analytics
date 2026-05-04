import pandas as pd
from core.corner_detector import detect_corners, label_segments

def generate_feedback(df: pd.DataFrame) -> list[dict]:
    items: list[dict] = []

    if df.empty or "Speed" not in df.columns:
        return [{"icon": "⚠️", "title": "No Data",
                 "detail": "Telemetry data is empty or missing Speed channel.",
                 "priority": "warning", "color": "#FF8C00"}]

    if "Segment" not in df.columns:
        df = df.copy()
        corners = detect_corners(df)
        df = label_segments(df, corners)

    # Alias Segment as Micro_Sector for backward compatibility if needed internally
    sectors = sorted(df["Segment"].dropna().unique(), key=lambda x: (x[0], int(x[1:]) if x[1:].isdigit() else 0))

    
    # 1. Analise each sector individually!
    sector_scores = []
    
    for sec in sectors:
        sec_df = df[df["Segment"] == sec]
        if sec_df.empty: continue

        seg_type = sec_df["SegmentType"].iloc[0] if "SegmentType" in sec_df.columns else "Corner"

        
        # Coasting in this specific sector
        coasting_pct = (sec_df["Driver_State"] == "Coasting").mean() * 100
        
        # Speed in this specific sector
        min_spd = sec_df["Speed"].min() * 3.6
        max_spd = sec_df["Speed"].max() * 3.6
        avg_spd = sec_df["Speed"].mean() * 3.6
        
        # Trail braking in this sector
        trail_pct = 0
        has_steer = "Steer" in sec_df.columns or "SteeringWheelAngle" in sec_df.columns
        brake_zones = sec_df[sec_df["Brake"] > 0.05] if "Brake" in sec_df.columns else []
        if has_steer and len(brake_zones) > 0:
            steer_col = "Steer" if "Steer" in sec_df.columns else "SteeringWheelAngle"
            trail = (brake_zones["Brake"] < 0.80) & (brake_zones[steer_col].abs() > (0.08 if steer_col=="Steer" else 15.0))
            trail_pct = trail.mean() * 100
                
        # Generate Rules for Sector
        if coasting_pct > 12.0:
            items.append({
                "icon": "🔴", "priority": "critical",
                "title": f"{sec} - Excessive Coasting ({coasting_pct:.1f}%)",
                "detail": f"You are losing massive time floating without pedals in {sec}. Brake later or go to throttle earlier. Min speed: {min_spd:.1f} km/h.",
                "color": "#FF3B5C",
            })
        elif coasting_pct > 6.0:
            items.append({
                "icon": "🟠", "priority": "warning",
                "title": f"{sec} - High Coasting ({coasting_pct:.1f}%)",
                "detail": f"Try to tighten the gap between brake release and throttle application in {sec}.",
                "color": "#FF8C00",
            })
            
        if len(brake_zones) > 0 and trail_pct < 10.0 and coasting_pct > 5.0:
            items.append({
                "icon": "🔴", "priority": "critical",
                "title": f"{sec} - Missing Trail Braking",
                "detail": f"You are braking entirely in a straight line before {sec}, which leads to coasting. Carry 15% brake into the corner to maintain front grip.",
                "color": "#FF3B5C",
            })
        elif trail_pct > 30.0:
            items.append({
                "icon": "🟢", "priority": "good",
                "title": f"{sec} - Great Trail Braking ({trail_pct:.0f}%)",
                "detail": f"You are carrying the brakes perfectly into the apex of {sec}, keeping the nose planted.",
                "color": "#00D4AA",
            })
            
        # Oversteer / Throttle snap detection in this sector
        throttle_diff = sec_df["Throttle"].diff()
        hesitation = (sec_df["Throttle"] > 0.10) & (sec_df["Throttle"] < 0.90) & (throttle_diff < -0.05)
        if hesitation.sum() > 8:
            items.append({
                "icon": "🟠", "priority": "warning",
                "title": f"Turn {sec} - Throttle Hesitation",
                "detail": f"You are pumping the throttle on exit in {sec}. Wait longer before applying throttle so you can do it in one smooth motion.",
                "color": "#FF8C00",
            })

    # Return items (sort will happen in UI)
    return items


def generate_comparison_feedback(dfs: list) -> list[dict]:
    """
    Compare two or more drivers corner-by-corner.
    Produces feedback like: 'In T3, Driver A loses 0.3s vs Driver B on exit speed.'
    """
    items = []
    if len(dfs) < 2:
        return items

    try:
        from core.corner_detector import get_corner_phase_analysis
        from utils import infer_hz
    except ImportError:
        return items

    # Analyse each driver's best lap
    phase_dfs = []
    for df in dfs[:2]:
        hz = infer_hz(df)
        pdf = get_corner_phase_analysis(df, hz)
        if not pdf.empty:
            best_lap = pdf["Lap"].min()
            phase_dfs.append(pdf[pdf["Lap"] == best_lap])

    if len(phase_dfs) < 2:
        return items

    a = phase_dfs[0].set_index("Turn")
    b = phase_dfs[1].set_index("Turn")
    driver_a = a["Driver"].iloc[0] if not a.empty else "Driver 1"
    driver_b = b["Driver"].iloc[0] if not b.empty else "Driver 2"

    common_turns = sorted(set(a.index) & set(b.index),
                          key=lambda x: int(x[1:]) if x[1:].isdigit() else 0)

    for turn in common_turns:
        ra = a.loc[turn]
        rb = b.loc[turn]

        # Entry speed comparison
        entry_diff = ra["v_entry"] - rb["v_entry"]
        if abs(entry_diff) > 3:
            faster = driver_a if entry_diff > 0 else driver_b
            slower = driver_b if entry_diff > 0 else driver_a
            items.append({
                "icon": "🔵", "priority": "info",
                "title": f"{turn} — Entry Speed Gap ({abs(entry_diff):.1f} km/h)",
                "detail": f"{faster} enters {turn} {abs(entry_diff):.1f} km/h faster than {slower}. "
                          f"Check if {slower} is braking too early.",
                "color": "#00D4FF",
            })

        # Exit speed comparison
        exit_diff = ra["v_exit"] - rb["v_exit"]
        if abs(exit_diff) > 3:
            faster = driver_a if exit_diff > 0 else driver_b
            slower = driver_b if exit_diff > 0 else driver_a
            items.append({
                "icon": "🟢", "priority": "info",
                "title": f"{turn} — Exit Speed Gap ({abs(exit_diff):.1f} km/h)",
                "detail": f"{faster} exits {turn} {abs(exit_diff):.1f} km/h faster. "
                          f"{slower} might be applying throttle too late or not carrying enough apex speed.",
                "color": "#10B981",
            })

        # Trail braking comparison
        trail_diff = ra["Trail_%"] - rb["Trail_%"]
        if abs(trail_diff) > 15:
            better = driver_a if trail_diff > 0 else driver_b
            worse = driver_b if trail_diff > 0 else driver_a
            items.append({
                "icon": "🟣", "priority": "warning",
                "title": f"{turn} — Trail Brake Difference ({abs(trail_diff):.0f}%)",
                "detail": f"{better} carries much more trail braking into {turn} than {worse}. "
                          f"Trail braking keeps the front loaded and allows later braking.",
                "color": "#A855F7",
            })

    return items


def generate_trend_feedback(df: pd.DataFrame) -> list[dict]:
    """
    Analyse the driver's performance trend across laps.
    Detects: coasting increase, speed degradation, consistency issues.
    """
    items = []

    try:
        from core.corner_detector import compute_driving_style_metrics
        from utils import infer_hz
    except ImportError:
        return items

    hz = infer_hz(df)
    style = compute_driving_style_metrics(df, hz)

    if style.empty:
        return items

    flying = style[style["LapType"] == "Flying"]
    if len(flying) < 3:
        return items

    # Trend: coasting increasing over time?
    coast_vals = flying["Coasting_%"].values
    if len(coast_vals) >= 3:
        first_half = coast_vals[:len(coast_vals)//2].mean()
        second_half = coast_vals[len(coast_vals)//2:].mean()
        diff = second_half - first_half

        if diff > 2.0:
            items.append({
                "icon": "📈", "priority": "warning",
                "title": f"Coasting Increasing (+{diff:.1f}%)",
                "detail": f"Your coasting time increased from {first_half:.1f}% (early) to "
                          f"{second_half:.1f}% (late). This often indicates fatigue or tire degradation "
                          f"causing cautious driving.",
                "color": "#FF8C00",
            })
        elif diff < -2.0:
            items.append({
                "icon": "📉", "priority": "good",
                "title": f"Coasting Decreasing ({diff:.1f}%)",
                "detail": f"Your coasting time improved from {first_half:.1f}% to {second_half:.1f}%. "
                          f"You are getting more comfortable with the car across the session.",
                "color": "#10B981",
            })

    # Trend: throttle smoothness degrading?
    smooth_vals = flying["Throttle_Smoothness"].values
    if len(smooth_vals) >= 3:
        first_s = smooth_vals[:len(smooth_vals)//2].mean()
        second_s = smooth_vals[len(smooth_vals)//2:].mean()
        s_diff = second_s - first_s

        if s_diff < -5:
            items.append({
                "icon": "🟠", "priority": "warning",
                "title": f"Throttle Control Degrading ({s_diff:+.0f} pts)",
                "detail": f"Your throttle smoothness dropped from {first_s:.0f} to {second_s:.0f}. "
                          f"This could indicate tire wear causing oversteer on exit, or fatigue.",
                "color": "#FF8C00",
            })

    # Consistency: high variance in lap times
    lap_times_vals = flying["LapTime_s"].values
    valid_times = lap_times_vals[lap_times_vals > 0]
    if len(valid_times) >= 3:
        std = valid_times.std()
        mean = valid_times.mean()
        cv = (std / mean * 100) if mean > 0 else 0

        if cv > 2.0:
            items.append({
                "icon": "🔴", "priority": "critical",
                "title": f"Low Consistency (CV: {cv:.1f}%)",
                "detail": f"Your lap time variation is {std:.3f}s (σ). Mean: {mean:.3f}s. "
                          f"Focus on repeating the same braking points and throttle application.",
                "color": "#EF4444",
            })
        elif cv < 0.5:
            items.append({
                "icon": "🟢", "priority": "good",
                "title": f"Excellent Consistency (CV: {cv:.1f}%)",
                "detail": f"Your lap time variation is only {std:.3f}s. Very consistent driving.",
                "color": "#10B981",
            })

    return items
