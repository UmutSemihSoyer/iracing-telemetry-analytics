import numpy as np

from core.lap_classifier import classify_laps
from services.lap_anomalies import lap_anomalies
from tests.synthetic import make_session, HZ


def base(n=10):
    df = make_session(n_laps=n, lap_time=60.0)
    rng = np.random.default_rng(0)
    # tur sürelerini hafif oynat: Time sütununu tur başına ölçekle
    out = []
    t0 = 0.0
    for ln, g in df.groupby("LapNumber"):
        g = g.copy()
        scale = 1 + rng.normal(0, 0.002)
        g["Time"] = t0 + (g["Time"] - g["Time"].iloc[0]) * scale
        t0 = g["Time"].iloc[-1] + 1 / HZ
        out.append(g)
    import pandas as pd
    return pd.concat(out, ignore_index=True)


def test_clean_session_has_no_anomalies():
    assert lap_anomalies(classify_laps(base(), HZ)).empty


def test_slow_lap_flagged():
    import pandas as pd
    df = base(10)
    g = df[df.LapNumber == 5]
    df.loc[g.index, "Time"] = g["Time"].iloc[0] + (g["Time"] - g["Time"].iloc[0]) * 1.10
    shift = df.loc[g.index, "Time"].iloc[-1] - g["Time"].iloc[-1]
    df.loc[df.LapNumber > 5, "Time"] += shift
    a = lap_anomalies(classify_laps(df, HZ))
    assert 5 in set(a["LapNumber"]) and a.loc[a.LapNumber == 5, "Reason"].str.contains("slow").all()


def test_mid_lap_stop_flagged():
    df = base(10)
    idx = df[(df.LapNumber == 4) & (df.LapDistPct.between(0.40, 0.42))].index
    df.loc[idx, "Speed"] = 0.5
    a = lap_anomalies(classify_laps(df, HZ))
    assert 4 in set(a["LapNumber"])
    assert a.loc[a.LapNumber == 4, "Reason"].str.contains("stopped").any()


def test_too_few_laps_empty():
    assert lap_anomalies(classify_laps(make_session(n_laps=3), HZ)).empty
