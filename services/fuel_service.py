"""
Yakıt / stint / pit analizi (saf fonksiyonlar, arayüzden bağımsız).

Beklenen sütunlar: LapNumber, FuelLevel; opsiyonel: StintNumber, LapType, LapTime_s,
OnPitRoad, Speed (m/s), Time_s | Time | SessionTime.
"""
import math

import numpy as np
import pandas as pd

from services.telemetry_service import detect_stints

MIN_LAP_FUEL = 0.05    # L — bunun altı ölçüm gürültüsü
MAX_LAP_FUEL = 15.0    # L — bunun üstü dolum/hata


def _time_col(df):
    for c in ("Time_s", "Time", "SessionTime"):
        if c in df.columns:
            return c
    return None


def lap_fuel_table(df: pd.DataFrame) -> pd.DataFrame:
    """Tur başına yakıt tüketimi. Geçersiz ölçümlerde FuelUsed NaN."""
    cols = ["LapNumber", "StintNumber", "LapType", "LapTime_s", "FuelUsed", "FuelStart", "FuelEnd"]
    if "FuelLevel" not in df.columns or "LapNumber" not in df.columns:
        return pd.DataFrame(columns=cols)
    df = detect_stints(df)
    rows = []
    for ln, g in df.groupby("LapNumber"):
        fv = g["FuelLevel"].dropna()
        if fv.empty:
            continue
        used = float(fv.iloc[0] - fv.iloc[-1])
        rows.append({
            "LapNumber": int(ln),
            "StintNumber": int(g["StintNumber"].iloc[0]),
            "LapType": g["LapType"].iloc[0] if "LapType" in g.columns else "Unknown",
            "LapTime_s": float(g["LapTime_s"].iloc[0]) if "LapTime_s" in g.columns else float("nan"),
            "FuelUsed": used if MIN_LAP_FUEL < used < MAX_LAP_FUEL else float("nan"),
            "FuelStart": float(fv.iloc[0]),
            "FuelEnd": float(fv.iloc[-1]),
        })
    return pd.DataFrame(rows, columns=cols)


def stint_summary(df: pd.DataFrame, tank_capacity: float = None) -> pd.DataFrame:
    """Stint başına özet. Tüketim/tempo yalnızca Flying turlardan hesaplanır."""
    lf = lap_fuel_table(df)
    if lf.empty:
        return pd.DataFrame()
    rows = []
    for st, g in lf.groupby("StintNumber"):
        fly = g[(g["LapType"] == "Flying") & g["FuelUsed"].notna()]
        avg_f = float(fly["FuelUsed"].mean()) if not fly.empty else float("nan")
        times = fly["LapTime_s"][fly["LapTime_s"] > 0]
        row = {
            "Stint": int(st),
            "Laps": int(len(g)),
            "FirstLap": int(g["LapNumber"].min()),
            "LastLap": int(g["LapNumber"].max()),
            "FuelStart": round(float(g["FuelStart"].iloc[0]), 2),
            "FuelEnd": round(float(g["FuelEnd"].iloc[-1]), 2),
            "AvgFuelPerLap": round(avg_f, 3) if not math.isnan(avg_f) else float("nan"),
            "AvgLapTime_s": round(float(times.mean()), 3) if not times.empty else float("nan"),
            "BestLapTime_s": round(float(times.min()), 3) if not times.empty else float("nan"),
        }
        full = tank_capacity if tank_capacity else row["FuelStart"]
        row["MaxLapsOnFuel"] = round(full / avg_f, 1) if avg_f and not math.isnan(avg_f) else float("nan")
        rows.append(row)
    return pd.DataFrame(rows)


def pit_stops(df: pd.DataFrame, hz: float = 60.0) -> pd.DataFrame:
    """
    OnPitRoad ardışık bölgelerinden pit duraklarını çıkarır.
    InTime: pit yolunda toplam süre, Stationary: hız < 1 m/s süre, FuelAdded: bölge içinde yakıt artışı.
    Seans başındaki garaj çıkışı (ilk örnekten başlayan bölge) dahil edilmez.
    """
    cols = ["Stop", "EntryLap", "PitLaneTime_s", "Stationary_s", "FuelAdded"]
    if "OnPitRoad" not in df.columns:
        return pd.DataFrame(columns=cols)
    pit = (df["OnPitRoad"].fillna(0).values > 0).astype(int)
    if pit.sum() == 0:
        return pd.DataFrame(columns=cols)
    d = np.diff(np.concatenate([[0], pit, [0]]))
    starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]   # ends: ilk pit-dışı indeks
    tc = _time_col(df)
    t = df[tc].values if tc else None
    spd = df["Speed"].values if "Speed" in df.columns else None
    fuel = df["FuelLevel"].values if "FuelLevel" in df.columns else None
    rows = []
    for s, e in zip(starts, ends):
        if s == 0:
            continue
        # Seans başında garajdan çıkış: ilk turda, turun ilk yarısında başlayan bölge
        if "LapNumber" in df.columns and "LapDistPct" in df.columns:
            if df["LapNumber"].iloc[s] == df["LapNumber"].iloc[0] and df["LapDistPct"].iloc[s] < 0.5:
                continue
        sl = slice(s, e)
        dur = float(t[e - 1] - t[s]) if t is not None and e - 1 > s else (e - s) / hz
        stat = 0.0
        if spd is not None:
            step = dur / max(e - s - 1, 1)
            stat = float((spd[sl] < 1.0).sum() * step)
        added = 0.0
        if fuel is not None:
            fv = fuel[sl][~np.isnan(fuel[sl])]
            if len(fv):
                added = float(max(0.0, fv.max() - fv[0]))
        rows.append({
            "Stop": len(rows) + 1,
            "EntryLap": int(df["LapNumber"].iloc[s]) if "LapNumber" in df.columns else 0,
            "PitLaneTime_s": round(dur, 1),
            "Stationary_s": round(stat, 1),
            "FuelAdded": round(added, 2),
        })
    return pd.DataFrame(rows, columns=cols)


def pit_window(remaining_fuel: float, per_lap: float, tank_capacity: float = None,
               race_laps_left: float = None, margin_laps: float = 0.5) -> dict:
    """
    Mevcut yakıt ve tüketimden pit penceresi.
      laps_on_fuel     : margin_laps güvenlik payıyla yakıtın yeteceği tur
      pit_by_lap       : bu kadar tur içinde pite girilmeli (tam sayıya aşağı yuvarlanır)
      fuel_needed      : race_laps_left için gereken yakıt
      shortfall        : eksik yakıt
      stops_needed     : tank_capacity verilmişse gereken pit sayısı
    """
    out = {"laps_on_fuel": 0.0, "pit_by_lap": 0, "fuel_needed": None, "shortfall": None, "stops_needed": None}
    if not per_lap or per_lap <= 0 or remaining_fuel is None:
        return out
    laps = max(0.0, remaining_fuel / per_lap - margin_laps)
    out["laps_on_fuel"] = round(laps, 2)
    out["pit_by_lap"] = int(math.floor(laps))
    if race_laps_left is not None and race_laps_left >= 0:
        need = race_laps_left * per_lap + margin_laps * per_lap
        short = max(0.0, need - remaining_fuel)
        out["fuel_needed"] = round(need, 2)
        out["shortfall"] = round(short, 2)
        if tank_capacity and tank_capacity > 0:
            out["stops_needed"] = int(math.ceil(short / tank_capacity)) if short > 0 else 0
    return out
