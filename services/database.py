import sqlite3
import datetime
import pickle
import gzip
from pathlib import Path
import pandas as pd

DB_PATH = Path("iracing_sessions.db")
SAVED_DATA_DIR = Path("saved_sessions")
SAVED_DATA_DIR.mkdir(exist_ok=True)

def db_init():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT,
            driver      TEXT,
            track       TEXT,
            car         TEXT,
            series      TEXT,
            weather     TEXT,
            track_temp  TEXT,
            best_lap_s  REAL,
            best_lap_str TEXT,
            n_laps      INTEGER,
            file_path   TEXT,
            compound    TEXT,
            notes       TEXT,
            data_path   TEXT,
            max_speed   REAL DEFAULT 0,
            setup_rating  INTEGER DEFAULT 0,
            advisor_score INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS setups (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  INTEGER,
            -- Aerodynamics
            front_wing  REAL, rear_wing REAL,
            -- Suspension
            fl_spring   REAL, fr_spring REAL, rl_spring REAL, rr_spring REAL,
            fl_camber   REAL, fr_camber REAL, rl_camber REAL, rr_camber REAL,
            fl_toe      REAL, fr_toe    REAL, rl_toe    REAL, rr_toe    REAL,
            fl_ride_h   REAL, fr_ride_h REAL, rl_ride_h REAL, rr_ride_h REAL,
            -- Tyres
            fl_cold_p   REAL, fr_cold_p REAL, rl_cold_p REAL, rr_cold_p REAL,
            compound    TEXT,
            -- Brakes
            brake_bias  REAL,
            -- Differential
            diff_entry  REAL, diff_mid  REAL, diff_exit REAL,
            notes       TEXT,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        );
        CREATE TABLE IF NOT EXISTS annotations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  INTEGER,
            lap_number  INTEGER,
            track_pos   REAL,
            channel     TEXT,
            note        TEXT,
            created_at  TEXT,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        );
        CREATE TABLE IF NOT EXISTS session_metrics (
            session_id      INTEGER PRIMARY KEY,
            avg_tire_temp_f REAL,
            avg_tire_temp_r REAL,
            tire_temp_spread REAL,
            yaw_spike_pct   REAL,
            brake_stability REAL,
            throttle_smooth REAL,
            coasting_pct    REAL,
            max_lat_g       REAL,
            avg_speed       REAL,
            oversteer_ratio REAL,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        );
    """)
    try:
        cur.execute("ALTER TABLE sessions ADD COLUMN data_path TEXT")
        con.commit()
    except sqlite3.OperationalError: pass

    try:
        cur.execute("ALTER TABLE sessions ADD COLUMN max_speed REAL DEFAULT 0")
        con.commit()
    except sqlite3.OperationalError: pass
    # v9.1 — ML columns
    for col_def in [
        "setup_rating INTEGER DEFAULT 0",
        "advisor_score INTEGER DEFAULT 0",
    ]:
        try:
            cur.execute(f"ALTER TABLE sessions ADD COLUMN {col_def}")
            con.commit()
        except sqlite3.OperationalError:
            pass
    con.commit(); con.close()

def db_save_session(meta: dict, lt_df: pd.DataFrame,
                    compound: str = "", notes: str = "",
                    telemetry_df: pd.DataFrame = None) -> int:
    db_init()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    best_s   = lt_df["Time_s"].min()  if not lt_df.empty else 0
    best_str = lt_df.iloc[0]["Time_str"] if not lt_df.empty else ""
    n_laps   = len(lt_df)

    data_path = ""
    max_speed = 0.0
    if telemetry_df is not None:
        max_speed = float(telemetry_df["Speed"].max()) if "Speed" in telemetry_df.columns else 0.0
        ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        drv = meta.get("driver_name", "driver").replace(" ", "_")[:20]
        fname = f"{ts}_{drv}.pkl.gz"
        fpath = SAVED_DATA_DIR / fname
        with gzip.open(fpath, "wb") as f:
            pickle.dump({"df": telemetry_df, "meta": meta}, f, protocol=pickle.HIGHEST_PROTOCOL)
        data_path = str(fpath)

    cur.execute("""
        INSERT INTO sessions
        (date,driver,track,car,series,weather,track_temp,
         best_lap_s,best_lap_str,n_laps,file_path,compound,notes,data_path,max_speed)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        datetime.datetime.now().isoformat(),
        meta.get("driver_name","?"), meta.get("track","?"),
        meta.get("car_name","?"),   meta.get("series","?"),
        meta.get("weather","?"),    str(meta.get("track_temp","?")),
        best_s, best_str, n_laps,
        meta.get("filename",""), compound, notes, data_path, max_speed
    ))
    session_id = cur.lastrowid
    con.commit(); con.close()

    if telemetry_df is not None:
        try:
            from core.telemetry_metrics import extract_session_metrics
            metrics = extract_session_metrics(telemetry_df)
            db_save_metrics(session_id, metrics)
        except Exception as e:
            print(f"Failed to extract session metrics: {e}")

    return session_id

