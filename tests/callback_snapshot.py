"""Dash callback haritasının deterministik özeti (refactor güvenlik ağı)."""
import json


def snapshot(app):
    out = {}
    for key, v in app.callback_map.items():
        out[key] = {
            "inputs": sorted(json.dumps(i, sort_keys=True) for i in v.get("inputs", [])),
            "state": sorted(json.dumps(s, sort_keys=True) for s in v.get("state", [])),
            "prevent_initial_call": bool(v.get("prevent_initial_call", False)),
            "clientside": not callable(v.get("callback")) or "clientside" in type(v.get("callback")).__name__.lower(),
        }
    return dict(sorted(out.items()))


if __name__ == "__main__":      # python -m tests.callback_snapshot > tests/golden_callbacks.json
    import app
    print(json.dumps(snapshot(app.app), indent=1, sort_keys=True))
