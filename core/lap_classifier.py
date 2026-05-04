"""
Lap Classifier
==============
Detects outlap, inlap and flying laps.

Priority order:
  1. OnPitRoad IBT channel  — most accurate
  2. PitSvStatus / InCar flags
  3. Lap time threshold     — fallback (median × 1.25)
  4. LapDistPct start check — if lap starts near 0.0 after a gap, likely outlap

Usage:
    from core.lap_classifier import classify_laps, filter_flying_laps

    df = classify_laps(df)           # adds 'LapType' column
    flying = filter_flying_laps(df)  # returns only FLYING laps
"""

import numpy as np
import pandas as pd

__VERSION__ = "1.0.1-NaNFix"


# Lap type labels
FLYING  = "Flying"
OUTLAP  = "Outlap"
INLAP   = "Inlap"
UNKNOWN = "Unknown"
DNF     = "DNF"
ACTIVE_RESET = "Active Reset"

# If a lap time is longer than median × OUTLAP_RATIO, it's suspicious
OUTLAP_RATIO = 1.25


def classify_laps(df: pd.DataFrame, hz: float = 60.0) -> pd.DataFrame:
    """
    Adds 'LapType' column:  'Flying' | 'Outlap' | 'Inlap' | 'Unknown'
    Also adds 'LapTime_s' column (estimated seconds per lap).

    Works with both IBT (rich channels) and CSV.
    """
    df = df.copy()

    if "LapNumber" not in df.columns:
        df["LapType"]   = UNKNOWN
        df["LapTime_s"] = np.nan
        return df

    laps = sorted(df["LapNumber"].unique())

    # ── Step 1: estimate lap times ────────────────────────────────────────────
    lap_time_map = {}
    
    # Pre-calculate lap groups to avoid O(N^2) filtering
    lap_groups = {lap: group for lap, group in df.groupby("LapNumber")}
    
    # Priority 1 & 2: iRacing's exactly calculated lap time (LapLastLapTime)
    last_time_col = "LapLastLapTime" if "LapLastLapTime" in df.columns else ("LapLastTime" if "LapLastTime" in df.columns else None)
    curr_time_col = "LapCurrentTime" if "LapCurrentTime" in df.columns else None

    for i, lap in enumerate(laps):
        # Exact time from next lap
        if last_time_col and (lap + 1) in lap_groups:
            next_lap_data = lap_groups[lap + 1]
            valid_vals = next_lap_data[last_time_col].dropna()
            valid_vals = valid_vals[valid_vals > 0]
            if not valid_vals.empty:
                lap_time_map[lap] = float(valid_vals.max())
        
        # Fallback from current lap max (with reset detection)
        if lap not in lap_time_map and curr_time_col:
            lap_data = lap_groups[lap]
            times = lap_data[curr_time_col].values
            if len(times) > 1:
                dt = np.diff(times)
                resets = np.where(dt < -1.0)[0]
                lap_time_map[lap] = float(times[resets[0]] if len(resets) > 0 else times.max())

    # Priority 3: SessionTime Delta
    if len(lap_time_map) < len(laps):
        t_col = "Time_s" if "Time_s" in df.columns else ("Time" if "Time" in df.columns else ("SessionTime" if "SessionTime" in df.columns else None))
        if t_col:
            for lap in laps:
                if lap in lap_time_map: continue
                lap_data = lap_groups.get(lap)
                if lap_data is not None:
                    lap_time_map[lap] = float(lap_data[t_col].max() - lap_data[t_col].min())

    # Priority 4: Sample count estimation based on Hz
    if len(lap_time_map) < len(laps):
        for lap in laps:
            if lap in lap_time_map: continue
            lap_data = lap_groups.get(lap)
            if lap_data is not None:
                lap_time_map[lap] = len(lap_data) / hz

    # Median of valid laps (used as reference for threshold)
    valid_times = [t for t in lap_time_map.values() if t > 0]
    median_time = np.median(valid_times) if valid_times else 0

    # ── Step 2: detect via OnPitRoad channel (IBT) ────────────────────────────
    has_pit_channel = ("OnPitRoad" in df.columns and
                       df["OnPitRoad"].notna().any() and
                       df["OnPitRoad"].max() > 0)

    pit_laps = set()
    if has_pit_channel:
        # A lap is 'pit involved' if ANY sample on that lap has OnPitRoad == 1
        pit_involvement = (df.groupby("LapNumber")["OnPitRoad"]
                             .max()
                             .astype(int))
        pit_laps = set(pit_involvement[pit_involvement > 0].index)

    # ── Step 3: classify each lap ─────────────────────────────────────────────
    lap_types = {}

    sess_max_spd = df["Speed"].max() if "Speed" in df.columns else 0

    for i, lap in enumerate(laps):
        lap_t = lap_time_map.get(lap, 0)
        lap_data = lap_groups.get(lap)
        if lap_data is None: continue

        # If OnPitRoad channel says this lap touched pit road
        if has_pit_channel and lap in pit_laps:
            # First lap in session with pit = outlap
            # Last lap with pit = inlap
            # Both possible if it's a very short session
            is_first = (i == 0)
            is_last  = (i == len(laps) - 1)
            prev_pit = (laps[i-1] in pit_laps) if i > 0 else False
            next_pit = (laps[i+1] in pit_laps) if i < len(laps)-1 else False

            if is_first or prev_pit:
                lap_types[lap] = OUTLAP
            elif is_last or next_pit:
                lap_types[lap] = INLAP
            else:
                # Lap itself crossed pit road → both out and in
                lap_types[lap] = OUTLAP
            continue

        # Fallback: lap time threshold
        if median_time > 0 and lap_t > 0:
            if lap_t > median_time * OUTLAP_RATIO:
                # Long lap — is it first or last?
                if i == 0:
                    lap_types[lap] = OUTLAP
                elif i == len(laps) - 1:
                    lap_types[lap] = INLAP
                else:
                    lap_max_spd = lap_data["Speed"].max() if "Speed" in lap_data.columns else 0
                    if sess_max_spd > 0 and lap_max_spd < sess_max_spd * 0.75:
                        lap_types[lap] = "Safety Car"
                    else:
                        lap_types[lap] = "Invalid"
                continue

        # Everything else = flying
        lap_types[lap] = FLYING

    # ── Step 4: additional heuristics ─────────────────────────────────────────
    # Heuristic 1: first lap always suspicious
    if laps and laps[0] in lap_types and lap_types[laps[0]] == FLYING:
        first_lap_data = lap_groups.get(laps[0])
        if first_lap_data is not None and not first_lap_data.empty:
            first_speed = first_lap_data["Speed"].iloc[0] if "Speed" in first_lap_data.columns else 0
            median_speed = df["Speed"].median() if "Speed" in df.columns else 0
            if first_speed < median_speed * 0.5:
                lap_types[laps[0]] = OUTLAP

    # Heuristic 2: DNF / Short Lap / Active Reset
    for lap in laps:
        lap_data = lap_groups.get(lap)
        if lap_data is None or lap_data.empty: continue
        
        # 1. DNF check
        if "LapDistPct" in lap_data.columns:
            if lap_data["LapDistPct"].max() < 0.95:
                lap_types[lap] = DNF
                continue
        
        # 2. Short lap check
        if lap_types.get(lap, FLYING) == FLYING and len(lap_data) < hz * 10:
            lap_types[lap] = "Invalid"
            continue
            
        # 3. Active reset check
        if "LapDistPct" in lap_data.columns and len(lap_data) > 3:
            pct = lap_data["LapDistPct"].values
            dpct = np.diff(pct)
            if (dpct > 0.05).any() or ((dpct < -0.05) & (dpct > -0.95)).any():
                lap_types[lap] = ACTIVE_RESET

    # ── Apply to DataFrame ────────────────────────────────────────────────────
    df["LapType"]   = df["LapNumber"].map(lap_types).fillna(UNKNOWN)
    df["LapTime_s"] = df["LapNumber"].map(lap_time_map).fillna(0)

    return df


