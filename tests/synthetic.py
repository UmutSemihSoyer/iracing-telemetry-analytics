"""Sentetik telemetri üreticisi — gerçek .ibt dosyası olmadan test yazmak için."""
import numpy as np
import pandas as pd

HZ = 20  # test hızını düşük tutmak için


def make_session(n_laps=6, lap_time=60.0, hz=HZ, fuel_start=50.0, per_lap=2.5,
                 pit_laps=(), refuel_to=None, speed=50.0, driver="Test"):
    """
    n_laps       : tur sayısı (LapNumber 1..n_laps)
    pit_laps     : OnPitRoad=1 olan tur numaraları (tüm tur boyunca değil, turun sonu/başı)
    refuel_to    : pit_laps'in ardından yakıtın doldurulacağı seviye (None = doldurma yok)
    """
    n = int(lap_time * hz)
    rows = []
    fuel = fuel_start
    t0 = 0.0
    for lap in range(1, n_laps + 1):
        pct = np.linspace(0.0, 0.999, n)
        t = t0 + np.arange(n) / hz
        f = fuel - per_lap * np.arange(n) / n
        pit = np.zeros(n, dtype=int)
        if lap in pit_laps:
            pit[-int(n * 0.1):] = 1          # turun sonunda pite giriş
        if (lap - 1) in pit_laps:
            pit[: int(n * 0.1)] = 1          # sonraki turun başında pitten çıkış
        rows.append(pd.DataFrame({
            "LapNumber": lap, "LapDistPct": pct, "Time": t,
            "Speed": speed, "FuelLevel": f, "OnPitRoad": pit, "Driver": driver,
        }))
        fuel = f[-1] - per_lap / n
        if lap in pit_laps and refuel_to is not None:
            fuel = refuel_to
        t0 = t[-1] + 1 / hz
    return pd.concat(rows, ignore_index=True)
