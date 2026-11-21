import numpy as np
import pandas as pd

from core.lap_classifier import classify_laps
from services.pace_model import pace_dataset, fit_pace_model, predict_laps, stint_time
from plotting.fuel import fig_pace_model
from tests.synthetic import make_session, HZ


def session(n_laps=14, pit_laps=(7,), refuel_to=60.0, deg=0.05):
    """Her tur süresi: 60 + deg*stint_turu (sn). make_session tur süresini sabit üretir,
    bu yüzden lap_time'ı tur tur değiştirip birleştiriyoruz."""
    frames, t0, fuel = [], 0.0, 60.0
    age = 0
    for lap in range(1, n_laps + 1):
        lt = 60.0 + deg * age
        one = make_session(n_laps=1, lap_time=lt, fuel_start=fuel, per_lap=2.0,
                           pit_laps=(1,) if lap in pit_laps else ())
        one["LapNumber"] = lap
        one["Time"] = one["Time"] + t0
        t0 = float(one["Time"].iloc[-1]) + 1 / HZ
        fuel = float(one["FuelLevel"].iloc[-1]) - 0.05
        age += 1
        if lap in pit_laps:
            fuel, age = refuel_to, 0
        frames.append(one)
    return classify_laps(pd.concat(frames, ignore_index=True), HZ)


def test_dataset_has_age_per_stint():
    d = pace_dataset(session())
    assert not d.empty and d.groupby("StintNumber")["Age"].min().eq(0).all()


def test_degradation_recovered_when_collinear():
    m = fit_pace_model(session(deg=0.05))
    assert m is not None
    # iki stint, aynı yakıt profili → yakıt ve yaş ayrıştırılamaz, net trend ≈ 0.05 sn/tur
    assert not m["separable"] and m["deg_s_per_lap"] is None
    assert abs(m["trend_s_per_lap"] - 0.05) < 0.01
    assert m["quality"] == "good"


def test_noise_gives_weak_quality():
    rng = np.random.default_rng(1)
    df = session(deg=0.0)
    df["LapTime_s"] = df.groupby("LapNumber")["LapTime_s"].transform(lambda s: s + rng.normal(0, 0.8))
    m = fit_pace_model(df)
    assert m is None or m["quality"] == "weak"


def test_too_few_laps_returns_none():
    assert fit_pace_model(session(n_laps=4, pit_laps=())) is None


def test_prediction_monotonic_with_positive_trend():
    m = fit_pace_model(session(deg=0.08))
    p = predict_laps(m, 60.0, 2.0, 10)
    assert len(p) == 10 and stint_time(m, 60.0, 2.0, 10) == sum(p)


def test_figure_graceful_when_not_enough_data():
    fig = fig_pace_model(session(n_laps=3, pit_laps=()))
    assert fig.layout.annotations


def test_tab_renders_with_pace_card():
    from ui.tabs.fuel import _render_fuel
    assert _render_fuel([session()], None, "dark") is not None
