"""
Corner Detector — Automatic Track Segmentation
================================================
Detects corners (turns) and straights from telemetry data using
SteeringWheelAngle and/or LatAccel channels.

Each segment is labelled:
  T1, T2, T3 … (Turns)
  S1, S2, S3 … (Straights)

Usage:
    from core.corner_detector import detect_corners, label_segments, get_segment_summary

    corners  = detect_corners(df)           # list of (start_idx, end_idx) for best lap
    seg_df   = label_segments(df, corners)  # adds 'Segment' + 'SegmentType' columns
    summary  = get_segment_summary(df)      # per-segment stats dataframe
"""

import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d


# ════════════════════════════════════════════════════════════════════════════
# HELPER: Get best (fastest) flying lap df subset
# ════════════════════════════════════════════════════════════════════════════

def _get_best_lap(df: pd.DataFrame) -> pd.DataFrame:
    """Return the DataFrame slice for the fastest flying lap."""
    if df.empty or "LapNumber" not in df.columns:
        return pd.DataFrame()

    try:
        from core.lap_classifier import filter_flying_laps, flying_lap_times
        flying = filter_flying_laps(df)
        if flying.empty:
            flying = df
    except ImportError:
        flying = df

    if "LapTime_s" in flying.columns:
        lt_per_lap = flying.groupby("LapNumber")["LapTime_s"].first()
        valid = lt_per_lap[lt_per_lap > 0]
        if not valid.empty:
            best_num = valid.idxmin()
            return flying[flying["LapNumber"] == best_num]

    # Fallback: just return the first full lap
    laps = sorted(flying["LapNumber"].unique())
    if len(laps) > 1:
        return flying[flying["LapNumber"] == laps[1]]
    return flying


# ════════════════════════════════════════════════════════════════════════════
# CORNER DETECTION
# ════════════════════════════════════════════════════════════════════════════

def detect_corners(df: pd.DataFrame,
                   steer_threshold: float = 0.06,
                   lat_threshold: float = 2.5,
                   min_corner_samples: int = 12,
                   merge_gap: int = 8,
                   smooth_sigma: float = 5.0) -> list:
    """
    Detect corner (turn) zones from telemetry data.

    Strategy:
      1. Primary: SteeringWheelAngle — magnitude above threshold = turning
      2. Fallback: LatAccel — magnitude above threshold = turning
      3. Merge nearby zones (chicane = separate turns if gap > merge_gap)
      4. Filter very short zones

    Parameters
    ----------
    df : DataFrame
        Single-lap telemetry data (must have LapDistPct).
    steer_threshold : float
        Absolute steering angle threshold (radians). Default 0.06 (~3.4°).
    lat_threshold : float
        Absolute lateral acceleration threshold (m/s²). Default 2.5.
    min_corner_samples : int
        Minimum samples for a region to count as a corner.
    merge_gap : int
        If two detected zones are within this many samples, merge them.
    smooth_sigma : float
        Gaussian smoothing sigma for the detection signal.

    Returns
    -------
    list of dict
        Each dict: {start_idx, end_idx, start_pct, end_pct, direction}
        direction: 'L' (left) or 'R' (right)
    """
    if df.empty or "LapDistPct" not in df.columns:
        return []

    # Choose detection signal
    signal = None
    raw_signal = None

    # Preferred channels in order
    steer_channels = ["SteeringWheelAngle", "SteeringWheelAngleMax", "SteerAngle", "Steer"]
    lat_channels   = ["LatAccel", "LatAccel_LPR", "Grip_Lat"]

    for sc in steer_channels:
        if sc in df.columns and df[sc].std() > 0.001:
            raw_signal = df[sc].values.copy()
            signal = gaussian_filter1d(np.abs(raw_signal), sigma=smooth_sigma)
            # Normalize threshold if it's 'Steer' (usually -1 to 1) vs Angle (rads)
            mult = 0.5 if sc == "Steer" else 1.0
            threshold = steer_threshold * mult
            break
            
    if signal is None:
        for lc in lat_channels:
            if lc in df.columns and df[lc].std() > 0.01:
                raw_signal = df[lc].values.copy()
                signal = gaussian_filter1d(np.abs(raw_signal), sigma=smooth_sigma)
                threshold = lat_threshold
                break

    if signal is None:
        return []

    # Step 1: Find regions above threshold
    above = (signal > threshold).astype(int)
    diff = np.diff(above, prepend=0)
    starts = np.where(diff == 1)[0]
    ends = np.where(diff == -1)[0]

    # Handle edge cases
    if len(starts) == 0:
        return []
    if len(ends) == 0 or ends[-1] < starts[-1]:
        ends = np.append(ends, len(signal) - 1)
    if starts[0] > ends[0]:
        starts = np.insert(starts, 0, 0)

    # Pair start-end
    zones = list(zip(starts, ends))

    # Step 2: Merge close zones (but not chicanes — gap > merge_gap keeps them separate)
    merged = []
    for s, e in zones:
        if merged and (s - merged[-1][1]) < merge_gap:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))

    # Step 3: Filter too-short zones
    filtered = [(s, e) for s, e in merged if (e - s) >= min_corner_samples]

    # Step 4: Build result with direction (and split chicanes)
    pct = df["LapDistPct"].values
    corners = []
    for s, e in filtered:
        seg_raw = raw_signal[s:e]
        
        # Check for chicane (direction flip)
        # Find points where steering crosses a small neutral deadzone
        side = np.sign(seg_raw)
        crossings = np.where(np.diff(side) != 0)[0]
        
        split_idx = None
        if len(crossings) > 0:
            # Look for a crossing that divides the segment into two substantial parts
            for c in crossings:
                part1 = seg_raw[:c]
                part2 = seg_raw[c:]
                # Both parts are substantial in length and have opposite directions
                if len(part1) >= 8 and len(part2) >= 8:
                    if np.sign(np.mean(part1)) != np.sign(np.mean(part2)):
                        split_idx = c
                        break
        
        if split_idx is not None:
            # Split into 2 corners
            for start, end in [(0, split_idx), (split_idx, len(seg_raw))]:
                sub_seg = seg_raw[start:end]
                direction = "L" if np.mean(sub_seg) > 0 else "R"
                corners.append({
                    "start_idx": int(s + start),
                    "end_idx": int(s + end),
                    "start_pct": float(pct[s + start]),
                    "end_pct": float(pct[min(s + end, len(pct)-1)]),
                    "direction": direction,
                })
        else:
            # Standard single corner
            mean_val = np.mean(seg_raw)
            direction = "L" if mean_val > 0 else "R"
            corners.append({
                "start_idx": int(s),
                "end_idx": int(e),
                "start_pct": float(pct[s]),
                "end_pct": float(pct[min(e, len(pct)-1)]),
                "direction": direction,
            })

    # Recursive fallback with lower thresholds if nothing found
    if not corners and steer_threshold > 0.02:
        return detect_corners(df, 
                              steer_threshold=steer_threshold*0.5, 
                              lat_threshold=lat_threshold*0.5,
                              min_corner_samples=min_corner_samples-4 if min_corner_samples > 8 else min_corner_samples)

    return corners


