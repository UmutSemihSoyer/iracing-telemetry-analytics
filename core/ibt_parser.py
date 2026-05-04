"""
╔══════════════════════════════════════════════════════════════╗
║   iRacing IBT Binary Parser  —  Independent, zero deps        ║
║   Does not require pyirsdk or open iRacing                    ║
╚══════════════════════════════════════════════════════════════╝

Usage (standalone):
    from core.ibt_parser import IBTFile
    ibt = IBTFile("session.ibt")
    df  = ibt.to_dataframe()          # all channels
    df  = ibt.to_dataframe(channels=["Speed","Throttle","Brake"])
    print(ibt.session_info)           # YAML metadata (dict)
    print(ibt.available_channels())   # channel list

You can save:
    ibt.to_csv("output.csv")
"""

import struct
import io
from pathlib import Path
import numpy as np
import pandas as pd
from typing import Optional, Union, Any, Dict, List, cast

try:
    import yaml
    _YAML = True
except ImportError:
    _YAML = False


# ════════════════════════════════════════════════════════════════════════════
# IBT FORMAT CONSTANTS
# ════════════════════════════════════════════════════════════════════════════

# irsdk_varType
VAR_TYPES = {
    0: ("char",    "c", 1),
    1: ("bool",    "?", 1),
    2: ("int",     "i", 4),
    3: ("bitField","I", 4),
    4: ("float",   "f", 4),
    5: ("double",  "d", 8),
}

# irsdk_header  (112 bytes)
HEADER_FMT = struct.Struct("<10i 2i 4s4s4s4s4s4s4s4s4s4s4s4s4s4s4s4s")
# Daha okunabilir ayrıştırma için elle okuyacağız ↓

# irsdk_diskSubHeader (32 bytes)
DISK_SUB_FMT = struct.Struct("<qddii")   # longlong, double, double, int, int

# irsdk_varHeader (144 bytes)
VAR_HEADER_FMT = struct.Struct("<3i ?3x 32s 64s 32s")

# irsdk_varBuf (16 bytes each, 4 adet → 64 byte)
VAR_BUF_FMT = struct.Struct("<ii2i")   # tickCount, bufOffset, pad[2]

IRSDK_VER = 2
HEADER_SIZE    = 112
DISK_SUB_SIZE  = 32
VAR_HEADER_SIZE = 144
VAR_BUF_SIZE   = 16


# ════════════════════════════════════════════════════════════════════════════
# HELPERS: Manual struct parsing
# ════════════════════════════════════════════════════════════════════════════

def _read_header(data: bytes) -> dict:
    """Parse irsdk_header."""
    s = struct.unpack_from("<10i", data, 0)
    # ver, status, tickRate, sessionInfoUpdate, sessionInfoLen,
    # sessionInfoOffset, numVars, varHeaderOffset, numBuf, bufLen
    h = {
        "ver":               s[0],
        "status":            s[1],
        "tick_rate":         s[2],
        "session_info_update": s[3],
        "session_info_len":  s[4],
        "session_info_offset": s[5],
        "num_vars":          s[6],
        "var_header_offset": s[7],
        "num_buf":           s[8],
        "buf_len":           s[9],
    }
    # pad (8 byte), sonra varBuf[4]  her biri 16 byte
    var_bufs = []
    offset = 10 * 4 + 8   # after 10 ints + 2 pad ints
    for i in range(4):
        tick_count, buf_offset, _, _ = struct.unpack_from("<4i", data, offset)
        var_bufs.append({"tick_count": tick_count, "buf_offset": buf_offset})
        offset += VAR_BUF_SIZE
    h["var_bufs"] = var_bufs
    return h


def _read_disk_sub(data: bytes) -> dict:
    """irsdk_diskSubHeader'ı parse et."""
    s = struct.unpack_from("<qddii", data, HEADER_SIZE)
    return {
        "session_start_date": s[0],
        "session_start_time": s[1],
        "session_end_time":   s[2],
        "lap_count":          s[3],
        "record_count":       s[4],
    }


