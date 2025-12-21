"""Event-related database queries."""

from datetime import datetime
from typing import List, Dict, Any, Optional

from psycopg2.extras import Json, execute_values


class EventQueries:
    """Static methods for event database queries."""

    @staticmethod
    def insert_event(
        db,
        *,
        heat_no: int,
        pro_line_cd: str,
        proc_cd: str,
        device_no: str,
        event_code: str,
        event_name: str,
        event_msg: str,
        event_time_start: datetime,
        event_time_end: datetime,
        extra: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Insert a steelmaking event."""
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO steelmaking.steelmaking_event (
                    heat_no, pro_line_cd, proc_cd, device_no,
                    event_code, event_name, event_msg, event_time_start, event_time_end, extra
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    heat_no,
                    pro_line_cd,
                    proc_cd,
                    device_no,
                    event_code,
                    event_name,
                    event_msg,
                    event_time_start,
                    event_time_end,
                    Json(extra) if extra is not None else None,
                ),
            )
            result = cur.fetchone()
            return result["id"]

    @staticmethod
    def insert_events_batch(
        db,
        events: List[Dict[str, Any]],
    ) -> int:
        """Insert multiple events in a batch.
        
        Args:
            events: List of event dictionaries with keys:
                heat_no, pro_line_cd, proc_cd, device_no,
                event_code, event_name, event_msg, event_time_start, event_time_end, extra
                
        Returns:
            Number of events inserted
        """
        if not events:
            return 0
        
        with db.cursor() as cur:
            values = []
            for e in events:
                values.append((
                    e["heat_no"],
                    e["pro_line_cd"],
                    e["proc_cd"],
                    e["device_no"],
                    e["event_code"],
                    e["event_name"],
                    e["event_msg"],
                    e["event_time_start"],
                    e["event_time_end"],
                    Json(e.get("extra")) if e.get("extra") is not None else None,
                ))
            
            execute_values(
                cur,
                """
                INSERT INTO steelmaking.steelmaking_event (
                    heat_no, pro_line_cd, proc_cd, device_no,
                    event_code, event_name, event_msg, event_time_start, event_time_end, extra
                )
                VALUES %s
                """,
                values,
            )
            return len(values)

    @staticmethod
    def get_operation_event_count(
        db,
        *,
        heat_no: int,
        proc_cd: str,
        device_no: str,
        window_start: datetime,
        window_end: datetime,
    ) -> int:
        """Return number of events already emitted within an operation window."""
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS n
                FROM steelmaking.steelmaking_event
                WHERE heat_no = %s
                  AND proc_cd = %s
                  AND device_no = %s
                  AND event_time_start >= %s
                  AND event_time_start <= %s
                """,
                (heat_no, proc_cd, device_no, window_start, window_end),
            )
            row = cur.fetchone()
            return int(row["n"]) if row else 0

    @staticmethod
    def get_operation_last_event_time(
        db,
        *,
        heat_no: int,
        proc_cd: str,
        device_no: str,
        window_start: datetime,
        window_end: datetime,
    ):
        """Return the latest event_time_start for an operation window, or None."""
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT MAX(event_time_start) AS last_time
                FROM steelmaking.steelmaking_event
                WHERE heat_no = %s
                  AND proc_cd = %s
                  AND device_no = %s
                  AND event_time_start >= %s
                  AND event_time_start <= %s
                """,
                (heat_no, proc_cd, device_no, window_start, window_end),
            )
            row = cur.fetchone()
            return row["last_time"] if row else None

    @staticmethod
    def get_operation_events(
        db,
        *,
        heat_no: int,
        proc_cd: str,
        device_no: str,
        window_start: datetime,
        window_end: datetime,
    ) -> List[Dict[str, Any]]:
        """Return all events for an operation within the given time window."""
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT id, event_code, event_name, event_msg, event_time_start, event_time_end
                FROM steelmaking.steelmaking_event
                WHERE heat_no = %s
                  AND proc_cd = %s
                  AND device_no = %s
                  AND event_time_start >= %s
                  AND event_time_start <= %s
                ORDER BY event_time_start
                """,
                (heat_no, proc_cd, device_no, window_start, window_end),
            )
            return [dict(row) for row in cur.fetchall()]
