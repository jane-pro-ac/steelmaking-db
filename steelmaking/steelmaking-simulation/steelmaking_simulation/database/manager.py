"""Database connection manager for steelmaking simulation."""

import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import List, Dict, Any

from ..config import DatabaseConfig


class DatabaseManager:
    """Manages database connections and operations.
    
    This class provides the core database connectivity and inherits
    query methods from mixin classes for operations, warnings, and events.
    """

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._connection = None

    def connect(self):
        """Establish database connection."""
        if self._connection is None or self._connection.closed:
            self._connection = psycopg2.connect(self.config.connection_string)
            self._connection.autocommit = False
        return self._connection

    def close(self):
        """Close database connection."""
        if self._connection and not self._connection.closed:
            self._connection.close()

    @contextmanager
    def cursor(self):
        """Context manager for database cursor."""
        conn = self.connect()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()

    def get_steel_grades(self) -> List[Dict[str, Any]]:
        """Fetch all steel grades from the database."""
        with self.cursor() as cur:
            cur.execute("SELECT id, stl_grd_cd, stl_grd_nm FROM base.steel_grade")
            return cur.fetchall()

    def clear_operations(self):
        """Remove all operations, warnings, events, and KPI stats (demo reset)."""
        with self.cursor() as cur:
            cur.execute("""
                TRUNCATE steelmaking.steelmaking_event,
                         steelmaking.steelmaking_warning,
                         steelmaking.steelmaking_kpi_stats,
                         steelmaking.steelmaking_operation
                RESTART IDENTITY CASCADE
            """)

    # --- Operation Methods (delegated to OperationQueries) ---
    
    def get_active_operations(self) -> List[Dict[str, Any]]:
        """Get all active operations (status = 1)."""
        from .operations import OperationQueries
        return OperationQueries.get_active_operations(self)

    def get_pending_operations(self) -> List[Dict[str, Any]]:
        """Get all pending operations (status = 2)."""
        from .operations import OperationQueries
        return OperationQueries.get_pending_operations(self)

    def get_heat_operations(self, heat_no: int) -> List[Dict[str, Any]]:
        """Get all operations for a specific heat."""
        from .operations import OperationQueries
        return OperationQueries.get_heat_operations(self, heat_no)

    def get_device_current_operation(self, device_no: str):
        """Get the current active or pending operation for a device."""
        from .operations import OperationQueries
        return OperationQueries.get_device_current_operation(self, device_no)

    def get_latest_heat_no(self) -> int:
        """Get the latest heat number."""
        from .operations import OperationQueries
        return OperationQueries.get_latest_heat_no(self)

    def get_latest_heat_no_for_month(self, year: int, month: int) -> int:
        """Get the latest heat number for the given year-month window."""
        from .operations import OperationQueries
        return OperationQueries.get_latest_heat_no_for_month(self, year, month)

    def insert_operation(self, heat_no, pro_line_cd, proc_cd, device_no, crew_cd, 
                        stl_grd_id, stl_grd_cd, proc_status, plan_start_time, 
                        plan_end_time, real_start_time=None, real_end_time=None) -> int:
        """Insert a new operation record."""
        from .operations import OperationQueries
        return OperationQueries.insert_operation(
            self, heat_no, pro_line_cd, proc_cd, device_no, crew_cd,
            stl_grd_id, stl_grd_cd, proc_status, plan_start_time,
            plan_end_time, real_start_time, real_end_time
        )

    def update_operation_status(self, operation_id, proc_status, real_start_time=None,
                               real_end_time=None, device_no=None):
        """Update operation status and timestamps."""
        from .operations import OperationQueries
        return OperationQueries.update_operation_status(
            self, operation_id, proc_status, real_start_time, real_end_time, device_no
        )

    def update_operation_plan_times(self, operation_id, plan_start_time, plan_end_time):
        """Update planned timestamps for an operation."""
        from .operations import OperationQueries
        return OperationQueries.update_operation_plan_times(
            self, operation_id, plan_start_time, plan_end_time
        )

    def get_available_device(self, proc_cd: str, devices: List[str]):
        """Find an available device (no active operation) for the given process."""
        from .operations import OperationQueries
        return OperationQueries.get_available_device(self, proc_cd, devices)

    def get_device_operation_windows(self, device_no, min_window_start, exclude_operation_id=None):
        """Return scheduled/active windows on a device ordered by start time."""
        from .operations import OperationQueries
        return OperationQueries.get_device_operation_windows(
            self, device_no, min_window_start, exclude_operation_id
        )

    # --- Warning Methods (delegated to WarningQueries) ---

    def insert_warning(self, *, heat_no, pro_line_cd, proc_cd, device_no,
                      warning_level, warning_msg, warning_time_start, warning_time_end,
                      warning_code=None, extra=None) -> int:
        """Insert a warning event."""
        from .warnings import WarningQueries
        return WarningQueries.insert_warning(
            self, heat_no=heat_no, pro_line_cd=pro_line_cd, proc_cd=proc_cd,
            device_no=device_no, warning_level=warning_level, warning_msg=warning_msg,
            warning_time_start=warning_time_start, warning_time_end=warning_time_end,
            warning_code=warning_code, extra=extra
        )

    def get_operation_warning_count(self, *, heat_no, proc_cd, device_no, 
                                   window_start, window_end) -> int:
        """Return number of warnings already emitted within an operation window."""
        from .warnings import WarningQueries
        return WarningQueries.get_operation_warning_count(
            self, heat_no=heat_no, proc_cd=proc_cd, device_no=device_no,
            window_start=window_start, window_end=window_end
        )

    def get_operation_last_warning_end_time(self, *, heat_no, proc_cd, device_no,
                                           window_start, window_end):
        """Return the latest warning_time_end for an operation window, or None."""
        from .warnings import WarningQueries
        return WarningQueries.get_operation_last_warning_end_time(
            self, heat_no=heat_no, proc_cd=proc_cd, device_no=device_no,
            window_start=window_start, window_end=window_end
        )

    # --- Event Methods (delegated to EventQueries) ---

    def insert_event(self, *, heat_no, pro_line_cd, proc_cd, device_no,
                    event_code, event_name, event_msg, event_time_start, event_time_end, extra=None) -> int:
        """Insert a steelmaking event."""
        from .events import EventQueries
        return EventQueries.insert_event(
            self, heat_no=heat_no, pro_line_cd=pro_line_cd, proc_cd=proc_cd,
            device_no=device_no, event_code=event_code, event_name=event_name, event_msg=event_msg,
            event_time_start=event_time_start, event_time_end=event_time_end, extra=extra
        )

    def insert_events_batch(self, events: List[Dict[str, Any]]) -> int:
        """Insert multiple events in a batch."""
        from .events import EventQueries
        return EventQueries.insert_events_batch(self, events)

    def get_operation_event_count(self, *, heat_no, proc_cd, device_no,
                                 window_start, window_end) -> int:
        """Return number of events already emitted within an operation window."""
        from .events import EventQueries
        return EventQueries.get_operation_event_count(
            self, heat_no=heat_no, proc_cd=proc_cd, device_no=device_no,
            window_start=window_start, window_end=window_end
        )

    def get_operation_last_event_time(self, *, heat_no, proc_cd, device_no,
                                     window_start, window_end):
        """Return the latest event_time_start for an operation window, or None."""
        from .events import EventQueries
        return EventQueries.get_operation_last_event_time(
            self, heat_no=heat_no, proc_cd=proc_cd, device_no=device_no,
            window_start=window_start, window_end=window_end
        )

    def get_operation_events(self, *, heat_no, proc_cd, device_no,
                            window_start, window_end) -> List[Dict[str, Any]]:
        """Return all events for an operation within the given time window."""
        from .events import EventQueries
        return EventQueries.get_operation_events(
            self, heat_no=heat_no, proc_cd=proc_cd, device_no=device_no,
            window_start=window_start, window_end=window_end
        )

    # --- KPI Stats Methods (delegated to KpiStatsQueries) ---

    def get_kpi_definitions_by_proc_cd(self, proc_cd: str) -> List[Dict[str, Any]]:
        """Fetch all KPI definitions for a given process code."""
        from .kpi_stats import KpiStatsQueries
        return KpiStatsQueries.get_kpi_definitions_by_proc_cd(self, proc_cd)

    def get_all_kpi_definitions(self) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch all KPI definitions grouped by process code."""
        from .kpi_stats import KpiStatsQueries
        return KpiStatsQueries.get_all_kpi_definitions(self)

    def insert_kpi_stat(self, *, heat_no, pro_line_cd, proc_cd, device_no,
                       kpi_code, stat_value, sample_time, extra=None) -> int:
        """Insert a single KPI statistic record."""
        from .kpi_stats import KpiStatsQueries
        return KpiStatsQueries.insert_kpi_stat(
            self, heat_no=heat_no, pro_line_cd=pro_line_cd, proc_cd=proc_cd,
            device_no=device_no, kpi_code=kpi_code, stat_value=stat_value,
            sample_time=sample_time, extra=extra
        )

    def insert_kpi_stats_batch(self, stats: List[Dict[str, Any]]) -> int:
        """Insert multiple KPI statistics records in a batch."""
        from .kpi_stats import KpiStatsQueries
        return KpiStatsQueries.insert_kpi_stats_batch(self, stats)

    def get_operation_kpi_stats_count(self, *, heat_no, proc_cd, device_no,
                                     window_start, window_end) -> int:
        """Count KPI stats for an operation within a time window."""
        from .kpi_stats import KpiStatsQueries
        return KpiStatsQueries.get_operation_kpi_stats_count(
            self, heat_no=heat_no, proc_cd=proc_cd, device_no=device_no,
            window_start=window_start, window_end=window_end
        )

    def get_operation_last_kpi_sample_time(self, *, heat_no, proc_cd, device_no,
                                          window_start, window_end):
        """Get the latest sample_time for KPI stats in an operation window."""
        from .kpi_stats import KpiStatsQueries
        return KpiStatsQueries.get_operation_last_kpi_sample_time(
            self, heat_no=heat_no, proc_cd=proc_cd, device_no=device_no,
            window_start=window_start, window_end=window_end
        )

    def clear_kpi_stats(self) -> None:
        """Clear all KPI statistics (for demo reset)."""
        from .kpi_stats import KpiStatsQueries
        return KpiStatsQueries.clear_kpi_stats(self)
