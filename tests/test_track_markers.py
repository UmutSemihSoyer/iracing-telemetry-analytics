import numpy as np
import pandas as pd

from services.track_markers import corner_markers
from plotting.gps_maps import fig_apex_brake_map
from tests.synthetic import HZ


def corner_lap(n_laps=3, lap_time=40.0, hz=HZ):
    """Düz + tek viraj: 0.40-0.50 arası direksiyon, 0.33'te fren, apex ~0.45."""
    n = int(lap_time * hz)
    rows = []
    for lap in range(1, n_laps + 1):
        pct = np.linspace(0.0, 0.999, n)
        steer = np.where((pct > 0.40) & (pct < 0.50), 0.5, 0.0)
        speed = 70 - 40 * np.exp(-((pct - 0.45) / 0.04) ** 2)
        brake = np.where((pct > 0.33) & (pct < 0.42), 0.8, 0.0)
        ang = 2 * np.pi * pct
        rows.append(pd.DataFrame({
            "LapNumber": lap, "LapDistPct": pct, "Time": (lap - 1) * lap_time + np.arange(n) / hz,
            "LapTime_s": lap_time, "Speed": speed, "Brake": brake, "SteeringWheelAngle": steer,
            "Lat": 40 + 0.01 * np.sin(ang), "Lon": 32 + 0.01 * np.cos(ang),
            "LapType": "Flying",
        }))
    return pd.concat(rows, ignore_index=True)


def test_corner_has_apex_and_brake_point():
    marks = corner_markers(corner_lap())
    assert len(marks) == 1
    m = marks[0]
    assert 0.42 < m["apex_pct"] < 0.48
    assert m["apex_speed"] < 35
    assert 0.32 < m["brake_pct"] < 0.35          # frenin başladığı yer
    assert m["brake_pct"] < m["apex_pct"]


def test_no_brake_channel_still_gives_apex():
    marks = corner_markers(corner_lap().drop(columns=["Brake"]))
    assert marks and marks[0]["brake_lat"] is None


def test_missing_gps_returns_empty():
    assert corner_markers(corner_lap().drop(columns=["Lat", "Lon"])) == []


def test_figure_has_apex_and_brake_traces():
    fig = fig_apex_brake_map(corner_lap())
    names = {tr.name for tr in fig.data}
    assert {"Apex", "Brake point"} <= names


def test_figure_graceful_without_gps():
    fig = fig_apex_brake_map(corner_lap().drop(columns=["Lat", "Lon"]))
    assert fig.layout.annotations
