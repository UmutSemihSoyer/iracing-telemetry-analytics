"""
Gerçek .ibt duman testi. IBT_TEST_FILE ortam değişkeni ya da IBT_TEST_DIR (klasör, ilk 3 dosya)
verilmezse atlanır — CI'da çalışmaz, yerelde:

    IBT_TEST_FILE="C:/.../test2.ibt" pytest -m realdata
"""
import glob
import os

import pytest

from services.telemetry_service import load_ibt_from_path, detect_stints, predict_fuel_strategy

pytestmark = pytest.mark.realdata


def _files():
    f = os.environ.get("IBT_TEST_FILE")
    if f:
        return [f]
    d = os.environ.get("IBT_TEST_DIR")
    if d:
        return sorted(glob.glob(os.path.join(d, "**", "*.ibt"), recursive=True))[:3]
    return []


FILES = _files()


@pytest.mark.skipif(not FILES, reason="IBT_TEST_FILE / IBT_TEST_DIR tanımlı değil")
@pytest.mark.parametrize("path", FILES)
def test_pipeline_on_real_file(path):
    df, meta = load_ibt_from_path(path, downsample=2)
    assert len(df) > 0
    assert {"LapNumber", "LapType", "Micro_Sector"} <= set(df.columns)
    df = detect_stints(df)
    assert df["StintNumber"].min() >= 1
    r = predict_fuel_strategy(df)
    if r is not None:
        assert 0 < r["avg_per_lap"] < 15
        assert r["est_laps"] >= 0
