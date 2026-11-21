"""Tur süresi modeli: süre = taban + yakıt etkisi × yakıt + lastik etkisi × stint turu.

Aynı stint içinde yakıt ve lastik yaşı neredeyse doğrusal bağlı (yakıt tur başına azalır),
bu yüzden ikisi ayrıştırılamazsa tek bir "net trend" (sn/tur) raporlanır ve bunu
söylüyoruz — uydurma ayrıştırma yok.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import HuberRegressor

from services.fuel_service import lap_fuel_table

MIN_LAPS = 6
OUTLIER_RATIO = 1.05      # medyanın %5 üstü = trafik/sarı/hata, modele girmez
COLLINEAR_R = 0.95


def pace_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Uçuş turları: LapNumber, StintNumber, Age (stint içi tur no, 0'dan), FuelStart, LapTime_s."""
    t = lap_fuel_table(df)
    if t.empty:
        return t
    t = t[(t["LapType"] == "Flying") & (t["LapTime_s"] > 0)].dropna(subset=["FuelStart"]).copy()
    if t.empty:
        return t
    t = t[t["LapTime_s"] <= t["LapTime_s"].median() * OUTLIER_RATIO]
    t["Age"] = t.groupby("StintNumber")["LapNumber"].transform(lambda s: s - s.min())
    return t.reset_index(drop=True)


def fit_pace_model(df: pd.DataFrame) -> dict | None:
    d = pace_dataset(df)
    if len(d) < MIN_LAPS:
        return None
    y = d["LapTime_s"].to_numpy(float)
    age = d["Age"].to_numpy(float)
    fuel = d["FuelStart"].to_numpy(float)
    if age.std() < 1e-9:
        return None
    r = abs(np.corrcoef(age, fuel)[0, 1]) if fuel.std() > 1e-9 else 1.0
    separable = bool(r < COLLINEAR_R)
    X = np.column_stack([fuel, age]) if separable else age.reshape(-1, 1)
    m = HuberRegressor(epsilon=1.35, alpha=0.0, max_iter=500).fit(X, y)
    pred = m.predict(X)
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum()) or 1e-12
    out = {"separable": separable, "n": int(len(d)), "base": float(m.intercept_),
           "r2": 1 - ss_res / ss_tot, "resid_std": float(np.std(y - pred)),
           "corr_fuel_age": float(r)}
    if separable:
        out.update(fuel_s_per_l=float(m.coef_[0]), deg_s_per_lap=float(m.coef_[1]))
    else:
        out.update(fuel_s_per_l=None, trend_s_per_lap=float(m.coef_[0]), deg_s_per_lap=None)
    out["quality"] = "good" if out["r2"] >= 0.5 else ("fair" if out["r2"] >= 0.2 else "weak")
    out["_coef"] = [float(c) for c in m.coef_]
    return out


def predict_laps(model: dict, fuel_start: float, per_lap: float, n_laps: int) -> list:
    """Yeni stint için tur süreleri (fuel_start litre ile çıkış, per_lap L/tur)."""
    ages = np.arange(n_laps, dtype=float)
    if model["separable"]:
        f = fuel_start - per_lap * ages
        t = model["base"] + model["_coef"][0] * f + model["_coef"][1] * ages
    else:
        t = model["base"] + model["_coef"][0] * ages
    return [float(x) for x in t]


def stint_time(model: dict, fuel_start: float, per_lap: float, n_laps: int) -> float:
    return float(sum(predict_laps(model, fuel_start, per_lap, n_laps)))
