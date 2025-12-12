"""Device scheduling helper to enforce timing constraints."""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from .config import SimulationConfig, EQUIPMENT, ProcessStatus
from .database import DatabaseManager
from .time_utils import CST


@dataclass
class Slot:
    device_no: str
    plan_start: datetime
    plan_end: datetime


class DeviceScheduler:
    """Finds non-overlapping device slots honoring rest and duration constraints."""

    def __init__(self, db: DatabaseManager, config: SimulationConfig):
        self.db = db
        self.config = config

    def _normalize_window(self, row: Dict[str, Any]) -> Optional[tuple]:
        """Convert a DB row into a (start, end) tuple with safeguards for active ops."""
        start = row["real_start_time"] or row["plan_start_time"]
        end = row["real_end_time"] or row["plan_end_time"]
        if not start:
            return None

        if end is None:
            # Fallback for malformed rows: assume worst-case duration.
            end = start + timedelta(minutes=self.config.max_operation_duration)

        return (start, end)

    def _get_device_windows(
        self,
        device_no: str,
        desired_start: datetime,
        exclude_operation_id: Optional[int],
    ) -> List[tuple]:
        """Fetch and sort windows around the desired start."""
        lookback_start = datetime.min.replace(tzinfo=CST)
        rows = self.db.get_device_operation_windows(device_no, lookback_start, exclude_operation_id)
        windows: List[tuple] = []
        for row in rows:
            normalized = self._normalize_window(row)
            if normalized:
                windows.append(normalized)
        windows.sort(key=lambda w: w[0])
        return windows

    def find_slot(
        self,
        process_name: str,
        desired_start: datetime,
        latest_start: Optional[datetime],
        duration: timedelta,
        devices: Optional[List[str]] = None,
        exclude_operation_id: Optional[int] = None,
    ) -> Optional[Slot]:
        """Pick a device and earliest valid slot.

        Hard constraints (including initialization):
        - No overlap per device.
        - Rest between consecutive operations on the same device is within
          [min_rest_duration_minutes, max_rest_duration_minutes].
        """
        proc_devices = devices if devices is not None else EQUIPMENT[process_name]["devices"]
        max_rest = timedelta(minutes=self.config.max_rest_duration_minutes)
        min_rest = timedelta(minutes=self.config.min_rest_duration_minutes)

        best_valid: Optional[Slot] = None

        for device_no in random.sample(proc_devices, k=len(proc_devices)):
            windows = self._get_device_windows(device_no, desired_start, exclude_operation_id)

            selected_start: Optional[datetime] = None
            prev_end: Optional[datetime] = None
            for idx in range(len(windows) + 1):
                next_start = windows[idx][0] if idx < len(windows) else None

                lower = desired_start
                upper_candidates: List[datetime] = []

                if prev_end is not None:
                    lower = max(lower, prev_end + min_rest)
                    upper_candidates.append(prev_end + max_rest)

                if next_start is not None:
                    # Fit before next window and keep rest bounds to next window.
                    upper_candidates.append(next_start - duration)
                    upper_candidates.append(next_start - min_rest - duration)
                    lower = max(lower, next_start - max_rest - duration)

                if prev_end is not None:
                    lower = max(lower, prev_end)

                upper = min(upper_candidates) if upper_candidates else None
                if upper is not None and lower > upper:
                    if idx < len(windows):
                        prev_end = windows[idx][1]
                    continue

                if next_start is not None and lower + duration > next_start:
                    if idx < len(windows):
                        prev_end = windows[idx][1]
                    continue

                selected_start = lower
                break

            if selected_start is None:
                continue

            plan_start = selected_start
            if latest_start is not None and plan_start > latest_start:
                continue
            plan_end = plan_start + duration
            slot = Slot(device_no=device_no, plan_start=plan_start, plan_end=plan_end)

            if best_valid is None or plan_start < best_valid.plan_start:
                best_valid = slot

        return best_valid
