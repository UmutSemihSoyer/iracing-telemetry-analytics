import os
import io
import glob
import base64
import pandas as pd
from pathlib import Path
from utils import infer_hz

try:
    from core.ibt_parser import IBTFile, ibt_to_dashboard_df
    IBT_OK = True
except ImportError:
    IBT_OK = False

try:
    from core.corner_detector import detect_corners, label_segments
    CORNER_OK = True
except ImportError:
    CORNER_OK = False

def detect_laps(df):
    """Detect lap boundaries — delegates to lap_classifier for consistency."""
    from core.lap_classifier import classify_laps
    if "LapNumber" not in df.columns:
        # Simple threshold-based detection if channel is missing
        lap_id, laps, prev = 0, [], df["LapDistPct"].iloc[0]
        for val in df["LapDistPct"]:
            if prev > 0.90 and val < 0.10: lap_id += 1
            laps.append(lap_id + 1); prev = val
        df["LapNumber"] = laps
    
    # If LapType is already there, we don't need to re-classify (optimization for large files)
    if "LapType" in df.columns:
        return df
        
    return classify_laps(df)


def detect_stints(df):
    """
    Groups laps into stints based on pit visits or refueling.
    Adds 'StintNumber' column to df.
    """
    if "StintNumber" in df.columns: return df
    
    stint_id = 1
    stints = []
    
    # 1. Detection via OnPitRoad (Standard)
    has_pit = "OnPitRoad" in df.columns
    # 2. Detection via Fuel Level Resets (Fallback)
    fuel = df["FuelLevel"].values if "FuelLevel" in df.columns else []
    
    laps = df["LapNumber"].unique()
    current_stint = 1
    
    # Map lap -> stint
    lap_to_stint = {}
    prev_fuel = -1
    
    for ln in laps:
        lap_data = df[df["LapNumber"] == ln]
        if lap_data.empty: continue
        
        # Check if pit was visited in this lap
        in_pit = False
        if has_pit and lap_data["OnPitRoad"].any():
            in_pit = True
            
        # Check for refueling (Fuel at start of lap > Fuel at end of prev lap)
        lap_start_fuel = lap_data["FuelLevel"].dropna().iloc[0] if len(fuel)>0 else 0
        if prev_fuel > 0 and (lap_start_fuel - prev_fuel) > 2.0:
            in_pit = True # We assume a pit if fuel increased by 2L+

        if in_pit and ln > 1:
            # We only increment stint AFTER the pit lap is over 
            # (or we can mark the pit lap as the boundary)
            # Standard: New stint starts on the outlap
            pass 

        lap_to_stint[ln] = current_stint
        
        # If we were in pits this lap, the NEXT lap starts a new stint
        if in_pit:
            current_stint += 1
            
        prev_fuel = lap_data["FuelLevel"].dropna().iloc[-1] if len(fuel)>0 else 0
        
    df["StintNumber"] = df["LapNumber"].map(lap_to_stint).fillna(1)
    return df

def _enrich(df):
    hz = infer_hz(df)
    if "Speed" in df.columns:
        # Physical calculation: (dv/dt). 
        # diff() gives dv, multiplying by hz (which is 1/dt) gives accel.
        df["Calc_Accel"] = df["Speed"].diff().fillna(0) * hz
    if "SteeringWheelAngle" in df.columns:
        mx = df["SteeringWheelAngle"].abs().max()
        df["Steer"] = df["SteeringWheelAngle"] / mx if mx > 0 else 0.0
        
    # Slip Angle Calculation
    if "VelocityX" in df.columns and "VelocityY" in df.columns:
        import numpy as np
        # Avoid division by zero and extreme values
        vx = df["VelocityX"].values
        # Safe threshold to avoid infinity spikes at low speed
        v_mask = np.abs(vx) > 0.5
        slip = np.zeros_like(vx)
        slip[v_mask] = np.degrees(np.arctan2(df["VelocityY"].values[v_mask], vx[v_mask]))
        df["SlipAngle"] = slip
    elif "LatAccel" in df.columns and "Speed" in df.columns:
        import numpy as np
        # Approximation: LatAccel / (Speed^2 / Wheelbase) 
        # But simpler: we use LatAccel and YawRate in our UI if SlipAngle is missing
        pass

    
    df["Driver_State"] = "Coasting"
    has_t = "Throttle" in df.columns
    has_b = "Brake"    in df.columns
    if has_t: df.loc[df["Throttle"] > 0.05, "Driver_State"] = "Throttle"
    if has_b: df.loc[df["Brake"]    > 0.05, "Driver_State"] = "Braking"
    if has_t and has_b:
        df.loc[(df["Throttle"]>0.05)&(df["Brake"]>0.05),"Driver_State"] = "Overlap"
    
    if "LapDistPct" in df.columns:
        df["Micro_Sector"] = pd.cut(df["LapDistPct"], bins=20,
                                     labels=[f"S{i:02d}" for i in range(1,21)])
        # Corner-based segmentation (auto-detect turns & straights)
        if CORNER_OK:
            try:
                best = df
                if "LapNumber" in df.columns:
                    # Use first complete lap for detection
                    laps = sorted(df["LapNumber"].unique())
                    if len(laps) > 1:
                        best = df[df["LapNumber"] == laps[1]]  # skip first (often outlap)
                    elif laps:
                        best = df[df["LapNumber"] == laps[0]]
                if not best.empty:
                    corners = detect_corners(best)
                    df = label_segments(df, corners)
            except Exception as e:
                print(f"Corner detection warning: {e}")
    # Classify outlap / inlap / flying — always run after laps are detected
    try:
        from core.lap_classifier import classify_laps
        hz = infer_hz(df)
        df = classify_laps(df, hz)
    except Exception:
        if "LapType" not in df.columns: df["LapType"] = "Flying"
    return df

