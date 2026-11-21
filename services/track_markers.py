"""Apex ve fren noktası işaretleri (en iyi tur üzerinden)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.corner_detector import detect_corners
from services.telemetry_service import best_lap_df

BRAKE_ON = 0.10        # fren pedalı bu değerin üstü = frende
LOOKBACK = 180         # viraj başlangıcından geriye bakılacak örnek sayısı (~3 sn @60Hz)


def corner_markers(df: pd.DataFrame) -> list[dict]:
    """Her viraj için apex (min hız) ve fren başlangıç noktasını döndürür.

    Dönen sözlük: corner, direction, apex_lat/lon/speed/pct,
    brake_lat/lon/pct (fren yoksa None).
    """
    lap = best_lap_df(df)
    if lap is None or len(lap) < 50:
        return []
    lap = lap.reset_index(drop=True)
    need = {"Speed", "Lat", "Lon", "LapDistPct"}
    if not need.issubset(lap.columns):
        return []

    brake = lap["Brake"].to_numpy(dtype=float) if "Brake" in lap.columns else None
    speed = lap["Speed"].to_numpy(dtype=float)
    out = []
    for n, c in enumerate(detect_corners(lap), start=1):
        s, e = int(c["start_idx"]), int(c["end_idx"])
        if e <= s:
            continue
        apex = s + int(np.argmin(speed[s:e + 1]))
        item = {
            "corner": n, "direction": c["direction"],
            "apex_lat": float(lap.at[apex, "Lat"]), "apex_lon": float(lap.at[apex, "Lon"]),
            "apex_speed": float(speed[apex]), "apex_pct": float(lap.at[apex, "LapDistPct"]),
            "brake_lat": None, "brake_lon": None, "brake_pct": None,
        }
        if brake is not None:
            lo = max(0, s - LOOKBACK)
            braking = brake[lo:apex + 1] > BRAKE_ON
            if braking.any():
                # apex'e en yakın kesintisiz fren bölgesinin başlangıcı
                j = len(braking) - 1 - int(np.argmax(braking[::-1]))   # son frenli örnek
                while j > 0 and braking[j - 1]:
                    j -= 1
                bi = lo + j
                item.update(brake_lat=float(lap.at[bi, "Lat"]),
                            brake_lon=float(lap.at[bi, "Lon"]),
                            brake_pct=float(lap.at[bi, "LapDistPct"]))
        out.append(item)
    return out
