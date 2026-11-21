"""Çoklu sürücü / takım karşılaştırması (aynı pist için yüklenmiş birden çok dosya)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from services.telemetry_service import best_lap_df, lap_times

N_BINS = 20


def _label(df: pd.DataFrame, i: int) -> str:
    d = str(df["Driver"].iloc[0]) if "Driver" in df.columns and len(df) else ""
    return d or f"File {i + 1}"


def _labels(dfs: list) -> list:
    """Aynı sürücünün birden çok dosyası olabilir: tekrarlayanlara #n eki ekle."""
    base = [_label(d, i) for i, d in enumerate(dfs)]
    seen, out = {}, []
    for b in base:
        seen[b] = seen.get(b, 0) + 1
        out.append(b if base.count(b) == 1 else f"{b} #{seen[b]}")
    return out


def _time_col(df):
    return next((c for c in ("Time_s", "Time") if c in df.columns), None)


def driver_summary(dfs: list) -> pd.DataFrame:
    """Dosya başına: Driver, Track, Laps, Best, Median, Std, Gap, Fuel/lap, TopSpeed."""
    rows = []
    labels = _labels(dfs)
    for i, df in enumerate(dfs):
        lt = lap_times(df, flying_only=True)
        times = lt["Time_s"].to_numpy(dtype=float) if not lt.empty else np.array([])
        fuel = np.nan
        if "FuelLevel" in df.columns and "LapNumber" in df.columns and len(times):
            f = df[df["LapNumber"].isin(lt["LapNumber"])].groupby("LapNumber")["FuelLevel"].agg(["first", "last"])
            use = (f["first"] - f["last"]).clip(lower=0)
            fuel = float(use.median()) if len(use) else np.nan
        rows.append({
            "Driver": labels[i],
            "Track": str(df["TrackName"].iloc[0]) if "TrackName" in df.columns and len(df) else "",
            "Laps": int(len(times)),
            "Best": float(times.min()) if len(times) else np.nan,
            "Median": float(np.median(times)) if len(times) else np.nan,
            "Std": float(times.std()) if len(times) > 1 else np.nan,
            "Fuel/lap": fuel,
            "Top km/h": float(df["Speed"].max() * 3.6) if "Speed" in df.columns else np.nan,
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["Gap"] = out["Best"] - out["Best"].min()
    return out.sort_values("Best", na_position="last").reset_index(drop=True)


def mixed_tracks(dfs: list) -> bool:
    tracks = {str(d["TrackName"].iloc[0]) for d in dfs if "TrackName" in d.columns and len(d)}
    return len(tracks) > 1


def sector_delta_matrix(dfs: list, n_bins: int = N_BINS) -> pd.DataFrame:
    """Satır = sürücü, sütun = pist dilimi (S01..); değer = en iyi turda o dilimde
    kaybedilen süre (sn), her dilimin en hızlı sürücüsüne göre (0 = en hızlı)."""
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    cols = [f"S{i + 1:02d}" for i in range(n_bins)]
    data, names = [], []
    labels = _labels(dfs)
    for i, df in enumerate(dfs):
        lap = best_lap_df(df)
        tc = _time_col(lap)
        if tc is None or "LapDistPct" not in lap.columns or len(lap) < 20:
            continue
        lap = lap.sort_values("LapDistPct").drop_duplicates("LapDistPct")
        t = lap[tc].to_numpy(dtype=float)
        cum = np.interp(edges, lap["LapDistPct"].to_numpy(dtype=float), t - t[0])
        data.append(np.diff(cum))
        names.append(labels[i])
    if not data:
        return pd.DataFrame(columns=cols)
    m = pd.DataFrame(data, index=names, columns=cols)
    return m - m.min(axis=0)
