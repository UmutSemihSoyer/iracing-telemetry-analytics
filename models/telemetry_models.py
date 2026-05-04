from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import pandas as pd

@dataclass
class LapSummary:
    lap_number: int
    lap_time: float
    is_valid: bool
    is_best: bool
    sector_times: List[float] = field(default_factory=list)

@dataclass
class TelemetrySession:
    """
    Represents a loaded iRacing telemetry session.
    Provides a type-safe wrapper around the raw DataFrame and metadata.
    """
    filename: str
    driver_name: str
    track_name: str
    car_name: str
    duration_s: float
    df: pd.DataFrame
    meta: Dict[str, Any]
    laps: List[LapSummary] = field(default_factory=list)

    @property
    def total_rows(self) -> int:
        return len(self.df)

@dataclass
class SetupData:
    """
    Wrapper for car setup parameters extracted from session info.
    """
    tire_type: str
    fuel_level: float
    front_wing: Optional[float] = None
    rear_wing: Optional[float] = None
    raw_setup: Dict[str, Any] = field(default_factory=dict)
