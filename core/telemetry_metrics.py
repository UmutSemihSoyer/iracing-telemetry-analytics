"""
╔══════════════════════════════════════════════════════════════╗
║   Telemetry Metrics Extractor                                ║
║   Extracts normalized session-level features for ML          ║
╚══════════════════════════════════════════════════════════════╝

Automatically called when a session is saved to the database.
Produces a dict of ~10 metrics that feed into anomaly detection.
"""

import numpy as np
import pandas as pd
from typing import Dict

__VERSION__ = "1.0.0"

METRIC_COLUMNS = [
    "avg_tire_temp_f", "avg_tire_temp_r", "tire_temp_spread",
    "yaw_spike_pct", "brake_stability", "throttle_smooth",
    "coasting_pct", "max_lat_g", "avg_speed", "oversteer_ratio",
]


def extract_session_metrics(df: pd.DataFrame) -> Dict[str, float]:
    """
    Extract normalized telemetry metrics from a session DataFrame.

    Returns dict with keys matching METRIC_COLUMNS.
    All values are floats, safe for SQL insertion.
    """
    m = {k: 0.0 for k in METRIC_COLUMNS}

    if df.empty:
        return m

    # ── 1. Tire Temperatures ──────────────────────────────────────────
    front_temp_cols = [c for c in ["TireTemp_FL_M", "TireTemp_FR_M"] if c in df.columns]
    rear_temp_cols = [c for c in ["TireTemp_RL_M", "TireTemp_RR_M"] if c in df.columns]

    if front_temp_cols:
        m["avg_tire_temp_f"] = float(df[front_temp_cols].mean().mean())
    if rear_temp_cols:
        m["avg_tire_temp_r"] = float(df[rear_temp_cols].mean().mean())

    # Tire temp spread = std across all 4 corners
    all_temp_cols = front_temp_cols + rear_temp_cols
    if all_temp_cols:
        corner_means = [df[c].mean() for c in all_temp_cols]
        m["tire_temp_spread"] = float(np.std(corner_means)) if len(corner_means) > 1 else 0.0

    # ── 2. Yaw Spike Percentage ───────────────────────────────────────
    if "YawRate" in df.columns:
        yaw_abs = df["YawRate"].abs()
        threshold = yaw_abs.quantile(0.95)
        if threshold > 0:
            m["yaw_spike_pct"] = float((yaw_abs > threshold).mean() * 100)

    # ── 3. Brake Stability ────────────────────────────────────────────
    # Lower is better — measures yaw during heavy braking
    if "Brake" in df.columns and "YawRate" in df.columns:
        heavy_brake = df[df["Brake"] > 0.8]
        if len(heavy_brake) > 10:
            yaw_during_brake = heavy_brake["YawRate"].abs().mean()
            yaw_overall = df["YawRate"].abs().mean()
            # Ratio: 1.0 = perfect, >2.0 = unstable
            m["brake_stability"] = float(yaw_during_brake / (yaw_overall + 1e-9))

    # ── 4. Throttle Smoothness ────────────────────────────────────────
    # Lower derivative std = smoother throttle application
    if "Throttle" in df.columns:
        throttle_diff = df["Throttle"].diff().abs().dropna()
        m["throttle_smooth"] = float(1.0 / (throttle_diff.std() + 1e-9))
        # Cap at reasonable values
        m["throttle_smooth"] = min(m["throttle_smooth"], 100.0)

    # ── 5. Coasting Percentage ────────────────────────────────────────
    if "Driver_State" in df.columns:
        m["coasting_pct"] = float((df["Driver_State"] == "Coasting").mean() * 100)
    elif "Throttle" in df.columns and "Brake" in df.columns:
        coasting = (df["Throttle"] < 0.05) & (df["Brake"] < 0.05)
        m["coasting_pct"] = float(coasting.mean() * 100)

    # ── 6. Max Lateral G ──────────────────────────────────────────────
    if "LatAccel" in df.columns:
        m["max_lat_g"] = float(df["LatAccel"].abs().max())

    # ── 7. Average Speed ──────────────────────────────────────────────
    if "Speed" in df.columns:
        m["avg_speed"] = float(df["Speed"].mean())

    # ── 8. Oversteer Ratio ────────────────────────────────────────────
    # Ratio of yaw rate during throttle+steering vs overall
    steer_col = "SteeringWheelAngle" if "SteeringWheelAngle" in df.columns else None
    if steer_col and "YawRate" in df.columns and "Throttle" in df.columns:
        turning = df[steer_col].abs() > 0.1
        throttle_on = df["Throttle"] > 0.5
        exit_mask = turning & throttle_on

        if exit_mask.sum() > 50:
            yaw_exit = df.loc[exit_mask, "YawRate"].abs().mean()
            yaw_all = df["YawRate"].abs().mean()
            m["oversteer_ratio"] = float(yaw_exit / (yaw_all + 1e-9))

    # ── Sanitize: replace NaN/inf with 0 ──────────────────────────────
    for k in m:
        if not np.isfinite(m[k]):
            m[k] = 0.0

    return m


# Human-readable labels for UI display
METRIC_LABELS = {
    "avg_tire_temp_f": "Front Tire Avg Temp (°C)",
    "avg_tire_temp_r": "Rear Tire Avg Temp (°C)",
    "tire_temp_spread": "Tire Temp Spread (σ°C)",
    "yaw_spike_pct": "Yaw Spike %",
    "brake_stability": "Brake Stability Ratio",
    "throttle_smooth": "Throttle Smoothness",
    "coasting_pct": "Coasting %",
    "max_lat_g": "Max Lateral G",
    "avg_speed": "Avg Speed (m/s)",
    "oversteer_ratio": "Exit Oversteer Ratio",
}