def _read_var_headers(data: bytes, num_vars: int, var_header_offset: int) -> list:
    """Tüm irsdk_varHeader'ları parse et."""
    headers = []
    offset  = int(var_header_offset)
    for _ in range(num_vars):
        type_id, var_offset, count, count_as_time = \
            struct.unpack_from("<iii?", data, offset)
        # 3 byte padding sonra name(32), desc(64), unit(32)
        # Type checker'ı ikna etmek için slice'ı netleştirelim
        name_raw = data[offset + 16 : offset + 48]
        desc_raw = data[offset + 48 : offset + 112]
        unit_raw = data[offset + 112 : offset + 144]
        
        def safe_decode(b_str):
            try:
                return b_str.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    return b_str.decode("cp1254")
                except UnicodeDecodeError:
                    return b_str.decode("latin-1", errors="replace")

        name = safe_decode(bytes(name_raw).rstrip(b"\x00"))
        desc = safe_decode(bytes(desc_raw).rstrip(b"\x00"))
        unit = safe_decode(bytes(unit_raw).rstrip(b"\x00"))

        type_info = VAR_TYPES.get(type_id, ("unknown", "x", 1))
        headers.append({
            "name":        name,
            "desc":        desc,
            "unit":        unit,
            "type_id":     type_id,
            "type_name":   type_info[0],
            "fmt":         type_info[1],
            "type_size":   type_info[2],
            "offset":      var_offset,
            "count":       count,
            "count_as_time": count_as_time,
        })
        offset += VAR_HEADER_SIZE
    return headers


# ════════════════════════════════════════════════════════════════════════════
# MAIN CLASS
# ════════════════════════════════════════════════════════════════════════════