def filter_flying_laps(df: pd.DataFrame) -> pd.DataFrame:
    """Return only rows belonging to FLYING laps."""
    if "LapType" not in df.columns:
        df = classify_laps(df)
    return df[df["LapType"] == FLYING].copy()


def lap_summary(df: pd.DataFrame, hz: float = 60.0) -> pd.DataFrame:
    """
    Returns per-lap summary DataFrame with LapType clearly shown.

    Columns: LapNumber, LapType, LapTime_s, LapTime_str, Driver
    """
    if "LapType" not in df.columns:
        df = classify_laps(df, hz)

    rows = []
    for lap, grp in df.groupby("LapNumber"):
        lap_t = 0
        if "LapTime_s" in grp.columns:
            val = grp["LapTime_s"].iloc[0]
            if pd.notna(val) and val > 0:
                lap_t = val
        
        # Fallback if STILL 0 or NaN
        if lap_t <= 0:
            if "Time" in grp.columns:
                lap_t = grp["Time"].max() - grp["Time"].min()
            elif "SessionTime" in grp.columns:
                lap_t = grp["SessionTime"].max() - grp["SessionTime"].min()
            else:
                lap_t = len(grp) / hz

        lap_type = grp["LapType"].iloc[0] if "LapType" in grp.columns else UNKNOWN
        driver   = grp["Driver"].iloc[0]  if "Driver"  in grp.columns else "?"
        
        fuel_used = ""
        if "FuelLevel" in grp.columns:
            valid_fuel = grp["FuelLevel"].dropna()
            if not valid_fuel.empty:
                used = valid_fuel.iloc[0] - valid_fuel.iloc[-1]
                if used > 0.1:
                    fuel_used = f"{used:.2f}L"
                    
        coasting_pct, overlap_pct = 0.0, 0.0
        if "Driver_State" in grp.columns:
            total_samples = len(grp)
            if total_samples > 0:
                counts = grp["Driver_State"].value_counts()
                coasting_pct = round((counts.get("Coasting", 0) / total_samples) * 100, 1)
                overlap_pct  = round((counts.get("Overlap", 0) / total_samples) * 100, 1)

        rows.append({
            "Driver":       driver,
            "LapNumber":    int(lap),
            "LapType":      lap_type,
            "LapTime_s":    round(float(lap_t), 3),
            "LapTime_str":  "DNF" if lap_type == DNF else _fmt(lap_t),
            "FuelUsed":     fuel_used,
            "Coasting (%)": f"{coasting_pct}%",
            "Overlap (%)":  f"{overlap_pct}%",
        })

    summary = pd.DataFrame(rows)
    return summary


def flying_lap_times(df: pd.DataFrame, hz: float = 60.0) -> pd.DataFrame:
    """
    Like lap_times() but only includes FLYING laps.
    Returns ranked DataFrame with Gap column.
    """
    if "LapType" not in df.columns:
        df = classify_laps(df, hz)

    lt = lap_summary(df, hz)
    lt = lt[lt["LapType"] == FLYING].sort_values("LapTime_s").reset_index(drop=True)

    if lt.empty:
        return lt

    best = lt["LapTime_s"].iloc[0]
    lt["Rank"] = range(1, len(lt) + 1)
    lt["Gap"]  = lt["LapTime_s"].apply(
        lambda s: "REF" if s == best else f"+{s-best:.3f}s"
    )
    cols = ["Rank","Driver","LapNumber","LapType","LapTime_str","Gap","LapTime_s"]
    if "FuelUsed" in lt.columns: cols.append("FuelUsed")
    if "Coasting (%)" in lt.columns: cols.extend(["Coasting (%)", "Overlap (%)"])
    return lt[cols]


def _fmt(s: float) -> str:
    if pd.isna(s) or np.isinf(s) or s <= 0:
        return "--:--.---"
    return f"{int(s//60)}:{s%60:06.3f}"
