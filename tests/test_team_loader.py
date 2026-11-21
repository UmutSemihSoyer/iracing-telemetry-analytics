import os

from services.team_loader import (track_of, driver_of, group_by_track, team_tracks,
                                  latest_per_driver)


def touch(path, mtime):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    os.utime(path, (mtime, mtime))
    return str(path)


def test_track_of_parses_filename():
    assert track_of("porsche9922cup_sebring international 2026-03-18 00-02-28.ibt") == "sebring international"
    assert track_of("fordmustanggt3_watkinsglen 2021 fullcourse 2026-06-15 20-23-06.ibt") == "watkinsglen 2021 fullcourse"
    assert track_of("weird.ibt") == "unknown"


def test_grouping_and_latest_per_driver(tmp_path):
    a_old = touch(tmp_path / "Ali" / "Spa" / "car_spa 2026-01-01 10-00-00.ibt", 100)
    a_new = touch(tmp_path / "Ali" / "SPA" / "car_spa 2026-02-01 10-00-00.ibt", 200)
    v = touch(tmp_path / "Veli" / "car_spa 2026-01-05 10-00-00.ibt", 150)
    s = touch(tmp_path / "Ali" / "car_sebring 2026-01-05 10-00-00.ibt", 150)
    ibts = [a_old, a_new, v, s]
    g = group_by_track(ibts, str(tmp_path))
    assert driver_of(a_new, str(tmp_path)) == "Ali"
    assert set(g["spa"]) == {"Ali", "Veli"}
    assert list(team_tracks(g)) == ["spa"]            # sebring tek sürücü
    assert latest_per_driver(g, "spa") == [a_new, v]  # eşit boyutta en yeni


def test_limit(tmp_path):
    ibts = [touch(tmp_path / f"D{i}" / f"c_x 2026-01-0{i + 1} 10-00-00.ibt", 100 + i) for i in range(8)]
    g = group_by_track(ibts, str(tmp_path))
    assert len(latest_per_driver(g, "x", limit=6)) == 6


def test_picks_largest_file_not_newest(tmp_path):
    big = touch(tmp_path / "Ali" / "c_spa 2026-01-01 10-00-00.ibt", 100)
    open(big, "wb").write(b"x" * 1000)
    tiny_new = touch(tmp_path / "Ali" / "c_spa 2026-02-01 10-00-00.ibt", 200)
    g = group_by_track([big, tiny_new], str(tmp_path))
    assert latest_per_driver(g, "spa") == [big]
