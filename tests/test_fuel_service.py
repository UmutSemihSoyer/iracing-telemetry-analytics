import math

import pytest

from core.lap_classifier import classify_laps
from services.fuel_service import lap_fuel_table, stint_summary, pit_stops, pit_window
from tests.synthetic import make_session, HZ


def prepared(**kw):
    return classify_laps(make_session(**kw), HZ)


def test_lap_fuel_table_values():
    t = lap_fuel_table(prepared(n_laps=5, per_lap=2.5))
    assert len(t) == 5
    assert t.FuelUsed.dropna().mean() == pytest.approx(2.5, rel=0.02)


def test_lap_fuel_table_nan_on_refuel_lap():
    df = prepared(n_laps=6, pit_laps=(3,), refuel_to=50.0, per_lap=2.5)
    t = lap_fuel_table(df).set_index("LapNumber")
    assert not math.isnan(t.loc[2, "FuelUsed"])


def test_lap_fuel_table_missing_columns():
    assert lap_fuel_table(make_session().drop(columns=["FuelLevel"])).empty


def test_stint_summary_two_stints():
    df = prepared(n_laps=10, pit_laps=(5,), refuel_to=50.0, per_lap=2.5)
    s = stint_summary(df)
    assert list(s.Stint) == [1, 2]
    assert s.AvgFuelPerLap.iloc[0] == pytest.approx(2.5, rel=0.03)
    assert s.Laps.sum() == 10
    assert s.MaxLapsOnFuel.iloc[0] == pytest.approx(50 / 2.5, rel=0.05)


def test_stint_summary_uses_tank_capacity():
    s = stint_summary(prepared(n_laps=6, per_lap=2.0), tank_capacity=100.0)
    assert s.MaxLapsOnFuel.iloc[0] == pytest.approx(50.0, rel=0.05)


def test_pit_stops_detected_with_fuel_added():
    df = prepared(n_laps=8, pit_laps=(3,), refuel_to=50.0)
    p = pit_stops(df, HZ)
    assert len(p) == 1
    assert p.EntryLap.iloc[0] == 3
    assert p.PitLaneTime_s.iloc[0] > 0
    assert p.FuelAdded.iloc[0] > 0


def test_pit_stops_ignores_garage_exit_and_missing_channel():
    df = make_session(n_laps=3)
    df.loc[:20, "OnPitRoad"] = 1               # seans başı: garajdan çıkış
    assert pit_stops(df, HZ).empty
    assert pit_stops(df.drop(columns=["OnPitRoad"]), HZ).empty


def test_pit_window_basic():
    w = pit_window(remaining_fuel=20.0, per_lap=2.5)
    assert w["laps_on_fuel"] == pytest.approx(7.5)
    assert w["pit_by_lap"] == 7


def test_pit_window_race_distance_and_stops():
    w = pit_window(20.0, 2.5, tank_capacity=50.0, race_laps_left=40)
    assert w["fuel_needed"] == pytest.approx(40 * 2.5 + 1.25)
    assert w["shortfall"] == pytest.approx(w["fuel_needed"] - 20.0)
    assert w["stops_needed"] == 2


def test_pit_window_no_stop_needed():
    w = pit_window(50.0, 2.0, tank_capacity=60.0, race_laps_left=10)
    assert w["shortfall"] == 0 and w["stops_needed"] == 0


def test_pit_window_invalid_consumption():
    assert pit_window(10.0, 0)["laps_on_fuel"] == 0.0
    assert pit_window(None, 2.0)["pit_by_lap"] == 0


def test_pit_stops_ignores_garage_exit_not_at_index_zero():
    df = make_session(n_laps=3)
    df.loc[40:80, "OnPitRoad"] = 1             # ilk turda, LapDistPct < 0.5
    assert pit_stops(df, HZ).empty
