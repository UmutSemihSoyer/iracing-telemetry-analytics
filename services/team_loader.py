"""Takım klasöründen (<kök>/<sürücü>/.../*.ibt) pist bazlı toplu seçim."""
from __future__ import annotations

import os
import re
from pathlib import Path

_TRACK_RE = re.compile(r"^[^_]+_(?P<track>.+?)\s+\d{4}-\d{2}-\d{2}")


def track_of(path: str) -> str:
    """iRacing dosya adından pist: '<araba>_<pist> <tarih> <saat>.ibt'. Bulunamazsa 'unknown'."""
    m = _TRACK_RE.match(Path(path).stem)
    return m.group("track").strip().lower() if m else "unknown"


def driver_of(path: str, root: str) -> str:
    """Kök altındaki ilk klasör adı (sürücü). Kök dışında/dosya doğrudan kökteyse üst klasör."""
    try:
        rel = Path(path).resolve().relative_to(Path(root).resolve())
        if len(rel.parts) > 1:
            return rel.parts[0]
    except ValueError:
        pass
    return Path(path).parent.name


def group_by_track(ibts: list, root: str) -> dict:
    """{pist: {sürücü: [dosyalar, yeni → eski]}}"""
    out: dict = {}
    for p in sorted(ibts, key=lambda x: os.path.getmtime(x), reverse=True):
        out.setdefault(track_of(p), {}).setdefault(driver_of(p, root), []).append(p)
    return out


def team_tracks(groups: dict, min_drivers: int = 2) -> dict:
    """Birden çok sürücünün sürdüğü pistler, sürücü sayısına göre azalan."""
    t = {k: v for k, v in groups.items() if len(v) >= min_drivers}
    return dict(sorted(t.items(), key=lambda kv: (-len(kv[1]), kv[0])))


def latest_per_driver(groups: dict, track: str, limit: int = 6) -> list:
    """Seçilen pist için her sürücünün en büyük dosyası (en çok tur; eşitlikte en yeni).

    `groups` dosyaları yeni → eski sıralı tutar, max() eşitlikte ilkini (en yeniyi) seçer.
    Ad geçmişten kaldı: en yeni değil en dolu dosya seçilir (kısa/boş kayıtları atlamak için).
    """
    drivers = groups.get(track, {})
    return [max(files, key=os.path.getsize) for _, files in sorted(drivers.items())][:limit]
