"""Database operations for steelmaking simulation."""

import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Optional, Any
from datetime import datetime
from contextlib import contextmanager

from .config import DatabaseConfig


class DatabaseManager:
    """Manages database connections and operations."""

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
            cur.execute("SELECT id, code, name FROM base.steel_grade")
            return cur.fetchall()

    def get_active_operations(self) -> List[Dict[str, Any]]:
        """Get all active operations (status = 1)."""
        with self.cursor() as cur:
            cur.execute("""
                SELECT id, heat_no, pro_line_cd, proc_cd, device_no, crew_cd,
                       stl_grd_id, stl_grd_cd, proc_status,
                       plan_start_time, plan_end_time,
                       real_start_time, real_end_time
                FROM steelmaking.steelmaking_operation
                WHERE proc_status = 1
                ORDER BY real_start_time
            """)
            return cur.fetchall()

    def get_pending_operations(self) -> List[Dict[str, Any]]:
        """Get all pending operations (status = 2)."""
        with self.cursor() as cur:
            cur.execute("""
                SELECT id, heat_no, pro_line_cd, proc_cd, device_no, crew_cd,
                       stl_grd_id, stl_grd_cd, proc_status,
                       plan_start_time, plan_end_time,
                       real_start_time, real_end_time
                FROM steelmaking.steelmaking_operation
                WHERE proc_status = 2
                ORDER BY plan_start_time
            """)
            return cur.fetchall()

    def get_heat_operations(self, heat_no: int) -> List[Dict[str, Any]]:
        """Get all operations for a specific heat."""
        with self.cursor() as cur:
            cur.execute("""
                SELECT id, heat_no, pro_line_cd, proc_cd, device_no, crew_cd,
                       stl_grd_id, stl_grd_cd, proc_status,
                       plan_start_time, plan_end_time,
                       real_start_time, real_end_time
                FROM steelmaking.steelmaking_operation
                WHERE heat_no = %s
                ORDER BY plan_start_time
            """, (heat_no,))
            return cur.fetchall()

    def get_device_current_operation(self, device_no: str) -> Optional[Dict[str, Any]]:
        """Get the current active or pending operation for a device."""
        with self.cursor() as cur:
            cur.execute("""
                SELECT id, heat_no, pro_line_cd, proc_cd, device_no, crew_cd,
                       stl_grd_id, stl_grd_cd, proc_status,
                       plan_start_time, plan_end_time,
                       real_start_time, real_end_time
                FROM steelmaking.steelmaking_operation
                WHERE device_no = %s AND proc_status IN (1, 2)
                ORDER BY proc_status, plan_start_time
                LIMIT 1
            """, (device_no,))
            return cur.fetchone()

    def get_latest_heat_no(self) -> int:
        """Get the latest heat number."""
        with self.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(MAX(heat_no), 0) as max_heat_no
                FROM steelmaking.steelmaking_operation
            """)
            result = cur.fetchone()
            return result['max_heat_no'] if result else 0

    def get_latest_heat_no_for_month(self, year: int, month: int) -> int:
        """Get the latest heat number for the given year-month window.

        Heat number encoding packs `year` and two-digit `month` into the high digits,
        so we use an integer range filter instead of trying to parse existing values.
        """
        # Encode the prefix for this month: YYMM + 5-digit sequence => YYMM00000-YYMM99999
        lower_bound = int(f"{year:02d}{month:02d}00000")
        upper_bound = int(f"{year:02d}{month:02d}99999")

        with self.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(MAX(heat_no), 0) AS max_heat_no
                FROM steelmaking.steelmaking_operation
                WHERE heat_no >= %s AND heat_no < %s
            """, (lower_bound, upper_bound))
            result = cur.fetchone()
            return result['max_heat_no'] if result else 0

    def insert_operation(
        self,
        heat_no: int,
        pro_line_cd: str,
        proc_cd: str,
        device_no: str,
        crew_cd: str,
        stl_grd_id: int,
        stl_grd_cd: str,
        proc_status: int,
        plan_start_time: datetime,
        plan_end_time: datetime,
        real_start_time: Optional[datetime] = None,
        real_end_time: Optional[datetime] = None
    ) -> int:
        """Insert a new operation record."""
        with self.cursor() as cur:
            cur.execute("""
                INSERT INTO steelmaking.steelmaking_operation
                (heat_no, pro_line_cd, proc_cd, device_no, crew_cd, stl_grd_id, stl_grd_cd,
                 proc_status, plan_start_time, plan_end_time, real_start_time, real_end_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (heat_no, pro_line_cd, proc_cd, device_no, crew_cd, stl_grd_id, stl_grd_cd,
                  proc_status, plan_start_time, plan_end_time, real_start_time, real_end_time))
            result = cur.fetchone()
            return result['id']

    def update_operation_status(
        self,
        operation_id: int,
        proc_status: int,
        real_start_time: Optional[datetime] = None,
        real_end_time: Optional[datetime] = None,
        device_no: Optional[str] = None
    ):
        """Update operation status and timestamps."""
        with self.cursor() as cur:
            cur.execute("""
                UPDATE steelmaking.steelmaking_operation
                SET proc_status = %s,
                    real_start_time = COALESCE(%s, real_start_time),
                    real_end_time = COALESCE(%s, real_end_time),
                    device_no = COALESCE(%s, device_no)
                WHERE id = %s
            """, (proc_status, real_start_time, real_end_time, device_no, operation_id))

    def update_operation_plan_times(
        self,
        operation_id: int,
        plan_start_time: datetime,
        plan_end_time: datetime
    ):
        """Update planned timestamps for an operation."""
        with self.cursor() as cur:
            cur.execute("""
                UPDATE steelmaking.steelmaking_operation
                SET plan_start_time = %s,
                    plan_end_time = %s
                WHERE id = %s
            """, (plan_start_time, plan_end_time, operation_id))

    def get_available_device(self, proc_cd: str, devices: List[str]) -> Optional[str]:
        """Find an available device (no active operation) for the given process."""
        with self.cursor() as cur:
            # Get devices that have active operations
            cur.execute("""
                SELECT DISTINCT device_no
                FROM steelmaking.steelmaking_operation
                WHERE proc_status = 1 AND device_no = ANY(%s)
            """, (devices,))
            busy_devices = {row['device_no'] for row in cur.fetchall()}
            
            # Return the first available device
            for device in devices:
                if device not in busy_devices:
                    return device
            return None

    def get_device_operation_windows(
        self,
        device_no: str,
        min_window_start: datetime,
        exclude_operation_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return scheduled/active windows on a device ordered by start time."""
        with self.cursor() as cur:
            cur.execute(
                """
                SELECT id,
                       proc_status,
                       plan_start_time,
                       plan_end_time,
                       real_start_time,
                       real_end_time
                FROM steelmaking.steelmaking_operation
                WHERE device_no = %s
                  AND (%s IS NULL OR id <> %s)
                  AND (
                        proc_status = 1
                        OR COALESCE(real_end_time, plan_end_time) >= %s
                  )
                ORDER BY COALESCE(real_start_time, plan_start_time)
                """,
                (device_no, exclude_operation_id, exclude_operation_id, min_window_start),
            )
            return cur.fetchall()

    def clear_operations(self):
        """Remove all operations (demo reset)."""
        with self.cursor() as cur:
            cur.execute("""
                TRUNCATE steelmaking.steelmaking_warning,
                         steelmaking.steelmaking_operation
                RESTART IDENTITY CASCADE
            """)

    def insert_warning(
        self,
        *,
        operation_id: int,
        heat_no: int,
        pro_line_cd: str,
        proc_cd: str,
        device_no: str,
        crew_cd: str,
        warning_level: int,
        warning_msg: str,
        warning_time_start: datetime,
        warning_time_end: datetime,
        warning_code: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Insert a warning linked to an operation."""
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO steelmaking.steelmaking_warning (
                    operation_id, heat_no, pro_line_cd, proc_cd, device_no, crew_cd,
                    warning_code, warning_msg, warning_level, warning_time_start, warning_time_end, extra
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    operation_id,
                    heat_no,
                    pro_line_cd,
                    proc_cd,
                    device_no,
                    crew_cd,
                    warning_code,
                    warning_msg,
                    warning_level,
                    warning_time_start,
                    warning_time_end,
                    extra,
                ),
            )
            result = cur.fetchone()
            return result["id"]

    def get_operation_warning_count(self, operation_id: int) -> int:
        """Return number of warnings already emitted for an operation."""
        with self.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS n
                FROM steelmaking.steelmaking_warning
                WHERE operation_id = %s
                """,
                (operation_id,),
            )
            row = cur.fetchone()
            return int(row["n"]) if row else 0

    def get_operation_last_warning_end_time(self, operation_id: int):
        """Return the latest warning_time_end for an operation, or None."""
        with self.cursor() as cur:
            cur.execute(
                """
                SELECT MAX(warning_time_end) AS last_end
                FROM steelmaking.steelmaking_warning
                WHERE operation_id = %s
                """,
                (operation_id,),
            )
            row = cur.fetchone()
            return row["last_end"] if row else None
