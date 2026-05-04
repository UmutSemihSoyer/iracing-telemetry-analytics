"""
╔══════════════════════════════════════════════════════════════╗
║   iRacing Setup Advisor  —  Rule-Based Analysis Engine       ║
║   Telemetry + Setup → Actionable Recommendations             ║
╚══════════════════════════════════════════════════════════════╝

Usage:
    from services.setup_advisor import analyze_setup, setup_score
    recommendations = analyze_setup(df, setup_dict)
    score = setup_score(recommendations)
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional

__VERSION__ = "1.0.0"

# ════════════════════════════════════════════════════════════════════════════
# CONSTANTS & DEFAULTS
# ════════════════════════════════════════════════════════════════════════════

# Default target hot pressures (kPa) — GT3 class baseline
DEFAULT_TARGET_HOT_KPA = 172.0  # ~24.9 PSI — typical GT3 target
TARGET_TOLERANCE_KPA = 5.0       # ±5 kPa acceptable window

# Temperature thresholds (°C)
TEMP_IMBALANCE_THRESHOLD = 12.0   # Inner-Outer temp diff triggering camber advice
TEMP_MIDDLE_EXCESS = 5.0          # Middle hotter than both sides → pressure too high
OPTIMAL_TEMP_RANGE = (80, 105)    # Default optimal surface temp range

# Understeer/Oversteer detection
UNDERSTEER_STEER_THRESHOLD = 0.3  # radians — significant steering input
OVERSTEER_YAW_THRESHOLD = 0.15   # rad/s — yaw rate spike

# Suspension
SUSP_TRAVEL_RATIO_WARN = 0.85    # Using >85% of travel → bottoming out risk

# Severity priority for sorting
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2, "good": 3}


# ════════════════════════════════════════════════════════════════════════════
# MAIN API
# ════════════════════════════════════════════════════════════════════════════

def analyze_setup(df: pd.DataFrame, setup: dict,
                  tire_type: str = "Dry",
                  target_hot_kpa: float = DEFAULT_TARGET_HOT_KPA) -> List[dict]:
    """
    Analyse telemetry DataFrame + current setup dict → list of recommendations.

    Each recommendation:
        {
            "category": str,    # "Tires" | "Aero" | "Brakes" | ...
            "severity": str,    # "critical" | "warning" | "info" | "good"
            "icon": str,
            "title": str,
            "detail": str,
            "parameter": str,   # setup key affected
            "direction": str,   # "increase" | "decrease" | "check"
            "suggested_delta": str,
        }
    """
    if df.empty:
        return [_rec("General", "warning", "⚠️", "No Data",
                      "Telemetry data is empty.", "", "check", "")]

    # Filter to flying laps for cleaner analysis
    try:
        from core.lap_classifier import filter_flying_laps
        flying = filter_flying_laps(df)
        if flying.empty or len(flying) < 100:
            flying = df
    except ImportError:
        flying = df

    recs: List[dict] = []

    # Run all rule checks
    recs.extend(_check_tire_pressures(flying, setup, target_hot_kpa))
    recs.extend(_check_tire_temps_camber(flying, setup))
    recs.extend(_check_tire_temps_pressure(flying, setup))
    recs.extend(_check_front_rear_balance(flying, setup))
    recs.extend(_check_aero_understeer(flying, setup))
    recs.extend(_check_aero_oversteer(flying, setup))
    recs.extend(_check_brake_bias(flying, setup))
    recs.extend(_check_suspension_travel(flying, setup))
    recs.extend(_check_diff_oversteer(flying, setup))
    recs.extend(_check_damper_stability(flying, setup))

    # Sort by severity
    recs.sort(key=lambda r: SEVERITY_ORDER.get(r["severity"], 99))

    # If no issues found, add a positive message
    if not recs:
        recs.append(_rec("General", "good", "✅", "Setup Looks Good",
                         "No significant issues detected from telemetry. "
                         "Fine-tune based on driver feel.",
                         "", "check", ""))

    return recs


def setup_score(recommendations: List[dict]) -> int:
    """Calculate an overall setup score out of 100 based on recommendations."""
    if not recommendations:
        return 85  # default — no data

    penalty_map = {"critical": 20, "warning": 8, "info": 2, "good": 0}
    total_penalty = sum(penalty_map.get(r["severity"], 0) for r in recommendations)
    return max(0, min(100, 100 - total_penalty))


def category_grades(recommendations: List[dict]) -> Dict[str, str]:
    """Return per-category grade: ✅ / ⚠️ / 🔴."""
    cats = {}
    for r in recommendations:
        cat = r["category"]
        sev = r["severity"]
        current = cats.get(cat, "good")
        if SEVERITY_ORDER.get(sev, 99) < SEVERITY_ORDER.get(current, 99):
            cats[cat] = sev
    grade_map = {"critical": "🔴", "warning": "⚠️", "info": "ℹ️", "good": "✅"}
    return {cat: grade_map.get(sev, "✅") for cat, sev in cats.items()}


# ════════════════════════════════════════════════════════════════════════════
# RULE IMPLEMENTATIONS
# ════════════════════════════════════════════════════════════════════════════

def _rec(category, severity, icon, title, detail, parameter, direction, suggested_delta):
    return {
        "category": category, "severity": severity, "icon": icon,
        "title": title, "detail": detail, "parameter": parameter,
        "direction": direction, "suggested_delta": suggested_delta,
    }


# ── Rule 1 & 2: Tire Pressure vs Target ─────────────────────────────────
def _check_tire_pressures(df, setup, target_kpa):
    recs = []
    pressure_cols = {
        "FL": "TirePress_FL", "FR": "TirePress_FR",
        "RL": "TirePress_RL", "RR": "TirePress_RR",
    }
    cold_keys = {
        "FL": "fl_cold_p", "FR": "fr_cold_p",
        "RL": "rl_cold_p", "RR": "rr_cold_p",
    }

    for corner, col in pressure_cols.items():
        if col not in df.columns:
            continue
        mean_p = df[col].mean()
        if mean_p < 1:
            continue

        # Auto-detect unit: if mean > 100 → likely kPa, else PSI
        if mean_p < 50:
            mean_kpa = mean_p * 6.895  # PSI → kPa
        else:
            mean_kpa = mean_p

        cold_current = setup.get(cold_keys[corner])
        diff = mean_kpa - target_kpa

        if diff > TARGET_TOLERANCE_KPA:
            delta_str = f"-{diff:.0f} kPa"
            sev = "critical" if diff > TARGET_TOLERANCE_KPA * 2 else "warning"
            cold_note = f" (current cold: {cold_current} kPa)" if cold_current else ""
            recs.append(_rec(
                "Tires", sev, "🔴" if sev == "critical" else "🟠",
                f"{corner} hot pressure {diff:.0f} kPa above target",
                f"{corner} running at {mean_kpa:.0f} kPa (target: {target_kpa:.0f} kPa). "
                f"Reduce cold pressure by ~{diff:.0f} kPa{cold_note}.",
                cold_keys[corner], "decrease", delta_str,
            ))
        elif diff < -TARGET_TOLERANCE_KPA:
            delta_str = f"+{abs(diff):.0f} kPa"
            sev = "critical" if diff < -TARGET_TOLERANCE_KPA * 2 else "warning"
            cold_note = f" (current cold: {cold_current} kPa)" if cold_current else ""
            recs.append(_rec(
                "Tires", sev, "🔴" if sev == "critical" else "🟠",
                f"{corner} hot pressure {abs(diff):.0f} kPa below target",
                f"{corner} running at {mean_kpa:.0f} kPa (target: {target_kpa:.0f} kPa). "
                f"Increase cold pressure by ~{abs(diff):.0f} kPa{cold_note}.",
                cold_keys[corner], "increase", delta_str,
            ))
        else:
            recs.append(_rec(
                "Tires", "good", "✅",
                f"{corner} pressure in target window",
                f"Running at {mean_kpa:.0f} kPa — within {TARGET_TOLERANCE_KPA:.0f} kPa of target.",
                cold_keys[corner], "check", "OK",
            ))

    return recs


# ── Rule 3 & 4: Tire Temp Inner vs Outer → Camber ───────────────────────
def _check_tire_temps_camber(df, setup):
    recs = []
    temp_map = {
        "FL": ("TireTemp_FL_L", "TireTemp_FL_R", "fl_camber"),
        "FR": ("TireTemp_FR_L", "TireTemp_FR_R", "fr_camber"),
        "RL": ("TireTemp_RL_L", "TireTemp_RL_R", "rl_camber"),
        "RR": ("TireTemp_RR_L", "TireTemp_RR_R", "rr_camber"),
    }

    for corner, (inner_col, outer_col, camber_key) in temp_map.items():
        if inner_col not in df.columns or outer_col not in df.columns:
            continue
        t_inner = df[inner_col].mean()
        t_outer = df[outer_col].mean()
        if t_inner < 20 or t_outer < 20:
            continue  # No real data

        delta = t_inner - t_outer
        camber_current = setup.get(camber_key)
        camber_str = f" (current: {camber_current}°)" if camber_current is not None else ""

        if delta > TEMP_IMBALANCE_THRESHOLD:
            adj = delta * 0.04  # approximate camber adjustment
            recs.append(_rec(
                "Tires", "warning", "🟠",
                f"{corner} inner edge overheating (Δ{delta:.1f}°C)",
                f"Inner tire is {delta:.1f}°C hotter than outer. "
                f"Decrease negative camber by ~{adj:.2f}°{camber_str}.",
                camber_key, "decrease", f"-{adj:.2f}°",
            ))
        elif delta < -TEMP_IMBALANCE_THRESHOLD:
            adj = abs(delta) * 0.04
            recs.append(_rec(
                "Tires", "warning", "🟠",
                f"{corner} outer edge overheating (Δ{abs(delta):.1f}°C)",
                f"Outer tire is {abs(delta):.1f}°C hotter than inner. "
                f"Increase negative camber by ~{adj:.2f}°{camber_str}.",
                camber_key, "increase", f"+{adj:.2f}°",
            ))

    return recs


# ── Rule 5 & 6: Middle Temp vs Sides → Pressure ─────────────────────────
def _check_tire_temps_pressure(df, setup):
    recs = []
    temp_map = {
        "FL": ("TireTemp_FL_L", "TireTemp_FL_M", "TireTemp_FL_R", "fl_cold_p"),
        "FR": ("TireTemp_FR_L", "TireTemp_FR_M", "TireTemp_FR_R", "fr_cold_p"),
        "RL": ("TireTemp_RL_L", "TireTemp_RL_M", "TireTemp_RL_R", "rl_cold_p"),
        "RR": ("TireTemp_RR_L", "TireTemp_RR_M", "TireTemp_RR_R", "rr_cold_p"),
    }

    for corner, (inner, mid, outer, press_key) in temp_map.items():
        if mid not in df.columns:
            continue
        if inner not in df.columns or outer not in df.columns:
            continue

        t_inner = df[inner].mean()
        t_mid = df[mid].mean()
        t_outer = df[outer].mean()

        if t_mid < 20:
            continue

        sides_avg = (t_inner + t_outer) / 2

        if t_mid > sides_avg + TEMP_MIDDLE_EXCESS:
            diff = t_mid - sides_avg
            recs.append(_rec(
                "Tires", "warning", "🟠",
                f"{corner} center overheating ({t_mid:.0f}°C)",
                f"Middle of tire is {diff:.1f}°C hotter than edges — pressure too high. "
                f"Reduce cold pressure by ~{diff * 0.5:.0f} kPa.",
                press_key, "decrease", f"-{diff * 0.5:.0f} kPa",
            ))
        elif t_mid < sides_avg - TEMP_MIDDLE_EXCESS:
            diff = sides_avg - t_mid
            recs.append(_rec(
                "Tires", "info", "🔵",
                f"{corner} center running cold ({t_mid:.0f}°C)",
                f"Middle of tire is {diff:.1f}°C cooler than edges — pressure may be too low. "
                f"Increase cold pressure by ~{diff * 0.5:.0f} kPa.",
                press_key, "increase", f"+{diff * 0.5:.0f} kPa",
            ))

    return recs


# ── Rule 14: Front-Rear Temperature Balance → ARB ───────────────────────
def _check_front_rear_balance(df, setup):
    recs = []
    front_cols = [c for c in ["TireTemp_FL_M", "TireTemp_FR_M"] if c in df.columns]
    rear_cols = [c for c in ["TireTemp_RL_M", "TireTemp_RR_M"] if c in df.columns]

    if not front_cols or not rear_cols:
        return recs

    front_avg = df[front_cols].mean().mean()
    rear_avg = df[rear_cols].mean().mean()

    if front_avg < 20 or rear_avg < 20:
        return recs

    diff = front_avg - rear_avg

    if diff > 8:
        recs.append(_rec(
            "Suspension", "warning", "🟠",
            f"Fronts running {diff:.0f}°C hotter than rears",
            f"Front avg: {front_avg:.0f}°C, Rear avg: {rear_avg:.0f}°C. "
            f"Consider softening front ARB or stiffening rear ARB to transfer load rearward.",
            "arb_front", "decrease", "Soften 1-2 clicks",
        ))
    elif diff < -8:
        recs.append(_rec(
            "Suspension", "warning", "🟠",
            f"Rears running {abs(diff):.0f}°C hotter than fronts",
            f"Front avg: {front_avg:.0f}°C, Rear avg: {rear_avg:.0f}°C. "
            f"Consider stiffening front ARB or softening rear ARB to transfer load forward.",
            "arb_rear", "decrease", "Soften 1-2 clicks",
        ))
    else:
        recs.append(_rec(
            "Suspension", "good", "✅",
            "Front-rear temperature balance is good",
            f"Front avg: {front_avg:.0f}°C, Rear avg: {rear_avg:.0f}°C (Δ{abs(diff):.0f}°C).",
            "", "check", "OK",
        ))

    return recs


# ── Rule 7: Understeer Detection → Aero ─────────────────────────────────
def _check_aero_understeer(df, setup):
    recs = []
    steer_col = "SteeringWheelAngle" if "SteeringWheelAngle" in df.columns else None
    if steer_col is None or "LatAccel" not in df.columns or "Speed" not in df.columns:
        return recs

    # Look for moments with high steering but low lateral G relative to speed
    fast_mask = df["Speed"] > 20  # >72 km/h
    if fast_mask.sum() < 100:
        return recs

    fast = df[fast_mask].copy()
    steer_abs = fast[steer_col].abs()
    high_steer = steer_abs > UNDERSTEER_STEER_THRESHOLD

    if high_steer.sum() < 50:
        return recs

    # Understeer ratio: high steering input but low lateral response
    lat_response = fast.loc[high_steer, "LatAccel"].abs()
    steer_input = steer_abs[high_steer]

    # Normalize: expected lat G per unit steering (higher = better response)
    response_ratio = lat_response.mean() / (steer_input.mean() + 1e-9)

    # Compare with overall average
    overall_ratio = fast["LatAccel"].abs().mean() / (steer_abs.mean() + 1e-9)

    if response_ratio < overall_ratio * 0.65:
        wing = setup.get("wing_setting")
        wing_str = f" (current wing: {wing})" if wing is not None else ""
        recs.append(_rec(
            "Aero", "warning", "🟠",
            "Understeer detected at high speed",
            f"Car shows reduced lateral response during heavy steering inputs. "
            f"Increase front downforce (raise front wing or lower front ride height){wing_str}.",
            "wing_setting", "increase", "+1 click",
        ))

    return recs


# ── Rule 8: Oversteer Detection → Aero ──────────────────────────────────
def _check_aero_oversteer(df, setup):
    recs = []
    if "YawRate" not in df.columns or "Speed" not in df.columns:
        return recs

    fast_mask = df["Speed"] > 20
    if fast_mask.sum() < 100:
        return recs

    fast = df[fast_mask]
    yaw_abs = fast["YawRate"].abs()

    # Count yaw rate spikes (sudden rotation = oversteer snap)
    yaw_spikes = (yaw_abs > yaw_abs.quantile(0.95)).sum()
    total = len(fast)
    spike_pct = yaw_spikes / total * 100

    if spike_pct > 5:
        # Check if spikes correlate with throttle (power oversteer)
        throttle_col = "Throttle" if "Throttle" in df.columns else None
        context = ""
        param = "wing_setting"
        if throttle_col:
            spike_mask = yaw_abs > yaw_abs.quantile(0.95)
            throttle_during_spike = fast.loc[spike_mask, throttle_col].mean()
            if throttle_during_spike > 0.5:
                context = " Mostly on throttle application (power oversteer). "
                param = "diff_preload"

        recs.append(_rec(
            "Aero", "warning", "🟠",
            f"Oversteer tendency detected ({spike_pct:.1f}% yaw spikes)",
            f"Car exhibits excessive yaw rotation in {spike_pct:.1f}% of high-speed samples.{context}"
            f"Increase rear downforce or soften rear suspension.",
            param, "increase" if param == "wing_setting" else "decrease",
            "+1 click" if param == "wing_setting" else "-1 Nm",
        ))
    else:
        recs.append(_rec(
            "Aero", "good", "✅",
            "Rear stability looks good",
            f"Yaw rate spikes at {spike_pct:.1f}% — within normal range.",
            "", "check", "OK",
        ))

    return recs


# ── Rule 9 & 10: Brake Bias ─────────────────────────────────────────────
def _check_brake_bias(df, setup):
    recs = []
    if "Brake" not in df.columns or "YawRate" not in df.columns:
        return recs

    steer_col = "SteeringWheelAngle" if "SteeringWheelAngle" in df.columns else None

    # Analyse heavy braking zones
    heavy_brake = df[df["Brake"] > 0.8]
    if len(heavy_brake) < 30:
        return recs

    bias_current = setup.get("brake_bias")
    bias_str = f" (current: {bias_current}%)" if bias_current is not None else ""

    # Check for front lock-up: heavy brake + increasing steering (trying to correct)
    if steer_col:
        steer_diff = heavy_brake[steer_col].diff().abs()
        excessive_correction = (steer_diff > 0.05).mean() * 100
        if excessive_correction > 40:
            recs.append(_rec(
                "Brakes", "warning", "🟠",
                f"Possible front lock-up under braking",
                f"Heavy steering corrections detected in {excessive_correction:.0f}% of hard braking zones. "
                f"Move brake bias rearward by 0.5-1.0%{bias_str}.",
                "brake_bias", "decrease", "-0.5%",
            ))
            return recs

    # Check for rear instability: high yaw during braking
    yaw_during_brake = heavy_brake["YawRate"].abs()
    yaw_median = df["YawRate"].abs().median()
    brake_yaw_ratio = yaw_during_brake.mean() / (yaw_median + 1e-9)

    if brake_yaw_ratio > 2.0:
        recs.append(_rec(
            "Brakes", "warning", "🟠",
            "Rear instability under braking",
            f"Yaw rate during heavy braking is {brake_yaw_ratio:.1f}× higher than average. "
            f"Move brake bias forward by 0.5-1.0%{bias_str}.",
            "brake_bias", "increase", "+0.5%",
        ))
    else:
        recs.append(_rec(
            "Brakes", "good", "✅",
            "Brake bias well balanced",
            f"No lock-ups or rear instability detected during heavy braking{bias_str}.",
            "brake_bias", "check", "OK",
        ))

    return recs


# ── Rule 11: Suspension Travel → Springs / Bump Rubber ──────────────────
def _check_suspension_travel(df, setup):
    recs = []
    susp_cols = {
        "FL": ("Suspension_FL", "fl_spring"),
        "FR": ("Suspension_FR", "fr_spring"),
        "RL": ("Suspension_RL", "rl_spring"),
        "RR": ("Suspension_RR", "rr_spring"),
    }

    for corner, (col, spring_key) in susp_cols.items():
        if col not in df.columns:
            continue

        vals = df[col].dropna()
        if vals.empty:
            continue

        travel_range = vals.max() - vals.min()
        max_defl = vals.max()

        # iRacing suspension deflection is in meters typically
        # Check for excessive range (bottoming out risk)
        if travel_range > 0:
            # Standard deviation as indicator of harshness
            std = vals.std()
            mean = vals.mean()

            # If max deflection is very high relative to mean → bottoming risk
            if max_defl > mean + 3 * std and max_defl > 0.01:
                spring_current = setup.get(spring_key)
                spring_str = f" (current: {spring_current} N/mm)" if spring_current else ""
                recs.append(_rec(
                    "Suspension", "warning", "🟠",
                    f"{corner} suspension bottoming out risk",
                    f"Excessive deflection spikes detected (max: {max_defl*1000:.1f}mm). "
                    f"Increase spring rate or reduce bump rubber gap{spring_str}.",
                    spring_key, "increase", "+5 N/mm",
                ))

    return recs


# ── Rule 12: Differential Oversteer on Exit ─────────────────────────────
def _check_diff_oversteer(df, setup):
    recs = []
    if "YawRate" not in df.columns or "Throttle" not in df.columns:
        return recs

    steer_col = "SteeringWheelAngle" if "SteeringWheelAngle" in df.columns else None
    if steer_col is None:
        return recs

    # Look for: throttle > 50% + turning + high yaw = power oversteer
    turning = df[steer_col].abs() > 0.1  # some steering input
    throttle_on = df["Throttle"] > 0.5
    combined = turning & throttle_on

    if combined.sum() < 50:
        return recs

    yaw_during_exit = df.loc[combined, "YawRate"].abs()
    yaw_overall = df["YawRate"].abs()

    exit_yaw_ratio = yaw_during_exit.mean() / (yaw_overall.mean() + 1e-9)

    diff_current = setup.get("diff_preload")
    diff_str = f" (current preload: {diff_current} Nm)" if diff_current is not None else ""

    if exit_yaw_ratio > 1.8:
        recs.append(_rec(
            "Differential", "warning", "🟠",
            "Power oversteer on corner exit",
            f"High yaw rotation detected during throttle application in corners ({exit_yaw_ratio:.1f}× average). "
            f"Reduce differential preload{diff_str} or increase rear downforce.",
            "diff_preload", "decrease", "-5 Nm",
        ))
    elif exit_yaw_ratio > 1.4:
        recs.append(_rec(
            "Differential", "info", "🔵",
            "Slight exit oversteer tendency",
            f"Moderate yaw rotation on throttle ({exit_yaw_ratio:.1f}× average). "
            f"Consider reducing diff preload if it feels snappy{diff_str}.",
            "diff_preload", "check", "Monitor",
        ))

    return recs


# ── Rule 13: Damper Stability (Pitch/Roll rates) ────────────────────────
def _check_damper_stability(df, setup):
    recs = []

    for rate_col, axis, damper_key in [
        ("PitchRate", "pitch", "front_lsc"),
        ("RollRate", "roll", "front_lsc"),
    ]:
        if rate_col not in df.columns:
            continue

        vals = df[rate_col].dropna()
        if vals.empty:
            continue

        std = vals.std()
        # High std → car is not settled
        # Thresholds are approximate and car-dependent
        if rate_col == "PitchRate" and std > 0.08:
            lsc = setup.get("front_lsc")
            lsc_str = f" (current: {lsc} clicks)" if lsc is not None else ""
            recs.append(_rec(
                "Dampers", "info", "🔵",
                f"High {axis} oscillation (σ={std:.3f})",
                f"Car shows significant {axis} movement. "
                f"Increase low-speed compression damping{lsc_str}.",
                damper_key, "increase", "+1 click",
            ))
        elif rate_col == "RollRate" and std > 0.10:
            lsc = setup.get("front_lsc")
            lsc_str = f" (current: {lsc} clicks)" if lsc is not None else ""
            recs.append(_rec(
                "Dampers", "info", "🔵",
                f"High {axis} oscillation (σ={std:.3f})",
                f"Car shows significant body {axis}. "
                f"Increase low-speed compression damping or stiffen ARB{lsc_str}.",
                damper_key, "increase", "+1 click",
            ))

    return recs
