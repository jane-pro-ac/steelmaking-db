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

    # Allow BOF planning to look ahead when no slot is available right now (minutes)
    new_heat_lookahead_minutes: int = int(os.getenv("NEW_HEAT_LOOKAHEAD_MINUTES", "240"))
    
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
