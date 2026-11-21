"""
Refactor güvenlik ağı: app.callback_map, kaydedilmiş altın kopyayla birebir aynı olmalı.
Bilinçli bir callback değişikliğinden sonra yeniden üret:
    python -m tests.callback_snapshot > tests/golden_callbacks.json
"""
import json
from pathlib import Path

from tests.callback_snapshot import snapshot


def test_callback_map_matches_golden():
    import app
    golden = json.loads((Path(__file__).parent / "golden_callbacks.json").read_text(encoding="utf-8"))
    current = json.loads(json.dumps(snapshot(app.app)))
    assert set(current) == set(golden), (
        f"eksik: {sorted(set(golden) - set(current))} fazla: {sorted(set(current) - set(golden))}")
    for k in golden:
        assert current[k] == golden[k], f"callback değişti: {k}"


def test_layout_builds_and_has_fuel_tab():
    import app
    assert app.app.layout is not None
    assert "fuel" in str(app.app.layout)


def test_main_exports_still_available():
    import app
    assert hasattr(app, "app") and hasattr(app, "IBT_OK") and hasattr(app, "DB_PATH")
