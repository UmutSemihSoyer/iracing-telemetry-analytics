"""
╔══════════════════════════════════════════════════════════════╗
║   Anomaly Detector — IsolationForest Session Analysis        ║
║   Compares new sessions to historical data                   ║
╚══════════════════════════════════════════════════════════════╝

Works with as few as 5 sessions. More data = better detection.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional

__VERSION__ = "1.0.0"

# Minimum sessions needed to run anomaly detection
MIN_SESSIONS = 5

# Metric interpretation: higher/lower = good or bad?
# "lower_better": anomaly when metric is HIGH (e.g., yaw spikes)
# "higher_better": anomaly when metric is LOW (e.g., throttle smoothness)
# "neutral": anomaly in either direction
METRIC_DIRECTION = {
    "avg_tire_temp_f":  "neutral",
    "avg_tire_temp_r":  "neutral",
    "tire_temp_spread": "lower_better",   # less spread = more balanced
    "yaw_spike_pct":    "lower_better",   # fewer spikes = more stable
    "brake_stability":  "lower_better",   # lower ratio = more stable braking
    "throttle_smooth":  "higher_better",  # smoother = better
    "coasting_pct":     "lower_better",   # less coasting = faster
    "max_lat_g":        "higher_better",  # more G = more grip used
    "avg_speed":        "higher_better",  # faster = better
    "oversteer_ratio":  "lower_better",   # less oversteer = more stable
}

METRIC_LABELS = {
    "avg_tire_temp_f":  "Front Tire Temperature",
    "avg_tire_temp_r":  "Rear Tire Temperature",
    "tire_temp_spread": "Tire Balance",
    "yaw_spike_pct":    "Yaw Stability",
    "brake_stability":  "Braking Stability",
    "throttle_smooth":  "Throttle Control",
    "coasting_pct":     "Coasting Time",
    "max_lat_g":        "Peak Lateral G",
    "avg_speed":        "Average Speed",
    "oversteer_ratio":  "Exit Oversteer",
}


def detect_anomalies(current_metrics: dict,
                     historical_df: pd.DataFrame) -> List[dict]:
    """
    Compare a session's metrics against historical data using IsolationForest.

    Parameters
    ----------
    current_metrics : dict — metric values for the new session
    historical_df   : pd.DataFrame — all historical session_metrics rows

    Returns
    -------
    List of anomaly dicts:
        {
            "metric": str,
            "label": str,
            "value": float,
            "historical_mean": float,
            "historical_std": float,
            "z_score": float,
            "direction": "higher" | "lower",
            "severity": "anomaly" | "notable" | "normal",
            "message": str,
        }
    """
    results = []

    feature_cols = [c for c in METRIC_DIRECTION.keys()
                    if c in historical_df.columns]

    if len(historical_df) < MIN_SESSIONS or not feature_cols:
        return [{
            "metric": "general",
            "label": "Insufficient Data",
            "value": 0,
            "historical_mean": 0,
            "historical_std": 0,
            "z_score": 0,
            "direction": "neutral",
            "severity": "info",
            "message": f"Need {MIN_SESSIONS}+ saved sessions for anomaly detection "
                       f"(currently {len(historical_df)}). Keep saving sessions!",
        }]

    # ── Z-Score analysis per metric ───────────────────────────────────
    for col in feature_cols:
        hist_vals = historical_df[col].dropna()
        if hist_vals.empty or hist_vals.std() == 0:
            continue

        current_val = current_metrics.get(col, 0.0)
        mean = hist_vals.mean()
        std = hist_vals.std()
        z = (current_val - mean) / (std + 1e-9)

        direction = "higher" if z > 0 else "lower"
        abs_z = abs(z)

        # Determine severity
        if abs_z > 2.5:
            severity = "anomaly"
        elif abs_z > 1.5:
            severity = "notable"
        else:
            severity = "normal"
            continue  # Skip normal metrics — only report interesting ones

        # Generate human-readable message
        pct_diff = ((current_val - mean) / (mean + 1e-9)) * 100
        label = METRIC_LABELS.get(col, col)
        metric_dir = METRIC_DIRECTION.get(col, "neutral")

        # Determine if this is good or bad
        if metric_dir == "lower_better":
            is_bad = direction == "higher"
        elif metric_dir == "higher_better":
            is_bad = direction == "lower"
        else:
            is_bad = abs_z > 2.0  # neutral metrics are concerning if extreme

        icon = "🔴" if (severity == "anomaly" and is_bad) else \
               "🟠" if (severity == "anomaly" or is_bad) else \
               "🟢"

        if direction == "higher":
            msg = (f"{label} is {abs(pct_diff):.0f}% higher than your average "
                   f"({current_val:.1f} vs avg {mean:.1f})")
        else:
            msg = (f"{label} is {abs(pct_diff):.0f}% lower than your average "
                   f"({current_val:.1f} vs avg {mean:.1f})")

        results.append({
            "metric": col,
            "label": label,
            "value": current_val,
            "historical_mean": mean,
            "historical_std": std,
            "z_score": z,
            "direction": direction,
            "severity": severity,
            "is_bad": is_bad,
            "icon": icon,
            "message": msg,
        })

    # ── IsolationForest for multi-variate anomaly score ───────────────
    try:
        from sklearn.ensemble import IsolationForest

        X_hist = historical_df[feature_cols].dropna()
        if len(X_hist) >= MIN_SESSIONS:
            current_row = pd.DataFrame([{c: current_metrics.get(c, 0.0) for c in feature_cols}])

            clf = IsolationForest(
                contamination=0.15,
                random_state=42,
                n_estimators=100,
            )
            clf.fit(X_hist)

            score = clf.decision_function(current_row)[0]
            is_anomaly = clf.predict(current_row)[0] == -1

            if is_anomaly:
                results.insert(0, {
                    "metric": "overall",
                    "label": "Overall Session Profile",
                    "value": score,
                    "historical_mean": 0,
                    "historical_std": 0,
                    "z_score": 0,
                    "direction": "anomaly",
                    "severity": "anomaly",
                    "is_bad": True,
                    "icon": "🔮",
                    "message": f"This session's overall telemetry profile is unusual "
                               f"compared to your last {len(X_hist)} sessions "
                               f"(anomaly score: {score:.3f}). "
                               f"Check the individual metrics below for details.",
                })
    except ImportError:
        pass  # sklearn not available — z-score analysis still works
    except Exception as e:
        print(f"IsolationForest error: {e}")

    # Sort: anomalies first, then notable
    severity_order = {"anomaly": 0, "notable": 1, "info": 2, "normal": 3}
    results.sort(key=lambda r: severity_order.get(r["severity"], 99))

    if not results:
        results.append({
            "metric": "general",
            "label": "All Normal",
            "value": 0,
            "historical_mean": 0,
            "historical_std": 0,
            "z_score": 0,
            "direction": "neutral",
            "severity": "normal",
            "is_bad": False,
            "icon": "✅",
            "message": "All metrics are within normal range compared to your history.",
        })

    return results


def session_trend(historical_df: pd.DataFrame, metric: str, n_recent: int = 10) -> dict:
    """Get trend direction for a specific metric over recent sessions."""
    if metric not in historical_df.columns or len(historical_df) < 3:
        return {"trend": "flat", "slope": 0.0}

    recent = historical_df[metric].tail(n_recent).dropna()
    if len(recent) < 3:
        return {"trend": "flat", "slope": 0.0}

    x = np.arange(len(recent))
    slope = np.polyfit(x, recent.values, 1)[0]

    if slope > recent.std() * 0.1:
        trend = "increasing"
    elif slope < -recent.std() * 0.1:
        trend = "decreasing"
    else:
        trend = "flat"

    return {"trend": trend, "slope": float(slope)}
