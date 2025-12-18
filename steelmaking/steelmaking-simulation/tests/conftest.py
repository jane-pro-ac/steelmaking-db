"""Pytest configuration and shared fixtures for steelmaking simulation tests."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytest

from steelmaking_simulation.config import (
    DatabaseConfig,
    SimulationConfig,
    ProcessStatus,
    EQUIPMENT,
    PROCESS_FLOW,
)
from steelmaking_simulation.core import SteelmakingSimulator
from steelmaking_simulation.utils import CST


class FakeDatabaseManager:
    """In-memory stand-in for DatabaseManager to test scheduling logic."""

    def __init__(self):
        self.operations: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.events: List[Dict[str, Any]] = []

    def clear_operations(self):
        self.operations = []
        self.warnings = []
        self.events = []

    def get_steel_grades(self) -> List[Dict[str, Any]]:
        return [{"id": 1, "stl_grd_cd": "G-TEST", "stl_grd_nm": "Test Grade"}]

    def get_latest_heat_no_for_month(self, year: int, month: int) -> int:
        lower_bound = int(f"{year:02d}{month:02d}00000")
        upper_bound = int(f"{year:02d}{month:02d}99999")
        candidates = [op["heat_no"] for op in self.operations if lower_bound <= op["heat_no"] < upper_bound]
        return max(candidates) if candidates else 0

    def insert_operation(
        self,
        heat_no: int,
        pro_line_cd: str,
        proc_cd: str,
        device_no: str,
        crew_cd: str,
        stl_grd_id: int,
        stl_grd_cd: str,
        proc_status: str,
        plan_start_time: datetime,
        plan_end_time: datetime,
        real_start_time: Optional[datetime] = None,
        real_end_time: Optional[datetime] = None,
    ) -> int:
        op_id = len(self.operations) + 1
        self.operations.append(
            {
                "id": op_id,
                "heat_no": heat_no,
                "pro_line_cd": pro_line_cd,
                "proc_cd": proc_cd,
                "device_no": device_no,
                "crew_cd": crew_cd,
                "stl_grd_id": stl_grd_id,
                "stl_grd_cd": stl_grd_cd,
                "proc_status": proc_status,
                "plan_start_time": plan_start_time,
                "plan_end_time": plan_end_time,
                "real_start_time": real_start_time,
                "real_end_time": real_end_time,
            }
        )
        return op_id

    def insert_warning(
        self,
        *,
        heat_no: int,
        pro_line_cd: str,
        proc_cd: str,
        device_no: str,
        warning_code: str,
        warning_msg: str,
        warning_level: str,
        warning_time_start: datetime,
        warning_time_end: datetime,
        extra: Optional[Dict] = None,
    ) -> int:
        warn_id = len(self.warnings) + 1
        self.warnings.append(
            {
                "id": warn_id,
                "heat_no": heat_no,
                "pro_line_cd": pro_line_cd,
                "proc_cd": proc_cd,
                "device_no": device_no,
                "warning_code": warning_code,
                "warning_msg": warning_msg,
                "warning_level": warning_level,
                "warning_time_start": warning_time_start,
                "warning_time_end": warning_time_end,
                "extra": extra,
            }
        )
        return warn_id

    def get_operation_warning_count(self, *, heat_no, proc_cd, device_no, window_start, window_end) -> int:
        return sum(
            1
            for w in self.warnings
            if w.get("heat_no") == heat_no
            and w.get("proc_cd") == proc_cd
            and w.get("device_no") == device_no
            and w.get("warning_time_start") >= window_start
            and w.get("warning_time_start") <= window_end
        )

    def get_operation_last_warning_end_time(self, *, heat_no, proc_cd, device_no, window_start, window_end):
        ends = [
            w.get("warning_time_end")
            for w in self.warnings
            if w.get("heat_no") == heat_no
            and w.get("proc_cd") == proc_cd
            and w.get("device_no") == device_no
            and w.get("warning_time_start") >= window_start
            and w.get("warning_time_start") <= window_end
            and w.get("warning_time_end")
        ]
        return max(ends) if ends else None

    def get_active_operations(self) -> List[Dict[str, Any]]:
        """Return operations that are ACTIVE."""
        return sorted(
            [op for op in self.operations if op["proc_status"] == ProcessStatus.ACTIVE],
            key=lambda op: op["real_start_time"] or op["plan_start_time"],
        )

    def get_pending_operations(self) -> List[Dict[str, Any]]:
        """Return operations that are pending."""
        return sorted(
            [op for op in self.operations if op["proc_status"] == ProcessStatus.PENDING],
            key=lambda op: op["plan_start_time"],
        )

    def get_heat_operations(self, heat_no: int) -> List[Dict[str, Any]]:
        """Return all operations for a given heat number."""
        return sorted(
            [op for op in self.operations if op["heat_no"] == heat_no],
            key=lambda op: op["plan_start_time"],
        )

    def update_operation_status(
        self,
        operation_id: int,
        proc_status: int,
        real_start_time=None,
        real_end_time=None,
        device_no=None,
    ):
        for op in self.operations:
            if op["id"] == operation_id:
                op["proc_status"] = proc_status
                op["real_start_time"] = real_start_time or op["real_start_time"]
                op["real_end_time"] = real_end_time or op["real_end_time"]
                if device_no:
                    op["device_no"] = device_no
                break

    def update_operation_plan_times(self, operation_id: int, plan_start_time, plan_end_time):
        for op in self.operations:
            if op["id"] == operation_id:
                op["plan_start_time"] = plan_start_time
                op["plan_end_time"] = plan_end_time
                break

    def get_device_current_operation(self, device_no: str):
        candidates = [
            op for op in self.operations 
            if op["device_no"] == device_no 
            and op["proc_status"] in (ProcessStatus.ACTIVE, ProcessStatus.PENDING)
        ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda op: (op["proc_status"], op["plan_start_time"]))[0]

    def get_available_device(self, proc_cd: str, devices):
        busy = {op["device_no"] for op in self.operations if op["proc_status"] == ProcessStatus.ACTIVE}
        for device in devices:
            if device not in busy:
                return device
        return None

    def get_device_operation_windows(self, device_no: str, min_window_start: datetime, exclude_operation_id=None):
        windows = []
        for op in self.operations:
            if op["device_no"] != device_no:
                continue
            if exclude_operation_id and op["id"] == exclude_operation_id:
                continue
            end_time = op["real_end_time"] or op["plan_end_time"]
            if op["proc_status"] != ProcessStatus.ACTIVE and end_time < min_window_start:
                continue
            windows.append(op)
        windows.sort(key=lambda op: op["real_start_time"] or op["plan_start_time"])
        return windows

    # Event methods
    def insert_event(
        self,
        *,
        heat_no: int,
        pro_line_cd: str,
        proc_cd: str,
        device_no: str,
        event_code: str,
        event_msg: str,
        event_time_start: datetime,
        event_time_end: datetime,
        extra: Optional[Dict] = None,
    ) -> int:
        event_id = len(self.events) + 1
        self.events.append(
            {
                "id": event_id,
                "heat_no": heat_no,
                "pro_line_cd": pro_line_cd,
                "proc_cd": proc_cd,
                "device_no": device_no,
                "event_code": event_code,
                "event_msg": event_msg,
                "event_time_start": event_time_start,
                "event_time_end": event_time_end,
                "extra": extra,
            }
        )
        return event_id

    def insert_events_batch(self, events):
        count = 0
        for e in events:
            self.insert_event(
                heat_no=e["heat_no"],
                pro_line_cd=e["pro_line_cd"],
                proc_cd=e["proc_cd"],
                device_no=e["device_no"],
                event_code=e.get("event_code"),
                event_msg=e["event_msg"],
                event_time_start=e["event_time_start"],
                event_time_end=e["event_time_end"],
                extra=e.get("extra"),
            )
            count += 1
        return count

    def get_operation_event_count(self, *, heat_no, proc_cd, device_no, window_start, window_end) -> int:
        return sum(
            1
            for e in self.events
            if e.get("heat_no") == heat_no
            and e.get("proc_cd") == proc_cd
            and e.get("device_no") == device_no
            and e.get("event_time_start") >= window_start
            and e.get("event_time_start") <= window_end
        )

    def get_operation_last_event_time(self, *, heat_no, proc_cd, device_no, window_start, window_end):
        times = [
            e.get("event_time_start")
            for e in self.events
            if e.get("heat_no") == heat_no
            and e.get("proc_cd") == proc_cd
            and e.get("device_no") == device_no
            and e.get("event_time_start") >= window_start
            and e.get("event_time_start") <= window_end
        ]
        return max(times) if times else None

    def get_operation_events(self, *, heat_no, proc_cd, device_no, window_start, window_end):
        return [
            e for e in self.events
            if e.get("heat_no") == heat_no
            and e.get("proc_cd") == proc_cd
            and e.get("device_no") == device_no
            and e.get("event_time_start") >= window_start
            and e.get("event_time_start") <= window_end
        ]

    def get_operations_by_heat_no(self, heat_no: int) -> List[Dict[str, Any]]:
        """Return all operations for a given heat number."""
        return [op for op in self.operations if op["heat_no"] == heat_no]

    # Compatibility stubs
    def connect(self): ...
    def close(self): ...
    def cursor(self): raise RuntimeError("Not implemented for fake DB")


@pytest.fixture
def fake_db() -> FakeDatabaseManager:
    """Provide a fresh FakeDatabaseManager instance for each test."""
    return FakeDatabaseManager()


@pytest.fixture
def db_config() -> DatabaseConfig:
    """Provide a default DatabaseConfig for tests."""
    return DatabaseConfig()


@pytest.fixture
def sim_config() -> SimulationConfig:
    """Provide a default SimulationConfig for tests."""
    return SimulationConfig(interval=0)