def db_load_session_data(session_id: int):
    db_init()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT data_path FROM sessions WHERE id=?", (session_id,))
    row = cur.fetchone()
    con.close()
    if not row or not row[0]:
        return None, None
    fpath = Path(row[0])
    if not fpath.exists():
        return None, None
    try:
        with gzip.open(fpath, "rb") as f:
            data = pickle.load(f)
        return data["df"], data["meta"]
    except Exception as e:
        print(f"Error loading session {session_id}: {e}")
        return None, None

def db_delete_session(session_id: int):
    db_init()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT data_path FROM sessions WHERE id=?", (session_id,))
    row = cur.fetchone()
    if row and row[0]:
        fpath = Path(row[0])
        if fpath.exists():
            try: fpath.unlink()
            except Exception as e: print(f"Delete file error: {e}")

    cur.execute("DELETE FROM setups WHERE session_id=?", (session_id,))
    cur.execute("DELETE FROM annotations WHERE session_id=?", (session_id,))
    cur.execute("DELETE FROM sessions WHERE id=?", (session_id,))
    con.commit(); con.close()

def db_save_setup(session_id: int, setup: dict):
    db_init()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cols = ["session_id",
            "front_wing","rear_wing",
            "fl_spring","fr_spring","rl_spring","rr_spring",
            "fl_camber","fr_camber","rl_camber","rr_camber",
            "fl_toe","fr_toe","rl_toe","rr_toe",
            "fl_ride_h","fr_ride_h","rl_ride_h","rr_ride_h",
            "fl_cold_p","fr_cold_p","rl_cold_p","rr_cold_p",
            "compound","brake_bias",
            "diff_entry","diff_mid","diff_exit","notes"]
    vals = [session_id] + [setup.get(c) for c in cols[1:]]
    cur.execute(f"INSERT INTO setups ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})", vals)
    con.commit(); con.close()

def db_save_annotation(session_id: int, lap: int, pos: float, channel: str, note: str):
    db_init()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""INSERT INTO annotations
                   (session_id,lap_number,track_pos,channel,note,created_at)
                   VALUES (?,?,?,?,?,?)""",
                (session_id, lap, pos, channel, note, datetime.datetime.now().isoformat()))
    con.commit(); con.close()

def db_load_sessions() -> pd.DataFrame:
    db_init()
    con = sqlite3.connect(DB_PATH)
    df  = pd.read_sql("SELECT * FROM sessions ORDER BY date DESC", con)
    con.close()
    return df

def db_load_setup(session_id: int) -> dict:
    db_init()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT * FROM setups WHERE session_id=? ORDER BY id DESC LIMIT 1", (session_id,))
    row = cur.fetchone()
    res = {}
    if row:
        cols = [d[0] for d in cur.description]
        res = dict(zip(cols, row))
    con.close()
    return res

def db_load_annotations(session_id: int) -> pd.DataFrame:
    db_init()
    con = sqlite3.connect(DB_PATH)
    df  = pd.read_sql(f"SELECT * FROM annotations WHERE session_id={session_id}", con)
    con.close()
    return df


# ════════════════════════════════════════════════════════════════════════════
# ML — Session Metrics & Rating
# ════════════════════════════════════════════════════════════════════════════

def db_save_metrics(session_id: int, metrics: dict):
    """Save computed telemetry metrics for ML anomaly detection."""
    db_init()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cols = ["session_id", "avg_tire_temp_f", "avg_tire_temp_r", "tire_temp_spread",
            "yaw_spike_pct", "brake_stability", "throttle_smooth",
            "coasting_pct", "max_lat_g", "avg_speed", "oversteer_ratio"]
    vals = [session_id] + [metrics.get(c, 0.0) for c in cols[1:]]
    cur.execute(f"INSERT OR REPLACE INTO session_metrics ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})", vals)
    con.commit(); con.close()


def db_load_all_metrics() -> pd.DataFrame:
    """Load all session metrics for ML analysis."""
    db_init()
    con = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql("SELECT * FROM session_metrics", con)
    except Exception:
        df = pd.DataFrame()
    con.close()
    return df


def db_save_rating(session_id: int, rating: int):
    """Save user's setup rating (1-5 stars) for a session."""
    db_init()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("UPDATE sessions SET setup_rating=? WHERE id=?", (rating, session_id))
    con.commit(); con.close()


def db_save_advisor_score(session_id: int, score: int):
    """Save the computed Setup Advisor score for a session."""
    db_init()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("UPDATE sessions SET advisor_score=? WHERE id=?", (score, session_id))
    con.commit(); con.close()
