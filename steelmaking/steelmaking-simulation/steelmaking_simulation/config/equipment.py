"""Equipment configuration for steelmaking simulation."""

import os


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
CANCEL_EVENT_PROBABILITY = float(os.getenv("CANCEL_EVENT_PROBABILITY", "0.02"))  # 2% chance
REWORK_EVENT_PROBABILITY = float(os.getenv("REWORK_EVENT_PROBABILITY", "0.03"))  # 3% chance
