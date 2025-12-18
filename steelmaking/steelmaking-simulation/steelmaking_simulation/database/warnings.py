"""Warning-related database queries."""

from datetime import datetime
from typing import Dict, Any, Optional

from psycopg2.extras import Json


class WarningQueries:
    """Static methods for warning database queries."""

    @staticmethod
    def insert_warning(
        db,
        *,
        heat_no: int,
        pro_line_cd: str,
        proc_cd: str,
        device_no: str,
        warning_level: int,
        warning_msg: str,
        warning_time_start: datetime,
        warning_time_end: datetime,
        warning_code: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Insert a warning event (operation_id column removed from schema)."""
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO steelmaking.steelmaking_warning (
                    heat_no, pro_line_cd, proc_cd, device_no,
                    warning_code, warning_msg, warning_level,
                    warning_time_start, warning_time_end, extra
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    heat_no,
                    pro_line_cd,
                    proc_cd,
                    device_no,
                    warning_code,
                    warning_msg,
                    warning_level,
                    warning_time_start,
                    warning_time_end,
                    Json(extra) if extra is not None else None,
                ),
            )
            result = cur.fetchone()
            return result["id"]

    @staticmethod
    def get_operation_warning_count(
        db,
        *,
        heat_no: int,
        proc_cd: str,
        device_no: str,
        window_start: datetime,
        window_end: datetime,
    ) -> int:
        """Return number of warnings already emitted within an operation window."""
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS n
                FROM steelmaking.steelmaking_warning
                WHERE heat_no = %s
                  AND proc_cd = %s
                  AND device_no = %s
                  AND warning_time_start >= %s
                  AND warning_time_start <= %s
                """,
                (heat_no, proc_cd, device_no, window_start, window_end),
            )
            row = cur.fetchone()
            return int(row["n"]) if row else 0

    @staticmethod
    def get_operation_last_warning_end_time(
        db,
        *,
        heat_no: int,
        proc_cd: str,
        device_no: str,
        window_start: datetime,
        window_end: datetime,
    ):
        """Return the latest warning_time_end for an operation window, or None."""
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT MAX(warning_time_end) AS last_end
                FROM steelmaking.steelmaking_warning
                WHERE heat_no = %s
                  AND proc_cd = %s
                  AND device_no = %s
                  AND warning_time_start >= %s
                  AND warning_time_start <= %s
                """,
                (heat_no, proc_cd, device_no, window_start, window_end),
            )
            row = cur.fetchone()
            return row["last_end"] if row else None
