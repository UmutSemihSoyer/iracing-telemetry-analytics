import numpy as np

from core.lap_classifier import classify_laps
from services.team_service import driver_summary, sector_delta_matrix, mixed_tracks
from plotting.team import fig_sector_delta_heatmap
from ui.tabs.team import _render_team
from tests.synthetic import make_session, HZ


def two_drivers():
    a = classify_laps(make_session(n_laps=5, lap_time=60.0, driver="Fast"), HZ)
    b = classify_laps(make_session(n_laps=5, lap_time=62.0, driver="Slow"), HZ)
    for d in (a, b):
        d["TrackName"] = "spa"
    return [b, a]


def test_summary_sorted_and_gap():
    s = driver_summary(two_drivers())
    assert list(s["Driver"]) == ["Fast", "Slow"]
    assert s["Gap"].iloc[0] == 0
    assert abs(s["Gap"].iloc[1] - 2.0) < 0.2
    assert (s["Laps"] > 0).all()


def test_sector_matrix_shape_and_nonnegative():
    m = sector_delta_matrix(two_drivers())
    assert m.shape == (2, 20)
    assert (m.values >= -1e-9).all()
    assert m.loc["Fast"].sum() < m.loc["Slow"].sum()
    # toplam kayıp ~2 sn
    assert abs(m.loc["Slow"].sum() - m.loc["Fast"].sum() - 2.0) < 0.5


def test_mixed_tracks_flag():
    d = two_drivers()
    assert not mixed_tracks(d)
    d[0]["TrackName"] = "sebring"
    assert mixed_tracks(d)


def test_empty_heatmap_does_not_crash():
    assert fig_sector_delta_heatmap(sector_delta_matrix([])) is not None


def test_render_requires_two_files():
    assert "at least two" in str(_render_team(two_drivers()[:1]).children)
    assert _render_team(two_drivers()) is not None


def test_duplicate_driver_names_get_suffix():
    a, b = two_drivers()
    a["Driver"] = "Same"; b["Driver"] = "Same"
    s = driver_summary([a, b])
    assert len(set(s["Driver"])) == 2
    assert len(set(sector_delta_matrix([a, b]).index)) == 2


def test_setup_diff_only_varying_numeric():
    from services.team_service import setup_diff
    dfs = two_drivers()          # Slow, Fast
    metas = [{"auto_setup": {"fl_cold_p": 159.0, "rear_wing": 5.0, "tire_type": "Dry", "fl_hot_p": 180.0}},
             {"auto_setup": {"fl_cold_p": 159.0, "rear_wing": 7.0, "tire_type": "Dry", "fl_hot_p": 190.0}}]
    t = setup_diff(dfs, metas)
    assert list(t.index) == ["rear_wing"]          # eşit olan, metin ve sıcak basınç elendi
    assert t.loc["rear_wing", "Spread"] == 2.0


def test_setup_diff_empty_without_metas():
    from services.team_service import setup_diff
    assert setup_diff(two_drivers(), []).empty
    assert setup_diff(two_drivers(), [{}, {}]).empty


def test_team_tab_with_metas_renders():
    metas = [{"auto_setup": {"rear_wing": 5.0}}, {"auto_setup": {"rear_wing": 7.0}}]
    assert _render_team(two_drivers(), "dark", metas) is not None