# ════════════════════════════════════════════════════════════════════════════
# SEGMENT LABELING
# ════════════════════════════════════════════════════════════════════════════

def label_segments(df: pd.DataFrame, corners: list) -> pd.DataFrame:
    """
    Add 'Segment' and 'SegmentType' columns to the DataFrame.

    Segments are labelled:
      T1, T2, T3, ... for turns (corners)
      S1, S2, S3, ... for straights (between corners)

    Parameters
    ----------
    df : DataFrame
        Telemetry data with LapDistPct.
    corners : list of dict
        Output from detect_corners().

    Returns
    -------
    DataFrame with added 'Segment' and 'SegmentType' columns.
    """
    n = len(df)
    if n == 0:
        return df

    # We work on a copy to avoid SettingWithCopyWarning if df is a slice
    df = df.copy()

    if not corners:
        df["Segment"] = "S1"
        df["SegmentType"] = "Straight"
        return df

    pct = df["LapDistPct"].values
    
    # Pre-allocate arrays with a sensible default
    segment_labels = np.full(n, "S0", dtype=object)
    segment_types = np.full(n, "Straight", dtype=object)

    # Sort corners by start_pct
    sorted_corners = sorted(corners, key=lambda c: c["start_pct"])

    # Build ordered segment list: S-T-S-T-S-T-S...
    segments = []  # list of (start_pct, end_pct, label, seg_type)
    turn_num = 0
    straight_num = 0

    # First straight (before first corner)
    if sorted_corners[0]["start_pct"] > 0.001:
        straight_num += 1
        segments.append((0.0, sorted_corners[0]["start_pct"], f"S{straight_num}", "Straight"))

    for i, corner in enumerate(sorted_corners):
        turn_num += 1
        segments.append((
            corner["start_pct"],
            corner["end_pct"],
            f"T{turn_num}",
            "Turn"
        ))

        # Straight between this corner and next
        if i < len(sorted_corners) - 1:
            next_start = sorted_corners[i + 1]["start_pct"]
            if next_start - corner["end_pct"] > 0.0001:
                straight_num += 1
                segments.append((corner["end_pct"], next_start, f"S{straight_num}", "Straight"))

    # Last straight (after last corner to end of lap)
    if sorted_corners[-1]["end_pct"] < 0.999:
        straight_num += 1
        segments.append((sorted_corners[-1]["end_pct"], 1.01, f"S{straight_num}", "Straight"))

    # Optimization: Instead of masking the whole DF for every segment (O(num_segments * n)),
    # we use np.searchsorted to find segment indices (O(n * log(num_segments))).
    # This is MUCH faster for long tracks like Nürburgring with 170+ corners.
    
    seg_boundaries = [s[0] for s in segments] + [segments[-1][1]]
    seg_indices = np.searchsorted(seg_boundaries, pct, side='right') - 1
    
    # Clip indices to valid range
    seg_indices = np.clip(seg_indices, 0, len(segments) - 1)
    
    # Map indices to labels and types
    labels_lookup = np.array([s[2] for s in segments], dtype=object)
    types_lookup = np.array([s[3] for s in segments], dtype=object)
    
    df["Segment"] = labels_lookup[seg_indices]
    df["SegmentType"] = types_lookup[seg_indices]
    
    return df


