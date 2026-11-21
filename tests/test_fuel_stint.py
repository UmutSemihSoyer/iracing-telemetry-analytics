import pytest

from core.lap_classifier import classify_laps
from services.telemetry_service import detect_stints, predict_fuel_strategy
from tests.synthetic import make_session, HZ


def stints(df):
    return df.groupby("LapNumber")["StintNumber"].first().astype(int).to_dict()


def test_no_pit_single_stint():
    df = detect_stints(make_session(n_laps=6))
    assert set(stints(df).values()) == {1}


def test_pit_stop_splits_stints_once():
    # tur 3 sonu pit + yakıt dolumu -> 4. tur yeni stint
    df = detect_stints(make_session(n_laps=8, pit_laps=(3,), refuel_to=50.0))
    assert stints(df) == {1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 2, 7: 2, 8: 2}


def test_two_pit_stops_three_stints():
    df = detect_stints(make_session(n_laps=10, pit_laps=(3, 7), refuel_to=50.0))
    s = stints(df)
    assert s[3] == 1 and s[4] == 2 and s[7] == 2 and s[8] == 3
    assert max(s.values()) == 3


def test_refuel_without_pit_channel_still_detected():
    df = make_session(n_laps=8, pit_laps=(3,), refuel_to=50.0).drop(columns=["OnPitRoad"])
    s = stints(detect_stints(df))
    assert s[3] == 1 and s[4] == 2 and max(s.values()) == 2


def test_existing_stint_column_is_preserved():
    df = make_session(n_laps=3)
    df["StintNumber"] = 7
    assert (detect_stints(df)["StintNumber"] == 7).all()


def test_fuel_strategy_none_without_fuel():
    assert predict_fuel_strategy(make_session().drop(columns=["FuelLevel"])) is None


def test_fuel_strategy_values():
    df = classify_laps(make_session(n_laps=8, per_lap=2.5, fuel_start=50.0), HZ)
    r = predict_fuel_strategy(df, HZ)
    assert r["avg_per_lap"] == pytest.approx(2.5, rel=0.02)
    assert r["recent_avg"] == pytest.approx(2.5, rel=0.02)
    assert r["stint_count"] == 1
    # kalan yakıt / tüketim - 0.5 tur güvenlik payı
    assert r["est_laps"] == pytest.approx(r["remaining"] / r["recent_avg"] - 0.5, rel=1e-6)
    assert r["total_used"] == pytest.approx(50.0 - r["remaining"])


def test_fuel_strategy_ignores_pit_laps():
    # pit turlarında yakıt dolumu tüketimi bozmamalı
    df = classify_laps(make_session(n_laps=10, pit_laps=(4,), refuel_to=50.0, per_lap=2.5), HZ)
    r = predict_fuel_strategy(df, HZ)
    assert r["avg_per_lap"] == pytest.approx(2.5, rel=0.02)
    assert r["stint_count"] == 2


def test_fuel_strategy_uses_current_stint_for_recent_avg():
    a = make_session(n_laps=4, per_lap=2.0, fuel_start=50.0)
    b = make_session(n_laps=4, per_lap=3.0, fuel_start=50.0)
    b["LapNumber"] += 4
    b["Time"] += a["Time"].iloc[-1] + 1
    import pandas as pd
    df = pd.concat([a, b], ignore_index=True)
    df["StintNumber"] = (df.LapNumber > 4).astype(int) + 1
    df = classify_laps(df, HZ)
    r = predict_fuel_strategy(df, HZ)
    assert r["recent_avg"] == pytest.approx(3.0, rel=0.03)
    assert r["avg_per_lap"] < r["recent_avg"]
