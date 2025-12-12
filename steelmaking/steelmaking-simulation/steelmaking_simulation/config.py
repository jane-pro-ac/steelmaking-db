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
    interval: int = int(os.getenv("SIMULATION_INTERVAL", "5"))
    
    # Probability of starting a new heat each tick
    new_heat_probability: float = float(os.getenv("NEW_HEAT_PROBABILITY", "0.3"))
    
    # Operation duration range (minutes)
    min_operation_duration: int = 10
    max_operation_duration: int = 30
    
    # Gap between operations range (minutes)
    min_gap_duration: int = 1
    max_gap_duration: int = 10

    # Demo seeding
    seed_past_heats: int = int(os.getenv("DEMO_SEED_PAST_HEATS", "4"))
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
