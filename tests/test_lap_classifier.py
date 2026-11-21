import numpy as np
import pytest

from core.lap_classifier import (classify_laps, filter_flying_laps, lap_summary,
                                 flying_lap_times, _fmt, FLYING, OUTLAP, INLAP, DNF,
                                 ACTIVE_RESET)
from tests.synthetic import make_session, HZ


def types(df):
    return df.groupby("LapNumber")["LapType"].first().to_dict()


def test_clean_session_all_flying():
    df = classify_laps(make_session(n_laps=5), HZ)
    assert set(types(df).values()) == {FLYING}
    assert (df["LapTime_s"] > 0).all()


def test_missing_lapnumber_gives_unknown():
    df = make_session().drop(columns=["LapNumber"])
    out = classify_laps(df, HZ)
    assert (out["LapType"] == "Unknown").all()


def test_pit_laps_are_inlap_and_outlap():
    # tur 3'ün sonunda pite girilir, tur 4'ün başında çıkılır
    df = classify_laps(make_session(n_laps=6, pit_laps=(3,)), HZ)
    t = types(df)
    assert t[3] == INLAP
    assert t[4] == OUTLAP
    assert t[2] == FLYING and t[5] == FLYING


def test_dnf_lap_detected():
    df = make_session(n_laps=4)
    # tur 2'nin ikinci yarısını kes
    drop = df[(df.LapNumber == 2) & (df.LapDistPct > 0.5)].index
    df = df.drop(drop).reset_index(drop=True)
    assert types(classify_laps(df, HZ))[2] == DNF


def test_active_reset_detected():
    df = make_session(n_laps=4)
    idx = df[(df.LapNumber == 3)].index
    df.loc[idx[len(idx) // 2:], "LapDistPct"] = (
        df.loc[idx[len(idx) // 2:], "LapDistPct"] + 0.3).clip(upper=0.999)
    assert types(classify_laps(df, HZ))[3] == ACTIVE_RESET


def test_slow_mid_session_lap_flagged_safety_car():
    df = make_session(n_laps=6, lap_time=60.0)
    # tur 4'ü 2x uzat: Time'ı gererek ve hızı düşürerek
    m = df.LapNumber == 4
    start = df.loc[m, "Time"].iloc[0]
    df.loc[m, "Time"] = start + (df.loc[m, "Time"] - start) * 2.0
    df.loc[m, "Speed"] = 20.0
    shift = df.loc[m, "Time"].iloc[-1] - df.loc[df.LapNumber == 5, "Time"].iloc[0] + 1 / HZ
    df.loc[df.LapNumber > 4, "Time"] += shift
    assert types(classify_laps(df, HZ))[4] == "Safety Car"


def test_filter_flying_excludes_pit_laps():
    df = classify_laps(make_session(n_laps=6, pit_laps=(3,)), HZ)
    fl = filter_flying_laps(df)
    assert set(fl.LapNumber.unique()) == {1, 2, 5, 6}


def test_lap_summary_and_ranking():
    df = make_session(n_laps=4)
    # tur 3'ü 1 sn hızlandır: örnekleri seyrelt yerine LapLastLapTime kullan
    df["LapLastLapTime"] = 0.0
    for lap, lt in {1: 60.5, 2: 60.2, 3: 59.4}.items():
        df.loc[df.LapNumber == lap + 1, "LapLastLapTime"] = lt
    out = flying_lap_times(classify_laps(df, HZ), HZ)
    assert list(out.LapNumber)[0] == 3          # en hızlı tur başta
    assert out.Gap.iloc[0] == "REF"
    assert out.Gap.iloc[1].startswith("+")
    assert out.Rank.tolist() == sorted(out.Rank.tolist())


def test_lap_summary_columns():
    s = lap_summary(make_session(n_laps=3), HZ)
    for c in ["Driver", "LapNumber", "LapType", "LapTime_s", "LapTime_str", "FuelUsed"]:
        assert c in s.columns
    assert s.LapNumber.tolist() == [1, 2, 3]


@pytest.mark.parametrize("sec,expected", [
    (135.619, "2:15.619"), (59.4, "0:59.400"), (0, "--:--.---"),
    (float("nan"), "--:--.---"), (float("inf"), "--:--.---"),
])
def test_fmt(sec, expected):
    assert _fmt(sec) == expected