def build_segment_map(corners: list) -> list:
    """
    Build an ordered list of segments from detected corners.

    Returns list of dicts: [{label, type, start_pct, end_pct, direction}, ...]
    """
    if not corners:
        return [{"label": "S1", "type": "Straight", "start_pct": 0.0, "end_pct": 1.0, "direction": None}]

    sorted_corners = sorted(corners, key=lambda c: c["start_pct"])
    segments = []
    turn_num = 0
    straight_num = 0

    # First straight
    if sorted_corners[0]["start_pct"] > 0.01:
        straight_num += 1
        segments.append({
            "label": f"S{straight_num}",
            "type": "Straight",
            "start_pct": 0.0,
            "end_pct": sorted_corners[0]["start_pct"],
            "direction": None,
        })

    for i, corner in enumerate(sorted_corners):
        turn_num += 1
        segments.append({
            "label": f"T{turn_num}",
            "type": "Turn",
            "start_pct": corner["start_pct"],
            "end_pct": corner["end_pct"],
            "direction": corner["direction"],
        })

        if i < len(sorted_corners) - 1:
            next_start = sorted_corners[i + 1]["start_pct"]
            if next_start - corner["end_pct"] > 0.005:
                straight_num += 1
                segments.append({
                    "label": f"S{straight_num}",
                    "type": "Straight",
                    "start_pct": corner["end_pct"],
                    "end_pct": next_start,
                    "direction": None,
                })

    if sorted_corners[-1]["end_pct"] < 0.99:
        straight_num += 1
        segments.append({
            "label": f"S{straight_num}",
            "type": "Straight",
            "start_pct": sorted_corners[-1]["end_pct"],
            "end_pct": 1.0,
            "direction": None,
        })

    return segments


# ════════════════════════════════════════════════════════════════════════════
# SEGMENT SUMMARY & COMPARISON
# ════════════════════════════════════════════════════════════════════════════

def get_segment_summary(df: pd.DataFrame,
                        segment_map: list = None,
                        hz: float = 60.0) -> pd.DataFrame:
    """
    Calculate per-segment statistics for a single lap.

    If segment_map is provided, uses it. Otherwise tries to use
    Segment/SegmentType columns already in df.

    Returns DataFrame with columns:
        Segment, Type, Direction, Duration_s, MinSpeed_kmh, AvgSpeed_kmh,
        MaxSpeed_kmh, EntrySpeed_kmh, ExitSpeed_kmh, AvgLatG, PeakLatG,
        AvgBrake, Start_pct, End_pct
    """
    if df.empty:
        return pd.DataFrame()

    has_segments = "Segment" in df.columns and "SegmentType" in df.columns

    if not has_segments and segment_map is None:
        return pd.DataFrame()

    rows = []
    pct = df["LapDistPct"].values if "LapDistPct" in df.columns else None

    if segment_map:
        for seg in segment_map:
            if pct is None:
                continue
            if seg["end_pct"] >= 0.99:
                mask = (pct >= seg["start_pct"]) & (pct <= seg["end_pct"])
            else:
                mask = (pct >= seg["start_pct"]) & (pct < seg["end_pct"])
            seg_df = df[mask]
            if seg_df.empty:
                continue
            rows.append(_calc_seg_stats(seg_df, seg["label"], seg["type"],
                                         seg.get("direction"), hz,
                                         seg["start_pct"], seg["end_pct"]))
    else:
        # Use existing Segment column
        for seg_label, seg_df in df.groupby("Segment", sort=False):
            seg_type = seg_df["SegmentType"].iloc[0] if "SegmentType" in seg_df.columns else "?"
            s_pct = seg_df["LapDistPct"].min() if "LapDistPct" in seg_df.columns else 0
            e_pct = seg_df["LapDistPct"].max() if "LapDistPct" in seg_df.columns else 0
            rows.append(_calc_seg_stats(seg_df, seg_label, seg_type, None, hz, s_pct, e_pct))

    return pd.DataFrame(rows)


def _calc_seg_stats(seg_df: pd.DataFrame, label: str, seg_type: str,
                    direction: str, hz: float,
                    start_pct: float, end_pct: float) -> dict:
    """Calculate statistics for a single segment."""
    n = len(seg_df)
    duration = n / hz

    speed = seg_df["Speed"].values * 3.6 if "Speed" in seg_df.columns else np.zeros(n)
    min_spd = float(np.min(speed)) if len(speed) > 0 else 0
    avg_spd = float(np.mean(speed)) if len(speed) > 0 else 0
    max_spd = float(np.max(speed)) if len(speed) > 0 else 0
    entry_spd = float(speed[0]) if len(speed) > 0 else 0
    exit_spd = float(speed[-1]) if len(speed) > 0 else 0

    lat_g = np.zeros(n)
    if "LatAccel" in seg_df.columns:
        lat_g = seg_df["LatAccel"].values / 9.81  # Convert to G
    avg_lat = float(np.mean(np.abs(lat_g)))
    peak_lat = float(np.max(np.abs(lat_g)))

    avg_brake = 0.0
    if "Brake" in seg_df.columns:
        avg_brake = float(seg_df["Brake"].mean() * 100)

    avg_throttle = 0.0
    if "Throttle" in seg_df.columns:
        avg_throttle = float(seg_df["Throttle"].mean() * 100)

    # Apex point = min speed point in the segment
    apex_pct = start_pct
    if "Speed" in seg_df.columns and "LapDistPct" in seg_df.columns and len(seg_df) > 0:
        apex_idx = seg_df["Speed"].idxmin()
        apex_pct = float(seg_df.loc[apex_idx, "LapDistPct"])

    return {
        "Segment": label,
        "Type": seg_type,
        "Direction": direction or "—",
        "Duration_s": round(duration, 3),
        "MinSpeed_kmh": round(min_spd, 1),
        "AvgSpeed_kmh": round(avg_spd, 1),
        "MaxSpeed_kmh": round(max_spd, 1),
        "EntrySpeed_kmh": round(entry_spd, 1),
        "ExitSpeed_kmh": round(exit_spd, 1),
        "AvgLatG": round(avg_lat, 2),
        "PeakLatG": round(peak_lat, 2),
        "AvgBrake_%": round(avg_brake, 1),
        "AvgThrottle_%": round(avg_throttle, 1),
        "Apex_pct": round(apex_pct, 4),
        "Start_pct": round(start_pct, 4),
        "End_pct": round(end_pct, 4),
    }


