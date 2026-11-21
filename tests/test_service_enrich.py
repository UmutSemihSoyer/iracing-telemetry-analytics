import numpy as np

from services.telemetry_service import _enrich, detect_laps
from tests.synthetic import make_session


def test_enrich_adds_columns():
    df = make_session(n_laps=3)
    df["Throttle"] = 1.0
    df["Brake"] = 0.0
    out = _enrich(df)
    assert {"Driver_State", "Micro_Sector", "LapType"} <= set(out.columns)
    assert (out["Driver_State"] == "Throttle").all()


def test_enrich_constant_lapdistpct_does_not_crash():
    # Regresyon: araç pitte/garajda dururken LapDistPct sabit -> pd.cut "Bin edges must be unique"
    df = make_session(n_laps=1)
    df["LapDistPct"] = 0.0224
    out = _enrich(df)
    assert "Micro_Sector" in out.columns


def test_micro_sector_uses_fixed_edges():
    df = make_session(n_laps=2)
    out = _enrich(df)
    assert out.loc[out.LapDistPct < 0.04, "Micro_Sector"].astype(str).eq("S01").all()


def test_detect_laps_from_lapdistpct_wrap():
    df = make_session(n_laps=4).drop(columns=["LapNumber", "LapType"], errors="ignore")
    out = detect_laps(df)
    assert out["LapNumber"].nunique() == 4
