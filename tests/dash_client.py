"""Tarayıcısız Dash callback çağrısı: Flask test client ile /_dash-update-component."""
import json


def find_key(app, input_id, input_prop, output_id):
    for k, v in app.callback_map.items():
        ins = {(i["id"], i["property"]) for i in v.get("inputs", [])}
        if (input_id, input_prop) in ins and k.startswith(output_id + "."):
            return k
    raise KeyError((input_id, input_prop, output_id))


def call(app, key, values=None, states=None):
    """values/states: {'component-id.property': value}; eksikler None gider."""
    meta = app.callback_map[key]
    values, states = values or {}, states or {}
    body = {
        "output": key,
        "outputs": _outputs(key),
        "inputs": [{**i, "value": values.get(f"{i['id']}.{i['property']}")} for i in meta["inputs"]],
        "state": [{**s, "value": states.get(f"{s['id']}.{s['property']}")} for s in meta.get("state", [])],
        "changedPropIds": [f"{i['id']}.{i['property']}" for i in meta["inputs"] if f"{i['id']}.{i['property']}" in values],
    }
    r = app.server.test_client().post("/_dash-update-component", json=body)
    return r.status_code, r.get_json(silent=True), r.get_data(as_text=True)


def _outputs(key):
    parts = [p for p in key.strip(".").split("...")]
    outs = []
    for p in parts:
        cid, prop = p.rsplit(".", 1)
        outs.append({"id": cid, "property": prop})
    return outs[0] if len(outs) == 1 else outs