def compute_corner_deltas(dfs: list,
                          hz: float = 60.0,
                          ref_mode: str = "best_of_each") -> tuple:
    """
    Compute per-segment time deltas between drivers or laps.

    Parameters
    ----------
    dfs : list of DataFrame
        One DataFrame per driver.
    hz : float
        Telemetry sample rate.
    ref_mode : str
        'best_of_each'        — each segment's fastest driver is ref (multi-driver)
        'individual_optimal'  — best lap vs 2nd best for single driver
        'collective_optimal'  — theoretical best segments across all laps

    Returns
    -------
    (delta_df, segment_map)
    """
    try:
        from core.lap_classifier import filter_flying_laps, flying_lap_times
    except ImportError:
        def filter_flying_laps(df): return df
        def flying_lap_times(df, hz=60): return pd.DataFrame()

    if not dfs:
        return pd.DataFrame(), []

    # Detect corners from the first driver's best lap (reference layout)
    ref_df = _get_best_lap(dfs[0])
    if ref_df.empty:
        return pd.DataFrame(), []

    corners = detect_corners(ref_df)
    seg_map = build_segment_map(corners)
    if not seg_map:
        return pd.DataFrame(), []

    is_single_driver = len(dfs) == 1

    # ── Single driver: compare multiple laps ──
    if is_single_driver and ref_mode in ("individual_optimal", "collective_optimal"):
        return _compute_multi_lap_deltas(dfs[0], seg_map, hz, ref_mode)

    # ── Multi-driver (or single driver best_of_each → also try multi-lap) ──
    rows = []
    all_driver_seg_times = {}

    for di, df in enumerate(dfs):
        driver = df["Driver"].iloc[0] if "Driver" in df.columns else f"Driver {di+1}"
        best = _get_best_lap(df)
        if best.empty:
            continue
        seg_times = _calc_lap_segment_times(best, seg_map, hz, driver)
        rows.extend(seg_times)
        all_driver_seg_times[driver] = {r["segment"]: r["time_s"] for r in seg_times}

    delta_df = pd.DataFrame(rows)
    if delta_df.empty:
        return delta_df, seg_map

    # For single-driver best_of_each, try multi-lap fallback
    if is_single_driver:
        multi_df, _ = _compute_multi_lap_deltas(dfs[0], seg_map, hz, "individual_optimal")
        if not multi_df.empty and multi_df["delta_s"].abs().max() > 0.001:
            return multi_df, seg_map

    # Reference = minimum time across all drivers for each segment
    ref_times = delta_df.groupby("segment")["time_s"].min().to_dict()
    delta_df["ref_time_s"] = delta_df["segment"].map(ref_times)
    delta_df["delta_s"] = delta_df["time_s"] - delta_df["ref_time_s"]

    return delta_df, seg_map


def _calc_lap_segment_times(lap_df, seg_map, hz, driver_label):
    """Calculate segment times for a single lap."""
    pct = lap_df["LapDistPct"].values
    speed = lap_df["Speed"].values if "Speed" in lap_df.columns else None
    rows = []

    for seg in seg_map:
        if seg["end_pct"] >= 0.99:
            mask = (pct >= seg["start_pct"]) & (pct <= seg["end_pct"])
        else:
            mask = (pct >= seg["start_pct"]) & (pct < seg["end_pct"])
        n_samples = mask.sum()
        seg_time = n_samples / hz

        seg_speed = entry_spd = exit_spd = min_spd = 0
        if speed is not None and n_samples > 0:
            seg_speeds = speed[mask]
            seg_speed = float(np.mean(seg_speeds)) * 3.6
            entry_spd = float(seg_speeds[0]) * 3.6
            exit_spd = float(seg_speeds[-1]) * 3.6
            min_spd = float(np.min(seg_speeds)) * 3.6

        lat_mid = lon_mid = np.nan
        if "Lat" in lap_df.columns and "Lon" in lap_df.columns and n_samples > 0:
            seg_data = lap_df[mask]
            mid_idx = len(seg_data) // 2
            lat_mid = float(seg_data["Lat"].iloc[mid_idx])
            lon_mid = float(seg_data["Lon"].iloc[mid_idx])

        rows.append({
            "segment": seg["label"],
            "seg_type": seg["type"],
            "driver": driver_label,
            "time_s": round(seg_time, 4),
            "avg_speed_kmh": round(seg_speed, 1),
            "entry_speed_kmh": round(entry_spd, 1),
            "exit_speed_kmh": round(exit_spd, 1),
            "min_speed_kmh": round(min_spd, 1),
            "lat_mid": lat_mid,
            "lon_mid": lon_mid,
        })
    return rows


