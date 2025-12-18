"""Operation-related database queries."""

from datetime import datetime
from typing import List, Dict, Any, Optional


class OperationQueries:
    """Static methods for operation database queries."""

    @staticmethod
    def get_active_operations(db) -> List[Dict[str, Any]]:
        """Get all active operations (status = 1)."""
        with db.cursor() as cur:
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

    @staticmethod
    def get_pending_operations(db) -> List[Dict[str, Any]]:
        """Get all pending operations (status = 2)."""
        with db.cursor() as cur:
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

    @staticmethod
    def get_heat_operations(db, heat_no: int) -> List[Dict[str, Any]]:
        """Get all operations for a specific heat."""
        with db.cursor() as cur:
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

    @staticmethod
    def get_device_current_operation(db, device_no: str) -> Optional[Dict[str, Any]]:
        """Get the current active or pending operation for a device."""
        with db.cursor() as cur:
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

    @staticmethod
    def get_latest_heat_no(db) -> int:
        """Get the latest heat number."""
        with db.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(MAX(heat_no), 0) as max_heat_no
                FROM steelmaking.steelmaking_operation
            """)
            result = cur.fetchone()
            return result['max_heat_no'] if result else 0

    @staticmethod
    def get_latest_heat_no_for_month(db, year: int, month: int) -> int:
        """Get the latest heat number for the given year-month window.

        Heat number encoding packs `year` and two-digit `month` into the high digits,
        so we use an integer range filter instead of trying to parse existing values.
        """
        lower_bound = int(f"{year:02d}{month:02d}00000")
        upper_bound = int(f"{year:02d}{month:02d}99999")

        with db.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(MAX(heat_no), 0) AS max_heat_no
                FROM steelmaking.steelmaking_operation
                WHERE heat_no >= %s AND heat_no < %s
            """, (lower_bound, upper_bound))
            result = cur.fetchone()
            return result['max_heat_no'] if result else 0

    @staticmethod
    def insert_operation(
        db,
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
        with db.cursor() as cur:
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

    @staticmethod
    def update_operation_status(
        db,
        operation_id: int,
        proc_status: int,
        real_start_time: Optional[datetime] = None,
        real_end_time: Optional[datetime] = None,
        device_no: Optional[str] = None
    ):
        """Update operation status and timestamps."""
        with db.cursor() as cur:
            cur.execute("""
                UPDATE steelmaking.steelmaking_operation
                SET proc_status = %s,
                    real_start_time = COALESCE(%s, real_start_time),
                    real_end_time = COALESCE(%s, real_end_time),
                    device_no = COALESCE(%s, device_no)
                WHERE id = %s
            """, (proc_status, real_start_time, real_end_time, device_no, operation_id))

    @staticmethod
    def update_operation_plan_times(
        db,
        operation_id: int,
        plan_start_time: datetime,
        plan_end_time: datetime
    ):
        """Update planned timestamps for an operation."""
        with db.cursor() as cur:
            cur.execute("""
                UPDATE steelmaking.steelmaking_operation
                SET plan_start_time = %s,
                    plan_end_time = %s
                WHERE id = %s
            """, (plan_start_time, plan_end_time, operation_id))

    @staticmethod
    def get_available_device(db, proc_cd: str, devices: List[str]) -> Optional[str]:
        """Find an available device (no active operation) for the given process."""
        with db.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT device_no
                FROM steelmaking.steelmaking_operation
                WHERE proc_status = 1 AND device_no = ANY(%s)
            """, (devices,))
            busy_devices = {row['device_no'] for row in cur.fetchall()}
            
            for device in devices:
                if device not in busy_devices:
                    return device
            return None

    @staticmethod
    def get_device_operation_windows(
        db,
        device_no: str,
        min_window_start: datetime,
        exclude_operation_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return scheduled/active windows on a device ordered by start time."""
        with db.cursor() as cur:
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