class IBTFile:
    """
    Reads iRacing .ibt file and converts to pandas DataFrame.

    Parameters
    ──────────
    path : str | Path | bytes
        File path or raw bytes (for browser upload).
    """
    _data: bytes
    filename: str
    _header: dict
    _disk_sub: dict
    session_info: dict
    _var_headers: list
    _var_map: dict
    _data_offset: int
    _buf_len: int
    _record_count: int

    def __init__(self, path: Union[str, Path, bytes]):
        if isinstance(path, (str, Path)):
            self._data = memoryview(Path(path).read_bytes())
            self.filename = Path(path).name
        else:
            self._data = memoryview(path)          # ham bytes
            self.filename = "upload.ibt"

        self._parse()

    # ────────────────────────────────────────────────────────────────────────
    def _parse(self):
        data = self._data

        # Başlık kontrol
        if len(data) < HEADER_SIZE + DISK_SUB_SIZE:
            raise ValueError("Dosya çok küçük — geçerli bir .ibt dosyası değil.")

        self._header   = _read_header(data)
        self._disk_sub = _read_disk_sub(data)

        if self._header["ver"] < IRSDK_VER:
            raise ValueError(f"Desteklenmeyen irsdk versiyonu: {self._header['ver']}")

        # Session info YAML
        si_offset = int(self._header["session_info_offset"])
        si_len    = int(self._header["session_info_len"])
        raw_yaml_b = bytes(data[si_offset : si_offset + si_len]).rstrip(b"\x00")
        try:
            raw_yaml = raw_yaml_b.decode("utf-8")
        except UnicodeDecodeError:
            try:
                raw_yaml = raw_yaml_b.decode("cp1254")
            except UnicodeDecodeError:
                raw_yaml = raw_yaml_b.decode("latin-1", errors="replace")

        if _YAML:
            try:
                self.session_info = yaml.safe_load(raw_yaml) or {}
            except Exception:
                self.session_info = {"raw": raw_yaml}
        else:
            self.session_info = {"raw": raw_yaml}

        # Değişken başlıkları
        self._var_headers = _read_var_headers(
            data, self._header["num_vars"], self._header["var_header_offset"]
        )
        self._var_map = {v["name"]: v for v in self._var_headers}

        # Veri bloğu başlangıcı
        # Disk modunda veri, header + disk_sub + session_info + var_headers'ın hemen ardından gelir
        # En güvenli yol: ilk varBuf'un buf_offset'ini kullan
        active_buf = None
        for vb in self._header["var_bufs"]:
            if vb["buf_offset"] > 0:
                active_buf = vb
                break

        if active_buf is None:
            # Disk modunda buf_offset=0 olabilir; manuel hesapla
            self._data_offset = (
                self._header["var_header_offset"]
                + self._header["num_vars"] * VAR_HEADER_SIZE
            )
        else:
            self._data_offset = active_buf["buf_offset"]

        self._buf_len     = self._header["buf_len"]
        self._record_count = self._disk_sub["record_count"]

        # Record count sıfırsa dosya sonundan hesapla
        if self._record_count <= 0:
            remaining = len(data) - self._data_offset
            if self._buf_len > 0:
                self._record_count = remaining // self._buf_len

    # ────────────────────────────────────────────────────────────────────────
    def available_channels(self) -> "pd.DataFrame":
        """List all channels with name, description, unit, and type."""
        rows = []
        for v in self._var_headers:
            rows.append({
                "Channel":     v["name"],
                "Description": v["desc"],
                "Unit":        v["unit"],
                "Type":        v["type_name"],
                "Count":       v["count"],
            })
        return pd.DataFrame(rows)

    def get_setup_dict(self) -> dict:
        """Extract car setup from session_info YAML into a comprehensive flat dict.
        
        Handles the real iRacing CarSetup YAML structure:
          CarSetup:
            TiresAero:
              LeftFront: { StartingPressure, LastHotPressure, ... }
              ...
              AeroBalanceCalc: { FrontRhAtSpeed, RearRhAtSpeed, WingSetting, ... }
            Chassis:
              FrontBrakesLights: { ArbSetting, TotalToeIn, FuelLevel, ... }
              LeftFront: { CornerWeight, RideHeight, SpringRate, Camber, ... }
              ...
              InCarAdjustments: { BrakePressureBias, AbsSetting, TcSetting, ... }
              GearsDifferential: { DiffPreload, ... }
            Dampers:
              FrontDampers: { LowSpeedCompressionDamping, ... }
              RearDampers: { ... }
        """
        import re
        
        setup = {}
        if not hasattr(self, "session_info") or "CarSetup" not in self.session_info:
            return setup

        car_setup = self.session_info["CarSetup"]

        def parse_val(s):
            """Parse numeric part from strings like '4 clicks', '138 kPa', '-2.50 deg'."""
            if s is None:
                return None
            if isinstance(s, (int, float)):
                return float(s)
            if not isinstance(s, str):
                return s
            m = re.search(r"([-+]?\d*\.?\d+)", s)
            if m:
                try:
                    return float(m.group(1))
                except Exception:
                    return s
            return s

        def get_raw(s):
            """Return raw string value for display (e.g. '159 kPa', '-4.0 deg')."""
            if s is None:
                return ""
            return str(s)

        # ── TiresAero ──────────────────────────────────────────────────
        tires_aero = car_setup.get("TiresAero", {})
        
        # Tire Type
        tire_type_info = tires_aero.get("TireType", {})
        setup["tire_type"] = tire_type_info.get("TireType", "Unknown")
        
        # Tire pressures & temps per corner
        for corner, prefix in [("LeftFront", "fl"), ("RightFront", "fr"),
                                ("LeftRear", "rl"), ("RightRear", "rr")]:
            corner_data = tires_aero.get(corner, {})
            setup[f"{prefix}_cold_p"] = parse_val(corner_data.get("StartingPressure"))
            setup[f"{prefix}_hot_p"] = parse_val(corner_data.get("LastHotPressure"))
            setup[f"{prefix}_last_temps"] = get_raw(
                corner_data.get("LastTempsOMI") or corner_data.get("LastTempsIMO", ""))
            setup[f"{prefix}_tread_remaining"] = get_raw(corner_data.get("TreadRemaining", ""))
        
        # Aero balance
        aero = tires_aero.get("AeroBalanceCalc", {})
        setup["front_rh_at_speed"] = parse_val(aero.get("FrontRhAtSpeed"))
        setup["rear_rh_at_speed"] = parse_val(aero.get("RearRhAtSpeed"))
        setup["wing_setting"] = parse_val(aero.get("WingSetting"))
        setup["front_downforce_pct"] = parse_val(aero.get("FrontDownforce"))
        # Map to legacy keys for compatibility
        setup["front_wing"] = setup.get("wing_setting")
        setup["rear_wing"] = setup.get("wing_setting")

        # ── Chassis ────────────────────────────────────────────────────
        chassis = car_setup.get("Chassis", {})
        
        # Front brakes / lights / misc
        front_misc = chassis.get("FrontBrakesLights", chassis.get("Front", {}))
        setup["arb_front"] = parse_val(front_misc.get("ArbSetting"))
        setup["front_toe"] = get_raw(front_misc.get("TotalToeIn", ""))
        setup["fuel_level"] = parse_val(front_misc.get("FuelLevel"))
        setup["front_master_cyl"] = parse_val(front_misc.get("FrontMasterCyl"))
        setup["rear_master_cyl"] = parse_val(front_misc.get("RearMasterCyl"))
        setup["brake_pads"] = get_raw(front_misc.get("BrakePads", ""))
        setup["splitter_height"] = parse_val(front_misc.get("CenterFrontSplitterHeight"))
        
        # Suspension per corner
        for corner, prefix in [("LeftFront", "fl"), ("RightFront", "fr"),
                                ("LeftRear", "rl"), ("RightRear", "rr")]:
            corner_data = chassis.get(corner, {})
            setup[f"{prefix}_corner_weight"] = parse_val(corner_data.get("CornerWeight"))
            setup[f"{prefix}_ride_h"] = parse_val(corner_data.get("RideHeight"))
            setup[f"{prefix}_bump_rubber"] = parse_val(corner_data.get("BumpRubberGap"))
            setup[f"{prefix}_spring"] = parse_val(corner_data.get("SpringRate"))
            setup[f"{prefix}_camber"] = parse_val(corner_data.get("Camber"))
        
        # Rear section
        rear = chassis.get("Rear", {})
        setup["arb_rear"] = parse_val(rear.get("RarbSetting"))
        setup["rear_toe"] = get_raw(rear.get("TotalToeIn", ""))
        setup["rear_wing_chassis"] = parse_val(rear.get("WingSetting"))
        
        # In-car adjustments
        in_car = chassis.get("InCarAdjustments", {})
        setup["brake_bias"] = parse_val(in_car.get("BrakePressureBias"))
        setup["abs_setting"] = get_raw(in_car.get("AbsSetting", ""))
        setup["tc_setting"] = get_raw(in_car.get("TcSetting", ""))
        setup["throttle_shape"] = parse_val(in_car.get("ThrottleShapeSetting"))
        setup["fw_dist"] = parse_val(in_car.get("FWtdist"))
        setup["cross_weight"] = parse_val(in_car.get("CrossWeight"))
        
        # Gears / Differential
        gears_diff = chassis.get("GearsDifferential", {})
        setup["gear_stack"] = get_raw(gears_diff.get("GearStack", ""))
        setup["diff_preload"] = parse_val(gears_diff.get("DiffPreload"))
        setup["friction_faces"] = parse_val(gears_diff.get("FrictionFaces"))
        # Legacy compat
        setup["diff_entry"] = setup.get("diff_preload")
        setup["diff_mid"] = None
        setup["diff_exit"] = None

        # ── Dampers ────────────────────────────────────────────────────
        dampers = car_setup.get("Dampers", {})
        
        front_dampers = dampers.get("FrontDampers", {})
        setup["front_lsc"] = parse_val(front_dampers.get("LowSpeedCompressionDamping"))
        setup["front_hsc"] = parse_val(front_dampers.get("HighSpeedCompressionDamping"))
        setup["front_lsr"] = parse_val(front_dampers.get("LowSpeedReboundDamping"))
        setup["front_hsr"] = parse_val(front_dampers.get("HighSpeedReboundDamping"))
        
        rear_dampers = dampers.get("RearDampers", {})
        setup["rear_lsc"] = parse_val(rear_dampers.get("LowSpeedCompressionDamping"))
        setup["rear_hsc"] = parse_val(rear_dampers.get("HighSpeedCompressionDamping"))
        setup["rear_lsr"] = parse_val(rear_dampers.get("LowSpeedReboundDamping"))
        setup["rear_hsr"] = parse_val(rear_dampers.get("HighSpeedReboundDamping"))

        # ── Store raw CarSetup for full access ─────────────────────────
        setup["_raw"] = car_setup

        # Clean out None values from mapping
        setup = {k: v for k, v in setup.items() if v is not None}
        
        return setup

    # ────────────────────────────────────────────────────────────────────────
    def to_dataframe(self,
                     channels: Optional[list] = None,
                     max_records: Optional[int] = None,
                     downsample: int = 1) -> "pd.DataFrame":
        """
        IBT verisini DataFrame'e dönüştür.

        Parametreler
        ────────────
        channels    : Okunacak kanal listesi. None → tümü.
        max_records : Maksimum satır sayısı (büyük dosyalar için).
        """
        data        = self._data
        buf_len     = self._buf_len
        n_records   = self._record_count
        data_offset = self._data_offset

        if max_records:
            n_records = min(n_records, max_records)

        # Okunacak kanalları belirle
        if channels:
            var_list = [self._var_map[c] for c in channels if c in self._var_map]
            missing  = [c for c in channels if c not in self._var_map]
            if missing:
                print(f"⚠️  Bulunamayan kanallar: {missing}")
        else:
            var_list = self._var_headers

        # Yüksek performanslı vektörize okuma (O(1) Memory Mapping)
        # 1. Beklenmedik kırpılmalara karşı güvenli satır hesabı
        safe_records = n_records
        for v in var_list:
            req_len = data_offset + v["offset"] + (safe_records - 1) * buf_len + v["count"] * v["type_size"]
            if req_len > len(data):
                safe_records = max(0, (len(data) - data_offset - v["offset"] - v["count"] * v["type_size"]) // buf_len + 1)

        arrays: Dict[str, Any] = {}
        for v in var_list:
            col = v["name"]
            c_type_np = _np_dtype(v)
            off = data_offset + v["offset"]
            cnt = v["count"]

            if safe_records <= 0:
                arrays[col] = np.zeros(0, dtype=c_type_np)
                continue

            # Memory map the exact buffer required
            req_len = off + (safe_records - 1) * buf_len + cnt * v["type_size"]
            arr = np.ndarray(
                shape=(safe_records, cnt) if cnt > 1 else (safe_records,),
                dtype=c_type_np,
                buffer=data[:req_len],
                offset=off,
                strides=(buf_len, c_type_np().itemsize) if cnt > 1 else (buf_len,)
            )

            # Bellek sızıntısını veya ham büyük veri bağımlılığını kesmek için kopyalıyoruz
            if cnt == 1:
                arrays[col] = arr[::downsample].copy()
            else:
                arrays[col] = list(arr[::downsample].copy())

        df = pd.DataFrame(arrays)

        # Tip düzeltmeleri
        for v in var_list:
            col = v["name"]
            if v["type_name"] == "bool" and col in df.columns:
                df[col] = df[col].astype(int)

        # Zaman indeksi ekle (tick_rate'e göre)
        tick_rate = self._header["tick_rate"] or 60
        # Adjust time for downsampling
        df.insert(0, "Time_s", (np.arange(len(df)) * downsample) / tick_rate)

        return df

    # ────────────────────────────────────────────────────────────────────────
    def to_csv(self, output_path: Union[str, Path],
               channels: Optional[list] = None) -> None:
        """Save DataFrame as CSV."""
        df = self.to_dataframe(channels=channels)
        df.to_csv(output_path, index=False)
        print(f"✅ Saved: {output_path}  ({len(df):,} rows, {len(df.columns)} channels)")

    # ────────────────────────────────────────────────────────────────────────
    @property
    def meta(self) -> dict:
        """Temel meta bilgileri."""
        si  = self.session_info
        drv = {}
        try:
            drv = si["DriverInfo"]["Drivers"][
                si["DriverInfo"]["DriverCarIdx"]
            ]
        except Exception:
            pass

        return {
            "filename":    self.filename,
            "tick_rate":   self._header["tick_rate"],
            "records":     self._record_count,
            "lap_count":   self._disk_sub["lap_count"],
            "duration_s":  round(self._disk_sub["session_end_time"]
                                 - self._disk_sub["session_start_time"], 2),
            "channels":    self._header["num_vars"],
            "driver_name": drv.get("UserName", "Unknown"),
            "car_name":    drv.get("CarPath", "Unknown"),
            "track":       si.get("WeekendInfo", {}).get("TrackName", "Unknown"),
            "track_length": si.get("WeekendInfo", {}).get("TrackLength", ""),
            "track_temp":  si.get("WeekendInfo", {}).get("TrackSurfaceTemp", "?"),
            "air_temp":    si.get("WeekendInfo", {}).get("AirTemp", "?"),
            "weather":     si.get("WeekendInfo", {}).get("Skies", "?"),
            "wind_speed":  si.get("WeekendInfo", {}).get("WindSpeed", ""),
            "wind_dir":    si.get("WeekendInfo", {}).get("WindDir", ""),
            "humidity":    si.get("WeekendInfo", {}).get("RelativeHumidity", ""),
            "series":      si.get("WeekendInfo", {}).get("SeriesName", "?"),
        }

    # ────────────────────────────────────────────────────────────────────────
    def __repr__(self):
        m = self.meta
        return (f"IBTFile({m['filename']})\n"
                f"  Sürücü : {m['driver_name']}\n"
                f"  Araç   : {m['car_name']}\n"
                f"  Pist   : {m['track']}\n"
                f"  Kanallar: {m['channels']}  |  Kayıtlar: {m['records']:,}\n"
                f"  Süre   : {m['duration_s']} s  |  Turlar: {m['lap_count']}")


# ════════════════════════════════════════════════════════════════════════════
# YARDIMCI
# ════════════════════════════════════════════════════════════════════════════

def _np_dtype(v: dict):
    m = {
        "char":     np.int8,
        "bool":     np.int8,
        "int":      np.int32,
        "bitField": np.uint32,
        "float":    np.float32,
        "double":   np.float64,
        "unknown":  np.float32,
    }
    return m.get(v["type_name"], np.float32)


# ════════════════════════════════════════════════════════════════════════════
# DASHBOARD İÇİN STANDART KANAL HARİTASI
# iRacing kanal adları → dashboard'un beklediği sütun adları
# ════════════════════════════════════════════════════════════════════════════

CHANNEL_MAP = {
    # Hız & Konum
    "Speed":             "Speed",          # m/s
    "VelocityX":         "VelocityX",      # İleri hız (m/s)
    "VelocityY":         "VelocityY",      # Yanal hız (m/s)
    "VelocityZ":         "VelocityZ",      # Dikey hız (m/s)
    "LapDist":           "LapDist",        # meters
    "LapDistPct":        "LapDistPct",
    "Lat":               "Lat",
    "Lon":               "Lon",
    "Alt":               "Alt",
    "OnPitRoad":         "OnPitRoad",

    # Pedal & Direksiyon
    "Brake":             "Brake",
    "Throttle":          "Throttle",
    "SteeringWheelAngle":"SteeringWheelAngle",
    "Clutch":            "Clutch",

    # Motor & Şanzıman
    "RPM":               "RPM",
    "Gear":              "Gear",

    # G kuvvetleri & Dinamikler
    "LatAccel":          "LatAccel",
    "LongAccel":         "LongAccel",
    "VertAccel":         "VertAccel",
    "Yaw":               "Yaw",
    "YawRate":           "YawRate",
    "Pitch":             "Pitch",
    "PitchRate":         "PitchRate",
    "Roll":              "Roll",
    "RollRate":          "RollRate",

    # Yakıt
    "FuelLevel":         "FuelLevel",
    "FuelLevelPct":      "FuelLevelPct",
    "FuelUsePerHour":    "FuelUsePerHour",

    # Lastik sıcaklık & basınç (4 tekerlek)
    # Lastik sıcaklık & basınç (4 tekerlek) - Surface (Yüzey) öncelikli
    "LFtempL":           "TireTemp_FL_L",
    "LFtempM":           "TireTemp_FL_M",
    "LFtempR":           "TireTemp_FL_R",
    "RFtempL":           "TireTemp_FR_L",
    "RFtempM":           "TireTemp_FR_M",
    "RFtempR":           "TireTemp_FR_R",
    "LRtempL":           "TireTemp_RL_L",
    "LRtempM":           "TireTemp_RL_M",
    "LRtempR":           "TireTemp_RL_R",
    "RRtempL":           "TireTemp_RR_L",
    "RRtempM":           "TireTemp_RR_M",
    "RRtempR":           "TireTemp_RR_R",

    # Carcass (Karkas/İç) sıcaklıklar - Yedek olarak
    "LFtempCL":          "TireTemp_FL_L_C",
    "LFtempCM":          "TireTemp_FL_M_C",
    "LFtempCR":          "TireTemp_FL_R_C",
    "RFtempCL":          "TireTemp_FR_L_C",
    "RFtempCM":          "TireTemp_FR_M_C",
    "RFtempCR":          "TireTemp_FR_R_C",
    "LRtempCL":          "TireTemp_RL_L_C",
    "LRtempCM":          "TireTemp_RL_M_C",
    "LRtempCR":          "TireTemp_RL_R_C",
    "RRtempCL":          "TireTemp_RR_L_C",
    "RRtempCM":          "TireTemp_RR_M_C",
    "RRtempCR":          "TireTemp_RR_R_C",

    # Lastik tipi (0=Dry, 1=Wet/Rain)
    "TireLF_Type":       "TireType_FL",
    "TireRF_Type":       "TireType_FR",
    "TireLR_Type":       "TireType_RL",
    "TireRR_Type":       "TireType_RR",

    # Lastik aşınması (Wear)
    "LFwearL":           "TireWear_FL_L",
    "LFwearM":           "TireWear_FL_M",
    "LFwearR":           "TireWear_FL_R",
    "RFwearL":           "TireWear_FR_L",
    "RFwearM":           "TireWear_FR_M",
    "RFwearR":           "TireWear_FR_R",
    "LRwearL":           "TireWear_RL_L",
    "LRwearM":           "TireWear_RL_M",
    "LRwearR":           "TireWear_RL_R",
    "RRwearL":           "TireWear_RR_L",
    "RRwearM":           "TireWear_RR_M",
    "RRwearR":           "TireWear_RR_R",

    # Lastik basıncı
    "LFpressure":        "TirePress_FL",
    "RFpressure":        "TirePress_FR",
    "LRpressure":        "TirePress_RL",
    "RRpressure":        "TirePress_RR",

    # Süspansiyon & Şasi
    "LFshockDefl":       "Suspension_FL",
    "RFshockDefl":       "Suspension_FR",
    "LRshockDefl":       "Suspension_RL",
    "RRshockDefl":       "Suspension_RR",

    # ABS / TC / DRS
    "ABSActive":         "ABSActive",
    "dcABS":             "ABSLevel",
    "DRSActive":         "DRSActive",

    # Tur & Zaman
    "Lap":               "Lap",
    "LapCurrentLapTime": "LapCurrentTime",
    "LapLastLapTime":    "LapLastTime",
    "LapBestLapTime":    "LapBestTime",
    "LapBestLap":        "LapBestLapNum",

    # Hava & Pist
    "AirTemp":           "AirTemp",
    "TrackTemp":         "TrackTemp",
    "TrackTempCrew":     "TrackTempCrew",
    "WindVel":           "WindSpeed",
    "WindDir":           "WindDir",
    "Humidity":          "Humidity",
    "FogLevel":          "FogLevel",

    # Motor detayları
    "OilTemp":           "OilTemp",
    "OilPress":          "OilPress",
    "WaterTemp":         "WaterTemp",
    "ManifoldPress":     "ManifoldPress",

    # Zaman
    "Time_s":            "Time_s",
}


def ibt_to_dashboard_df(ibt: IBTFile, max_records: Optional[int] = None, downsample: int = 1) -> pd.DataFrame:
    """
    IBTFile → DataFrame in the format expected by the Dashboard.
    Only takes available channels, skips missing ones.
    """
    available = set(ibt._var_map.keys()) | {"Time_s"}
    wanted    = [k for k in CHANNEL_MAP.keys() if k in available or k == "Time_s"]

    # Time_s to_dataframe tarafından ekleniyor, ayrıca isteme
    ibt_channels = [k for k in wanted if k != "Time_s" and k in ibt._var_map]

    df = ibt.to_dataframe(channels=ibt_channels, max_records=max_records, downsample=downsample)

    # Sütun adlarını yeniden adlandır
    rename: dict[str, str] = {k: v for k, v in CHANNEL_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)

    # LapDistPct 0-1 aralığında olmalı
    if "LapDistPct" in df.columns:
        mx = df["LapDistPct"].max()
        if mx > 1.01:   # muhtemelen 0-100 ölçeği
            df["LapDistPct"] = df["LapDistPct"] / 100.0

    # Speed m/s kontrolü (bazen kph gelir)
    if "Speed" in df.columns:
        if df["Speed"].max() > 120:   # muhtemelen kph
            df["Speed"] = df["Speed"] / 3.6

    # Gerçek tur numarası varsa kullan
    if "Lap" in df.columns:
        df["LapNumber"] = df["Lap"].astype(int)
    
    # Meta bilgiyi sütun olarak ekle
    meta = ibt.meta
    df["Driver"]    = meta["driver_name"]
    df["TrackName"] = meta["track"]

    return df


# ════════════════════════════════════════════════════════════════════════════
# CLI ARAYÜZÜ
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys, tkinter as tk
    from tkinter import filedialog

    root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
    path = filedialog.askopenfilename(
        title="IBT Dosyası Seç",
        filetypes=[("iRacing Telemetri", "*.ibt"), ("Tümü", "*.*")]
    )
    root.destroy()

    if not path:
        sys.exit("İptal edildi.")

    print(f"\n📂 Yükleniyor: {path}")
    ibt = IBTFile(path)
    print(ibt)

    print("\n📋 İlk 20 kanal:")
    print(ibt.available_channels().head(20).to_string(index=False))

    print("\n🔄 DataFrame'e dönüştürülüyor...")
    df = ibt_to_dashboard_df(ibt)
    print(f"✅ {len(df):,} satır × {len(df.columns)} sütun")
    print(df.describe().round(3))

    # CSV olarak kaydet?
    out = Path(path).with_suffix(".csv")
    df.to_csv(out, index=False)
    print(f"\n💾 CSV kaydedildi: {out}")