def _compute_multi_lap_deltas(df, seg_map, hz, ref_mode):
    """Compare best lap vs other flying laps for single-driver analysis."""
    try:
        from core.lap_classifier import filter_flying_laps, flying_lap_times
    except ImportError:
        return pd.DataFrame(), seg_map

    driver = df["Driver"].iloc[0] if "Driver" in df.columns else "Driver"
    lt = flying_lap_times(df, hz)
    if lt.empty or len(lt) < 2:
        return pd.DataFrame(), seg_map

    # Get top laps
    best_ln = int(lt.iloc[0]["LapNumber"])
    second_ln = int(lt.iloc[1]["LapNumber"])

    best_lap = df[df["LapNumber"] == best_ln]
    second_lap = df[df["LapNumber"] == second_ln]

    if best_lap.empty or second_lap.empty:
        return pd.DataFrame(), seg_map

    rows_best = _calc_lap_segment_times(best_lap, seg_map, hz, f"{driver} (Best L{best_ln})")
    rows_second = _calc_lap_segment_times(second_lap, seg_map, hz, f"{driver} (L{second_ln})")

    if ref_mode == "collective_optimal":
        # Theoretical best: min across ALL flying laps
        all_rows = list(rows_best)
        for _, row_lt in lt.iterrows():
            ln = int(row_lt["LapNumber"])
            if ln == best_ln:
                continue
            lap_data = df[df["LapNumber"] == ln]
            if not lap_data.empty:
                all_rows.extend(_calc_lap_segment_times(lap_data, seg_map, hz, f"L{ln}"))
        all_df = pd.DataFrame(all_rows)
        ref_times = all_df.groupby("segment")["time_s"].min().to_dict()
    else:
        # individual_optimal: reference = best lap
        ref_times = {r["segment"]: r["time_s"] for r in rows_best}

    all_rows = rows_best + rows_second
    delta_df = pd.DataFrame(all_rows)
    delta_df["ref_time_s"] = delta_df["segment"].map(ref_times)
    delta_df["delta_s"] = delta_df["time_s"] - delta_df["ref_time_s"]

    return delta_df, seg_map


def _get_best_lap(df: pd.DataFrame) -> pd.DataFrame:
    """Get the best (fastest flying) lap from df."""
    try:
        from core.lap_classifier import filter_flying_laps, flying_lap_times
        flying = filter_flying_laps(df)
        if flying.empty:
            flying = df
        lt = flying_lap_times(df)
        if not lt.empty:
            best_ln = lt.iloc[0]["LapNumber"]
            return df[df["LapNumber"] == best_ln].copy()
        # Fallback: calculate track distance covered to ignore tiny corrupted laps
        if "LapDistPct" in flying.columns:
            dist_ranges = flying.groupby("LapNumber")["LapDistPct"].agg(lambda x: x.max() - x.min())
            max_dist = dist_ranges.max()
            v_laps = dist_ranges[dist_ranges >= max_dist * 0.90].index
            counts = flying[flying["LapNumber"].isin(v_laps)].groupby("LapNumber").size()
            best_ln = counts.idxmin() if not counts.empty else flying["LapNumber"].unique()[0]
        else:
            counts = flying.groupby("LapNumber").size()
            best_ln = counts.idxmin() if not counts.empty else flying["LapNumber"].unique()[0]
        
        return df[df["LapNumber"] == best_ln].copy()
    except ImportError:
        if "LapNumber" in df.columns:
            laps = df["LapNumber"].unique()
            if len(laps) > 0:
                return df[df["LapNumber"] == laps[0]].copy()
        return df


