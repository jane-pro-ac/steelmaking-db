"""Constants for steelmaking simulation."""


# Process status codes
class ProcessStatus:
    COMPLETED = 0
    ACTIVE = 1
    PENDING = 2
    CANCELED = 3  # Operation was canceled


# Process flow order
PROCESS_FLOW = ["BOF", "LF", "CCM"]

# Crew codes
CREW_CODES = ("A", "B", "C", "D")

# Production line code
PRO_LINE_CD = "G1"
