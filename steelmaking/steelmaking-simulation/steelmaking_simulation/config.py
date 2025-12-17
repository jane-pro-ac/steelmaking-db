"""Configuration settings for the steelmaking simulation."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class DatabaseConfig:
    """Database connection configuration."""
    host: str = os.getenv("DB_HOST", "localhost")
    port: int = int(os.getenv("DB_PORT", "5432"))
    database: str = os.getenv("DB_NAME", "postgres")
    user: str = os.getenv("DB_USER", "postgres")
    password: str = os.getenv("DB_PASSWORD", "")

    @property
    def connection_string(self) -> str:
        return f"host={self.host} port={self.port} dbname={self.database} user={self.user} password={self.password}"


@dataclass
class SimulationConfig:
    """Simulation parameters configuration."""
    # Time interval between simulation ticks (seconds)
    interval: int = int(os.getenv("SIMULATION_INTERVAL", "2"))
    
    # Probability of starting a new heat each tick
    new_heat_probability: float = float(os.getenv("NEW_HEAT_PROBABILITY", "0.3"))
    
    # Operation duration range (minutes)
    min_operation_duration: int = int(os.getenv("MIN_OPERATION_DURATION_MINUTES", "30"))
    max_operation_duration: int = int(os.getenv("MAX_OPERATION_DURATION_MINUTES", "50"))

    # Transfer gap between BOF->LF->CCM for the same heat (minutes)
    min_transfer_gap_minutes: int = int(os.getenv("MIN_TRANSFER_GAP_MINUTES", "20"))
    max_transfer_gap_minutes: int = int(os.getenv("MAX_TRANSFER_GAP_MINUTES", "30"))

    # Max allowed device idle/rest time (minutes)
    max_rest_duration_minutes: int = int(os.getenv("MAX_REST_DURATION_MINUTES", "20"))
    # Min required device rest time between consecutive operations (minutes)
    min_rest_duration_minutes: int = int(os.getenv("MIN_REST_DURATION_MINUTES", "3"))

    # Prefer aligned routing: BOF#i -> LF#i -> CCM#i
    aligned_route_probability: float = float(os.getenv("ALIGNED_ROUTE_PROBABILITY", "0.9"))

    # Warnings
    max_warnings_per_operation: int = int(os.getenv("MAX_WARNINGS_PER_OPERATION", "10"))
    warning_probability_per_tick: float = float(os.getenv("WARNING_PROBABILITY_PER_TICK", "0.2"))
    seed_warning_probability_per_completed_operation: float = float(
        os.getenv("SEED_WARNING_PROBABILITY_PER_COMPLETED_OPERATION", "0.2")
    )

    # Gap between operations range (minutes)
    min_gap_duration: int = 1
    max_gap_duration: int = 10

    # Demo seeding
    seed_past_heats: int = int(os.getenv("DEMO_SEED_PAST_HEATS", "4"))
    seed_active_heats: int = int(os.getenv("DEMO_SEED_ACTIVE_HEATS", "2"))
    seed_future_heats: int = int(os.getenv("DEMO_SEED_FUTURE_HEATS", "4"))


# Equipment configuration
EQUIPMENT = {
    "BOF": {
        "proc_cd": "G12",
        "devices": ["G120", "G121", "G122"],
    },
    "LF": {
        "proc_cd": "G13",
        "devices": ["G130", "G131", "G132"],
    },
    "CCM": {
        "proc_cd": "G16",
        "devices": ["G160", "G161", "G162"],
    },
}

# Process flow order
PROCESS_FLOW = ["BOF", "LF", "CCM"]

# Crew codes
CREW_CODES = ("A", "B", "C", "D")

# Production line code
PRO_LINE_CD = "G1"

# Process status codes
class ProcessStatus:
    COMPLETED = 0
    ACTIVE = 1
    PENDING = 2
    CANCELED = 3  # Operation was canceled


# Special event configuration for 取消/回炉 events
# Each process can have:
#   - cancel_event: Event code that triggers cancellation (current + subsequent processes canceled)
#   - rework_event: Event code that triggers rework (process continues from 处理开始)
# Probabilities are configurable via environment variables
SPECIAL_EVENT_CONFIG = {
    "BOF": {
        "cancel_event": "G12007",  # 炉次取消
        "rework_event": None,       # BOF has no rework
    },
    "LF": {
        "cancel_event": "G13008",  # 炉次取消
        "rework_event": "G13007",  # 炉次回炉
    },
    "RH": {
        "cancel_event": "G15008",  # 炉次取消
        "rework_event": "G15007",  # 炉次回炉
    },
    "CCM": {
        "cancel_event": "G16015",  # 炉次开浇取消
        "rework_event": None,       # CCM has no rework
    },
}

# Environment variable driven probabilities for special events
# These are probabilities per-operation during historical seeding
import os as _os
CANCEL_EVENT_PROBABILITY = float(_os.getenv("CANCEL_EVENT_PROBABILITY", "0.02"))  # 2% chance
REWORK_EVENT_PROBABILITY = float(_os.getenv("REWORK_EVENT_PROBABILITY", "0.03"))  # 3% chance
