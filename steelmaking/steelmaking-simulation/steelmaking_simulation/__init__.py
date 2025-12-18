"""Steelmaking simulation package.

This package provides a comprehensive steelmaking operations simulator.
The code is organized into the following subpackages:

- config/: Configuration settings, constants, and equipment definitions
- database/: Database operations and connection management
- utils/: Utility functions (time handling, etc.)
- events/: Event generation and engine
- warnings/: Warning generation and engine
- core/: Core simulation logic (simulator, scheduler, processor)
- seeding/: Initial data seeding
- planning/: Heat planning logic

Import examples:
  - from steelmaking_simulation.config import DatabaseConfig
  - from steelmaking_simulation.events import EventGenerator
  - from steelmaking_simulation.core import SteelmakingSimulator
"""

__version__ = "0.1.0"

# Re-export from subpackages for convenience
from .config import (
    DatabaseConfig,
    SimulationConfig,
    ProcessStatus,
    PROCESS_FLOW,
    PRO_LINE_CD,
    CREW_CODES,
    EQUIPMENT,
    SPECIAL_EVENT_CONFIG,
    CANCEL_EVENT_PROBABILITY,
    REWORK_EVENT_PROBABILITY,
)
from .database import (
    DatabaseManager,
    OperationQueries,
    WarningQueries,
    EventQueries,
)
from .utils import CST
from .events import (
    EventEngine,
    EventEngineConfig,
    EventGenerator,
    Event,
    EventSequenceResult,
    SpecialEventType,
    EVENT_CODES,
    PROC_CD_TO_NAME,
    EventSequenceConfig,
    EVENT_SEQUENCE_CONFIGS,
    EventMessageGenerator,
)
from .warnings import (
    WarningEngine,
    WARNING_TEMPLATES,
    WarningPayload,
)
from .core import (
    SteelmakingSimulator,
    DeviceScheduler,
    Slot,
    OperationProcessor,
    OperationProcessorContext,
)
from .seeding import (
    OperationSeeder,
    SeedContext,
)
from .planning import (
    HeatPlanner,
    HeatPlanContext,
)

__all__ = [
    # Config
    "DatabaseConfig",
    "SimulationConfig",
    "ProcessStatus",
    "PROCESS_FLOW",
    "PRO_LINE_CD",
    "CREW_CODES",
    "EQUIPMENT",
    "SPECIAL_EVENT_CONFIG",
    "CANCEL_EVENT_PROBABILITY",
    "REWORK_EVENT_PROBABILITY",
    # Database
    "DatabaseManager",
    "OperationQueries",
    "WarningQueries",
    "EventQueries",
    # Utils
    "CST",
    # Events
    "EventEngine",
    "EventEngineConfig",
    "EventGenerator",
    "Event",
    "EventSequenceResult",
    "SpecialEventType",
    "EVENT_CODES",
    "PROC_CD_TO_NAME",
    "EventSequenceConfig",
    "EVENT_SEQUENCE_CONFIGS",
    "EventMessageGenerator",
    # Warnings
    "WarningEngine",
    "WARNING_TEMPLATES",
    "WarningPayload",
    # Core
    "SteelmakingSimulator",
    "DeviceScheduler",
    "Slot",
    "OperationProcessor",
    "OperationProcessorContext",
    # Seeding
    "OperationSeeder",
    "SeedContext",
    # Planning
    "HeatPlanner",
    "HeatPlanContext",
]

