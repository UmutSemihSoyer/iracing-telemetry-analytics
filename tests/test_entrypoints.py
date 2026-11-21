import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_electron_files_list_points_at_existing_paths():
    cfg = json.loads((ROOT / "electron" / "package.json").read_text(encoding="utf-8"))
    for pat in cfg["build"]["files"]:
        if pat.startswith("!"):
            continue
        base = pat.split("/**")[0]
        assert ((ROOT / "electron") / base).resolve().exists(), f"stale entry in electron build.files: {pat}"


def test_app_py_accepts_port_flag():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "--port" in src and "port=_args.port" in src
    r = subprocess.run([sys.executable, "-c", "import ast,sys;ast.parse(open('app.py',encoding='utf-8').read())"],
                       cwd=ROOT, capture_output=True)
    assert r.returncode == 0
