"""Tur bazlı anomali tespiti: yavaş tur (robust z-skor) ve tur ortası durma/spin.

Not: Bu, setup metriklerini geçmişle karşılaştıran core/anomaly_detector.py'den ayrıdır.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from services.telemetry_service import lap_times

Z_LIMIT = 3.5            # modifiye z-skor eşiği (Iglewicz–Hoaglin)
MIN_SLOWER = 1.02        # medyanın en az %2 üstü olmalı (çok tutarlı sürücülerde sahte alarm olmasın)
STOP_SPEED = 3.0         # m/s altı = durma/spin
MIN_LAPS = 5
COLS = ["LapNumber", "LapTime_s", "Reason"]


def lap_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """Uçuş turları içinde yavaş veya tur ortasında duran turları listeler."""
    lt = lap_times(df, flying_only=True)
    if lt.empty or len(lt) < MIN_LAPS:
        return pd.DataFrame(columns=COLS)
    times = lt.set_index("LapNumber")["Time_s"].astype(float)
    med = float(times.median())
    mad = float((times - med).abs().median())
    reasons: dict = {}

    if mad > 0:
        z = 0.6745 * (times - med) / mad
        for ln in times.index[(z > Z_LIMIT) & (times > med * MIN_SLOWER)]:
            reasons.setdefault(int(ln), []).append(f"slow (+{times[ln] - med:.2f} s vs median)")

    if "Speed" in df.columns and "LapDistPct" in df.columns:
        mid = df[(df["LapDistPct"] > 0.02) & (df["LapDistPct"] < 0.98)]
        if "OnPitRoad" in mid.columns:
            mid = mid[mid["OnPitRoad"] == 0]
        slow = mid[mid["Speed"] < STOP_SPEED]
        for ln in slow["LapNumber"].unique():
            if int(ln) in times.index:
                reasons.setdefault(int(ln), []).append("stopped / spun mid-lap")

    rows = [{"LapNumber": ln, "LapTime_s": float(times[ln]), "Reason": "; ".join(r)}
            for ln, r in sorted(reasons.items())]
    return pd.DataFrame(rows, columns=COLS)
