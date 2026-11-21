"""Tarayıcısız uçtan uca: gerçek Dash sunucu yolundan callback çağırır."""
import app as A
from core.lap_classifier import classify_laps
from tests.dash_client import find_key, call
from tests.synthetic import make_session, HZ


def _load_session():
    df = classify_laps(make_session(n_laps=10, pit_laps=(5,), refuel_to=50.0), HZ)
    A._DATA.update({"dfs": [df], "metas": [{}], "tas": [], "mode": "dark"})


def test_layout_and_dependencies_endpoints():
    c = A.app.server.test_client()
    assert c.get("/_dash-layout").status_code == 200
    assert c.get("/_dash-dependencies").status_code == 200


def test_switch_to_fuel_tab_via_http():
    _load_session()
    key = find_key(A.app, "tabs", "value", "tab-content")
    code, js, raw = call(A.app, key, values={"tabs.value": "fuel"},
                         states={"theme-store.data": "dark"})
    assert code == 200, raw[:300]
    assert "Fuel" in raw and "Stint" in raw


def test_switch_tab_without_data_shows_hint():
    A._DATA.clear()
    key = find_key(A.app, "tabs", "value", "tab-content")
    code, js, raw = call(A.app, key, values={"tabs.value": "overview"},
                         states={"theme-store.data": "dark"})
    assert code == 200 and "No telemetry loaded" in raw


def test_pit_window_callback_via_http():
    _load_session()
    key = find_key(A.app, "fuel-tank-input", "value", "fuel-pit-window-out")
    code, js, raw = call(A.app, key, values={"fuel-tank-input.value": 50, "fuel-laps-left-input.value": 30},
                         states={"theme-store.data": "dark"})
    assert code == 200, raw[:300]
    assert "Stops needed" in raw


import os
import pytest

TABS = ["overview", "sectors", "channel_gps", "overlay", "brakes", "dynamics", "driving_style",
        "tire", "ai_engineer", "setup", "setup_advisor", "setup_delta", "database", "fuel"]


@pytest.mark.parametrize("tab", TABS)
def test_every_tab_renders_over_http(tab):
    """Her sekme sentetik veriyle HTTP üzerinden 200 dönmeli (NameError/AttributeError yakalar)."""
    _load_session()
    for col in ("Lat", "Lon"):
        A._DATA["dfs"][0][col] = 40.0 + A._DATA["dfs"][0]["LapDistPct"] * 0.01
    A._DATA["dfs"][0]["SlipAngle"] = 1.0
    key = find_key(A.app, "tabs", "value", "tab-content")
    code, js, raw = call(A.app, key, values={"tabs.value": tab, "unit-store.data": "metric"},
                         states={"theme-store.data": "dark"})
    assert code == 200, f"{tab}: {raw[:200]}"


def test_tab_with_missing_channels_shows_friendly_message():
    """Eksik kanalda sekme 500 vermemeli; okunur uyarı göstermeli."""
    _load_session()                      # sentetik veride Brake kanalı yok
    key = find_key(A.app, "tabs", "value", "tab-content")
    code, js, raw = call(A.app, key, values={"tabs.value": "brakes", "unit-store.data": "metric"},
                         states={"theme-store.data": "dark"})
    assert code == 200
    assert "could not be rendered" in raw