def calculate_optimal_lap_time(df, hz=60.0):
    """
    Calculate the sum of best sectors across all valid flying laps.
    Returns: (total_optimal_s, formatting_string)
    """
    try:
        from core.lap_classifier import flying_lap_times
    except ImportError:
        return 0.0, "—"

    if "Segment" not in df.columns:
        corners = detect_corners(df)
        if not corners:
            return 0.0, "—"
        df = label_segments(df, corners)

    lt = flying_lap_times(df, hz)
    if lt.empty:
        return 0.0, "—"

    # Vectorized calculation: group by LapNumber and Segment, count rows
    flying_laps = df[df["LapNumber"].isin(lt["LapNumber"])]
    counts = flying_laps.groupby(["LapNumber", "Segment"]).size()
    
    if counts.empty:
        return 0.0, "—"
        
    # Convert samples to seconds and find the minimum time for each segment
    seg_times = counts / hz
    best_sector_times = seg_times.groupby("Segment").min()

    total_s = best_sector_times.sum()
    if total_s < 1.0 or total_s > 10000:
        return 0.0, "—"

    mm = int(total_s // 60)
    ss = total_s % 60
    return total_s, f"{mm}:{ss:06.3f}"


# ════════════════════════════════════════════════════════════════════════════
# CORNER PHASE ANALYSIS — Entry / Apex / Exit speeds + Brake Depth
# ════════════════════════════════════════════════════════════════════════════

def get_corner_phase_analysis(df: pd.DataFrame, hz: float = 60.0) -> pd.DataFrame:
    """
    Analyse each detected corner (Turn) with:
      - v_entry   : speed at corner entry (km/h)
      - v_apex    : minimum speed in corner (km/h)
      - v_exit    : speed at corner exit (km/h)
      - brake_depth_pct : how far into the corner braking continues (0-100 %)
      - trail_pct : % of brake zone with simultaneous steering
      - decel_g   : peak deceleration in the corner (positive G)

    Returns DataFrame with one row per turn per lap.
    """
    try:
        from core.lap_classifier import filter_flying_laps
    except ImportError:
        def filter_flying_laps(d): return d

    if df.empty or "Speed" not in df.columns:
        return pd.DataFrame()

    flying = filter_flying_laps(df)
    if flying.empty:
        flying = df

    # Detect corners from best lap
    best = _get_best_lap(df)
    if best.empty:
        return pd.DataFrame()

    corners = detect_corners(best)
    if not corners:
        return pd.DataFrame()

    seg_map = build_segment_map(corners)
    pct_col = "LapDistPct"
    if pct_col not in flying.columns:
        return pd.DataFrame()

    rows = []
    laps = sorted(flying["LapNumber"].unique())

    for lap_num in laps:
        lap_df = flying[flying["LapNumber"] == lap_num]
        if lap_df.empty or len(lap_df) < 20:
            continue
        driver = lap_df["Driver"].iloc[0] if "Driver" in lap_df.columns else "Driver"
        pct = lap_df[pct_col].values
        speed = lap_df["Speed"].values * 3.6  # km/h

        has_brake = "Brake" in lap_df.columns
        has_steer = "Steer" in lap_df.columns or "SteeringWheelAngle" in lap_df.columns
        steer_col = "Steer" if "Steer" in lap_df.columns else ("SteeringWheelAngle" if "SteeringWheelAngle" in lap_df.columns else None)
        steer_thresh = 0.08 if steer_col == "Steer" else (15.0 if steer_col == "SteeringWheelAngle" else 0)

        turn_num = 0
        for seg in seg_map:
            if seg["type"] != "Turn":
                continue
            turn_num += 1

            if seg["end_pct"] >= 0.99:
                mask = (pct >= seg["start_pct"]) & (pct <= seg["end_pct"])
            else:
                mask = (pct >= seg["start_pct"]) & (pct < seg["end_pct"])

            n = mask.sum()
            if n < 5:
                continue

            seg_speed = speed[mask]
            v_entry = float(seg_speed[0])
            v_apex = float(np.min(seg_speed))
            v_exit = float(seg_speed[-1])

            # Apex index relative to corner
            apex_rel_idx = int(np.argmin(seg_speed))
            apex_pct_val = apex_rel_idx / max(n - 1, 1) * 100  # 0-100 %

            # Brake depth: how far into corner is brake > 5% ?
            brake_depth = 0.0
            trail_pct = 0.0
            if has_brake:
                seg_brake = lap_df["Brake"].values[mask]
                braking = seg_brake > 0.05
                if braking.any():
                    last_brake_idx = np.where(braking)[0][-1]
                    brake_depth = (last_brake_idx + 1) / n * 100

                    # Trail braking: brake + steering at the same time
                    if has_steer and steer_col:
                        seg_steer = np.abs(lap_df[steer_col].values[mask])
                        trail_mask = braking & (seg_steer > steer_thresh)
                        trail_pct = trail_mask.sum() / max(braking.sum(), 1) * 100

            # Peak deceleration (longitudinal G)
            decel_g = 0.0
            if "LongAccel" in lap_df.columns:
                seg_long = lap_df["LongAccel"].values[mask]
                decel_g = float(np.abs(np.min(seg_long))) / 9.81
            elif "Calc_Accel" in lap_df.columns:
                seg_accel = lap_df["Calc_Accel"].values[mask]
                decel_g = float(np.abs(np.min(seg_accel))) / 9.81

            rows.append({
                "Driver": driver,
                "Lap": int(lap_num),
                "Turn": f"T{turn_num}",
                "Direction": seg.get("direction", "—"),
                "v_entry": round(v_entry, 1),
                "v_apex": round(v_apex, 1),
                "v_exit": round(v_exit, 1),
                "Apex_pos_%": round(apex_pct_val, 0),
                "Brake_depth_%": round(brake_depth, 1),
                "Trail_%": round(trail_pct, 1),
                "Decel_G": round(decel_g, 2),
            })

    return pd.DataFrame(rows)


# ════════════════════════════════════════════════════════════════════════════
# TRAIL BRAKE SCORING — 0-100 score for each brake zone
# ════════════════════════════════════════════════════════════════════════════

def score_trail_braking(df: pd.DataFrame, hz: float = 60.0) -> list:
    """
    Score each brake zone on a 0-100 scale based on how well
    the driver tapers brake pressure while adding steering.

    Ideal shape: brake is released linearly from peak into the corner,
    overlapping with steering input.  A flat-release (all-or-nothing) scores low.

    Returns list of dicts with zone info + score.
    """
    if df.empty or "Brake" not in df.columns:
        return []

    try:
        from core.lap_classifier import filter_flying_laps
        flying = filter_flying_laps(df)
        if flying.empty:
            flying = df
    except ImportError:
        flying = df

    best = _get_best_lap(df)
    if best.empty:
        return []

    brake = best["Brake"].values
    has_steer = "Steer" in best.columns or "SteeringWheelAngle" in best.columns
    steer_col = "Steer" if "Steer" in best.columns else ("SteeringWheelAngle" if "SteeringWheelAngle" in best.columns else None)
    steer_thresh = 0.08 if steer_col == "Steer" else 15.0
    pct = best["LapDistPct"].values if "LapDistPct" in best.columns else np.linspace(0, 1, len(best))

    # Find brake zones (contiguous regions where brake > 5%)
    in_brake = (brake > 0.05).astype(int)
    diff = np.diff(in_brake, prepend=0)
    starts = np.where(diff == 1)[0]
    ends = np.where(diff == -1)[0]
    if len(starts) == 0:
        return []
    if len(ends) == 0 or ends[-1] < starts[-1]:
        ends = np.append(ends, len(brake) - 1)

    zones = []
    for i, (s, e) in enumerate(zip(starts, ends)):
        if (e - s) < 5:
            continue  # too short

        zone_brake = brake[s:e]
        peak_brake = float(np.max(zone_brake))
        peak_idx = np.argmax(zone_brake)

        # Release phase: from peak to end of zone
        release = zone_brake[peak_idx:]
        if len(release) < 3:
            continue

        # === Score Components ===
        # 1. Taper linearity (30 pts): how smooth is the release?
        ideal_taper = np.linspace(peak_brake, 0, len(release))
        mse = np.mean((release - ideal_taper) ** 2)
        taper_score = max(0, 30 * (1 - mse / max(peak_brake ** 2, 0.01)))

        # 2. Trail overlap (40 pts): does brake overlap with steering?
        trail_score = 0
        if has_steer and steer_col:
            steer_vals = np.abs(best[steer_col].values[s:e])
            overlap = (brake[s:e] > 0.05) & (steer_vals > steer_thresh)
            overlap_ratio = overlap.sum() / max(len(zone_brake), 1)
            trail_score = min(40, overlap_ratio * 100)

        # 3. Duration (15 pts): longer tapered release is better
        release_ratio = len(release) / max(len(zone_brake), 1)
        duration_score = min(15, release_ratio * 25)

        # 4. No snap release (15 pts): penalise sudden drops
        brake_diffs = np.abs(np.diff(release))
        max_drop = np.max(brake_diffs) if len(brake_diffs) > 0 else 0
        snap_score = max(0, 15 * (1 - max_drop / max(peak_brake, 0.01)))

        total = round(taper_score + trail_score + duration_score + snap_score)
        total = min(100, max(0, total))

        # Grade
        if total >= 80:
            grade = "A"
        elif total >= 60:
            grade = "B"
        elif total >= 40:
            grade = "C"
        elif total >= 20:
            grade = "D"
        else:
            grade = "F"

        zones.append({
            "Zone": i + 1,
            "Track_%": round(float(pct[s]) * 100, 1),
            "Peak_%": round(peak_brake * 100, 0),
            "Score": total,
            "Grade": grade,
            "Taper": round(taper_score, 0),
            "Trail": round(trail_score, 0),
            "Duration": round(duration_score, 0),
            "Smoothness": round(snap_score, 0),
        })

    return zones


# ════════════════════════════════════════════════════════════════════════════
# DRIVING STYLE METRICS — Per-Lap Style Breakdown
# ════════════════════════════════════════════════════════════════════════════

def compute_driving_style_metrics(df: pd.DataFrame, hz: float = 60.0) -> pd.DataFrame:
    """
    Per-lap driving style metrics:
      - Coasting %  : time where neither throttle nor brake > 5%
      - Overlap %   : time where both throttle AND brake > 5%
      - Throttle_smoothness : inverse of throttle jitter (0-100)
      - Avg_trail_score : mean trail brake score for that lap

    Returns DataFrame with one row per lap.
    """
    try:
        from core.lap_classifier import classify_laps
        if "LapType" not in df.columns:
            df = classify_laps(df, hz)
    except ImportError:
        pass

    if df.empty:
        return pd.DataFrame()

    rows = []
    laps = sorted(df["LapNumber"].unique()) if "LapNumber" in df.columns else [1]

    for lap_num in laps:
        lap_df = df[df["LapNumber"] == lap_num] if "LapNumber" in df.columns else df
        if lap_df.empty or len(lap_df) < 20:
            continue

        driver = lap_df["Driver"].iloc[0] if "Driver" in lap_df.columns else "Driver"
        lap_type = lap_df["LapType"].iloc[0] if "LapType" in lap_df.columns else "?"
        n = len(lap_df)

        # Coasting & Overlap
        coasting = 0.0
        overlap = 0.0
        if "Driver_State" in lap_df.columns:
            counts = lap_df["Driver_State"].value_counts()
            coasting = round(counts.get("Coasting", 0) / n * 100, 1)
            overlap = round(counts.get("Overlap", 0) / n * 100, 1)

        # Throttle smoothness: 100 - (jitter * factor)
        throttle_smooth = 0.0
        if "Throttle" in lap_df.columns:
            t_diff = np.abs(np.diff(lap_df["Throttle"].values))
            jitter = float(np.mean(t_diff))
            # Scale: jitter of 0.01 = smooth (100), jitter of 0.10 = choppy (0)
            throttle_smooth = round(max(0, min(100, (1 - jitter / 0.10) * 100)), 0)

        # Brake smoothness
        brake_smooth = 0.0
        if "Brake" in lap_df.columns:
            b_diff = np.abs(np.diff(lap_df["Brake"].values))
            b_jitter = float(np.mean(b_diff))
            brake_smooth = round(max(0, min(100, (1 - b_jitter / 0.08) * 100)), 0)

        # Lap time
        lap_time = 0.0
        if "LapTime_s" in lap_df.columns:
            val = lap_df["LapTime_s"].iloc[0]
            if pd.notna(val) and val > 0:
                lap_time = float(val)

        rows.append({
            "Driver": driver,
            "Lap": int(lap_num),
            "LapType": lap_type,
            "LapTime_s": round(lap_time, 3),
            "Coasting_%": coasting,
            "Overlap_%": overlap,
            "Throttle_Smoothness": throttle_smooth,
            "Brake_Smoothness": brake_smooth,
        })

    return pd.DataFrame(rows)


# ════════════════════════════════════════════════════════════════════════════
# ABS & TC EVENT TRACKING
# ════════════════════════════════════════════════════════════════════════════

def compute_abs_tc_events(df: pd.DataFrame, hz: float = 60.0) -> dict:
    """
    Track ABS (Anti-lock Brake System) and TC (Traction Control)
    activation events across the session.

    Returns dict with:
      - abs_activations  : total events
      - abs_duration_s   : total seconds ABS was active
      - tc_activations   : total events
      - tc_duration_s    : total seconds TC was active
      - abs_zones        : list of (track_pct, duration) for GPS overlay
      - tc_zones         : list of (track_pct, duration) for GPS overlay
    """
    result = {
        "abs_activations": 0, "abs_duration_s": 0.0,
        "tc_activations": 0, "tc_duration_s": 0.0,
        "abs_zones": [], "tc_zones": [],
    }

    try:
        from core.lap_classifier import filter_flying_laps
        flying = filter_flying_laps(df)
        if flying.empty:
            flying = df
    except ImportError:
        flying = df

    best = _get_best_lap(df)
    if best.empty:
        best = flying

    pct = best["LapDistPct"].values if "LapDistPct" in best.columns else None

    # ABS
    abs_col = None
    for c in ["BrakeABSactive", "ABSActive", "ABS"]:
        if c in best.columns:
            abs_col = c
            break

    if abs_col is not None:
        abs_vals = best[abs_col].values
        try:
            abs_vals = abs_vals.astype(float)
        except:
            pass
        active = (abs_vals > 0.5).astype(int)
        transitions = np.diff(active, prepend=0)
        starts = np.where(transitions == 1)[0]
        ends = np.where(transitions == -1)[0]
        if len(ends) < len(starts):
            ends = np.append(ends, len(active) - 1)

        result["abs_activations"] = len(starts)
        result["abs_duration_s"] = round(active.sum() / hz, 2)

        if pct is not None:
            for s, e in zip(starts, ends):
                result["abs_zones"].append({
                    "track_pct": round(float(pct[s]) * 100, 1),
                    "duration_s": round((e - s) / hz, 3),
                })

    # TC
    tc_col = None
    for c in ["dcTractionControlToggle", "TCActive", "DRSActive", "TC"]:
        if c in best.columns and best[c].std() > 0.01:
            tc_col = c
            break

    if tc_col is not None:
        tc_vals = best[tc_col].values
        try:
            tc_vals = tc_vals.astype(float)
        except:
            pass
        active = (tc_vals > 0.5).astype(int)
        transitions = np.diff(active, prepend=0)
        starts = np.where(transitions == 1)[0]
        ends = np.where(transitions == -1)[0]
        if len(ends) < len(starts):
            ends = np.append(ends, len(active) - 1)

        result["tc_activations"] = len(starts)
        result["tc_duration_s"] = round(active.sum() / hz, 2)

        if pct is not None:
            for s, e in zip(starts, ends):
                result["tc_zones"].append({
                    "track_pct": round(float(pct[s]) * 100, 1),
                    "duration_s": round((e - s) / hz, 3),
                })

    return result


# ════════════════════════════════════════════════════════════════════════════
# SECTOR FUEL CONSUMPTION
# ════════════════════════════════════════════════════════════════════════════

def compute_sector_fuel(df: pd.DataFrame, hz: float = 60.0) -> pd.DataFrame:
    """
    Calculate fuel consumed in each segment (Turn / Straight) for the best lap.
    Returns DataFrame: Segment, Type, FuelUsed_ml, FuelPct
    """
    if "FuelLevel" not in df.columns:
        return pd.DataFrame()

    best = _get_best_lap(df)
    if best.empty or "Segment" not in best.columns:
        return pd.DataFrame()

    rows = []
    total_fuel = 0
    for seg_label, seg_df in best.groupby("Segment", sort=False):
        fuel = seg_df["FuelLevel"].dropna()
        if len(fuel) < 2:
            continue
        used = float(fuel.iloc[0] - fuel.iloc[-1])
        if used < 0:
            used = 0  # sanity
        seg_type = seg_df["SegmentType"].iloc[0] if "SegmentType" in seg_df.columns else "?"
        total_fuel += used
        rows.append({
            "Segment": seg_label,
            "Type": seg_type,
            "FuelUsed_ml": round(used * 1000, 1),  # litres → ml
        })

    result = pd.DataFrame(rows)
    if not result.empty and total_fuel > 0:
        result["FuelPct"] = (result["FuelUsed_ml"] / (total_fuel * 1000) * 100).round(1)
    else:
        result["FuelPct"] = 0.0

    return result
