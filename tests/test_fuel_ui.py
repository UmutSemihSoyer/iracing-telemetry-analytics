import json

import plotly.graph_objects as go
from dash.development.base_component import Component

from core.lap_classifier import classify_laps
from plotting.fuel import fig_fuel_level, fig_fuel_per_lap, fig_stint_compare
from ui.tabs.fuel import _render_fuel, pit_window_children
from tests.synthetic import make_session, HZ


def dfs2():
    a = classify_laps(make_session(n_laps=10, pit_laps=(5,), refuel_to=50.0, driver="A"), HZ)
    b = classify_laps(make_session(n_laps=8, per_lap=2.0, driver="B"), HZ)
    return [a, b]


def test_figures_build_with_data():
    for f in (fig_fuel_level, fig_fuel_per_lap, fig_stint_compare):
        fig = f(dfs2(), "dark")
        assert isinstance(fig, go.Figure) and len(fig.data) >= 1


def test_figures_graceful_without_fuel():
    d = [make_session().drop(columns=["FuelLevel"])]
    for f in (fig_fuel_level, fig_fuel_per_lap, fig_stint_compare):
        assert isinstance(f(d, "dark"), go.Figure)


def test_render_fuel_is_serializable():
    out = _render_fuel(dfs2(), [], "dark")
    assert isinstance(out, Component)
    json.dumps(out, default=lambda o: o.to_plotly_json() if hasattr(o, "to_plotly_json") else str(o))


def test_render_fuel_no_data_and_no_channel():
    assert "No data" in _render_fuel([], [], "dark").children
    assert "FuelLevel" in _render_fuel([make_session().drop(columns=["FuelLevel"])], [], "dark").children


def test_pit_window_children_texts():
    d = [classify_laps(make_session(n_laps=8, per_lap=2.5), HZ)]
    txt = str(pit_window_children(d, 50.0, 30, "dark").to_plotly_json())
    assert "Stops needed" in txt and "Laps on fuel" in txt