def load_file(contents, filename, driver_name="Driver", downsample=1):
    if "," not in contents:
        # If the file is too large, the browser might fail to generate the base64 string properly
        # or it might be truncated.
        raise ValueError("Invalid file upload format. The file might be too large to upload through the browser. For large files (>100MB), please place them in the project folder and use the 'Scan Folder' feature instead.")
    
    _, cs = contents.split(",", 1)
    raw   = base64.b64decode(cs)
    ext   = filename.lower().rsplit(".", 1)[-1]
    meta  = {}
    if ext == "ibt":
        if not IBT_OK: raise RuntimeError("ibt_parser.py missing")
        ibt  = IBTFile(raw)
        df   = ibt_to_dashboard_df(ibt, downsample=downsample)
        meta = ibt.meta
        meta["filename"] = filename
        meta["auto_setup"] = ibt.get_setup_dict()
        if not driver_name or driver_name.startswith("Driver "):
            driver_name = meta.get("driver_name", driver_name)
        df["Driver"] = driver_name
    else:
        # Detect where headers start (look for common telemetry headers)
        s_raw = raw.decode("utf-8", errors="ignore")
        lines = s_raw.splitlines()
        skip = 0
        for i, line in enumerate(lines[:10]):
            if "Time" in line or "Speed" in line or "Lap" in line:
                skip = i; break
        
        df = pd.read_csv(io.StringIO(s_raw), skiprows=skip)
        df.columns = df.columns.str.strip()
        
        # Rename common columns to match expectation
        rename_map = {"Lap":"LapNumber", "SessionTime":"Time", "RPM":"EngineRPMS"}
        df = df.rename(columns={k:v for k,v in rename_map.items() if k in df.columns})

        for col in ["ABSActive","DRSActive"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.lower()\
                                 .map({"true":1,"false":0}).fillna(0).astype(int)
        df["Driver"] = driver_name
        
        # Automatic lap detection if missing
        if "LapNumber" not in df.columns and "LapDistPct" in df.columns:
            df = detect_laps(df)
            
        meta = {"driver_name":driver_name,"track":"?","car_name":"?",
                "weather":"?","track_temp":"?","air_temp":"?",
                "series":"?","filename":filename}
    return _enrich(df), meta


def load_ibt_from_path(path: str, downsample: int = 1) -> tuple:
    if not IBT_OK: return None, {}
    ibt  = IBTFile(path)
    df   = ibt_to_dashboard_df(ibt, downsample=downsample)
    
    file_path = Path(path)
    meta = ibt.meta
    meta["filename"] = file_path.name
    meta["auto_setup"] = ibt.get_setup_dict()
    
    # iRacing embeds the recording client's name. For team sessions, prioritize the folder name.
    parent_dir = file_path.parent.name
    ignore_folders = {"", ".", "telemetry", "iracing", "data", "sessions", "iracingf1", "desktop"}
    
    if parent_dir and parent_dir.lower() not in ignore_folders:
        driver_name = parent_dir
    else:
        driver_name = meta.get("driver_name", "Driver")
        
    df["Driver"] = driver_name
    meta["driver_name"] = driver_name
    
    # _enrich will call detect_laps/classify_laps if needed
    return _enrich(df), meta


def lap_times(df, hz=60.0, flying_only=True):
    """
    Returns ranked lap time table.
    flying_only=True  → excludes outlaps / inlaps (default for all analysis)
    flying_only=False → returns ALL laps with LapType label (for display table)
    """
    from core.lap_classifier import classify_laps, flying_lap_times, lap_summary

    if "LapType" not in df.columns:
        df = classify_laps(df, infer_hz(df))

    if flying_only:
        lt = flying_lap_times(df, hz)
        if lt.empty: return pd.DataFrame()
        cols = ["Rank","Driver","LapNumber","LapTime_str","Gap","LapTime_s"]
        if "FuelUsed" in lt.columns: cols.append("FuelUsed")
        if "Coasting (%)" in lt.columns: cols.extend(["Coasting (%)", "Overlap (%)"])
        return lt[cols].rename(columns={"LapTime_str":"Time_str","LapTime_s":"Time_s"})
    else:
        # Full table including outlap / inlap, labelled
        lt = lap_summary(df, hz).sort_values("LapTime_s").reset_index(drop=True)
        if lt.empty: return lt
        # Rank only among flying laps, others show label instead
        lt["Rank"] = ""
        rank = 1
        for i, row in lt.iterrows():
            if row["LapType"] == "Flying":
                lt.at[i, "Rank"] = rank; rank += 1
            else:
                lt.at[i, "Rank"] = "—"
        best = lt[lt["LapType"]=="Flying"]["LapTime_s"].min() \
               if (lt["LapType"]=="Flying").any() else 0
        lt["Gap"] = lt.apply(
            lambda r: "REF" if (r["LapType"]=="Flying" and r["LapTime_s"]==best)
                      else f"[{r['LapType']}]" if r["LapType"]!="Flying"
                      else f"+{r['LapTime_s']-best:.3f}s", axis=1
        )
        lt = lt.rename(columns={"LapTime_str":"Time_str","LapTime_s":"Time_s"})
        cols = ["Rank","Driver","LapNumber","LapType","Time_str","Gap","Time_s"]
        if "FuelUsed" in lt.columns: cols.append("FuelUsed")
        if "Coasting (%)" in lt.columns: cols.extend(["Coasting (%)", "Overlap (%)"])
        return lt[cols]


def predict_fuel_strategy(df, hz=60.0):
    if "FuelLevel" not in df.columns: return None
    
    # Ensure stints are detected
    if "StintNumber" not in df.columns:
        df = detect_stints(df)

    # Filter to valid flying laps that are NOT in-laps or out-laps (which skew consumption)
    flying = df[df["LapType"] == "Flying"] if "LapType" in df.columns else df
    if flying.empty: return None
    
    consumptions = []
    # Key: Stint -> List of per-lap consumption
    stint_map = {}

    for (stint, ln), grp in flying.groupby(["StintNumber", "LapNumber"]):
        fuel = grp["FuelLevel"].dropna()
        if len(fuel) > 10:
            diff = fuel.iloc[0] - fuel.iloc[-1]
            # Sanity check: consumption should be positive and reasonable (e.g. < 15L per lap)
            if 0.05 < diff < 15.0:
                consumptions.append(diff)
                if stint not in stint_map: stint_map[stint] = []
                stint_map[stint].append(diff)
            
    if not consumptions: return None
    
    avg_consume = sum(consumptions) / len(consumptions)
    
    # Get recent stint consumption (more relevant for current strategy)
    current_stint_id = df["StintNumber"].max()
    recent_consume = avg_consume
    if current_stint_id in stint_map and len(stint_map[current_stint_id]) > 0:
        recent_consume = sum(stint_map[current_stint_id]) / len(stint_map[current_stint_id])

    remaining_fuel = df["FuelLevel"].dropna().iloc[-1]
    
    # Calculate Est Laps with a 0.5 lap safety margin
    total_est = (remaining_fuel / recent_consume) if recent_consume > 0 else 0
    safe_est = max(0, total_est - 0.5) 

    return {
        "avg_per_lap": avg_consume,
        "recent_avg": recent_consume,
        "remaining": remaining_fuel,
        "est_laps": safe_est,
        "total_used": df["FuelLevel"].dropna().iloc[0] - remaining_fuel,
        "laps_in_stint": len(stint_map.get(current_stint_id, [])),
        "stint_count": int(current_stint_id)
    }


def best_lap_df(df):
    lt = lap_times(df, flying_only=True)
    if not lt.empty:
        return df[df["LapNumber"]==lt.iloc[0]["LapNumber"]].copy()

    # No flying laps found — fallback: pick the most complete single lap
    # (by LapDistPct coverage) instead of returning ALL data which may
    # contain broken GPS from active resets / teleportation jumps.
    if "LapNumber" in df.columns and "LapDistPct" in df.columns:
        completeness = df.groupby("LapNumber")["LapDistPct"].max()
        if not completeness.empty:
            best_lap = completeness.idxmax()
            candidate = df[df["LapNumber"] == best_lap]
            # Only use it if it has reasonable data (at least 50% of track)
            if completeness[best_lap] > 0.5 and len(candidate) > 10:
                return candidate.copy()

    # Ultimate fallback: return entire df (shouldn't normally reach here)
    return df

def discover_ibts(folder: str) -> list:
    """Recursively find all IBT files in a folder, sorted newest first."""
    pattern = os.path.join(folder, "**", "*.ibt")
    files   = glob.glob(pattern, recursive=True)
    return sorted(files, key=os.path.getmtime, reverse=True)
