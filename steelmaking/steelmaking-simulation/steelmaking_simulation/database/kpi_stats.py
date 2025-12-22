"""Database queries for KPI statistics."""

from typing import Any, Dict, List, Optional
from decimal import Decimal

from psycopg2.extras import Json


class KpiStatsQueries:
    """Database query methods for KPI definitions and statistics."""
    
    @staticmethod
    def get_kpi_definitions_by_proc_cd(db, proc_cd: str) -> List[Dict[str, Any]]:
        """Fetch all KPI definitions for a given process code.
        
        Args:
            db: Database manager instance
            proc_cd: Process code (e.g., G12, G13, G15, G16)
            
        Returns:
            List of KPI definition dicts with keys:
            - kpi_code: The KPI code
            - kpi_name: Display name
            - unit: Unit of measurement
            - int_digits: Number of integer digits
            - decimal_digits: Number of decimal digits
            - upper_limit: Upper limit for value range
            - lower_limit: Lower limit for value range
        """
        with db.cursor() as cur:
            cur.execute("""
                SELECT kpi_code, kpi_name, unit, 
                       int_digits, decimal_digits, 
                       upper_limit, lower_limit
                FROM steelmaking.steelmaking_kpi_def
                WHERE proc_cd = %s AND display_enabled = true
                ORDER BY display_order
            """, (proc_cd,))
            return [dict(row) for row in cur.fetchall()]
    
    @staticmethod
    def get_all_kpi_definitions(db) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch all KPI definitions grouped by process code.
        
        Args:
            db: Database manager instance
            
        Returns:
            Dict mapping proc_cd to list of KPI definitions
        """
        with db.cursor() as cur:
            cur.execute("""
                SELECT proc_cd, kpi_code, kpi_name, unit, 
                       int_digits, decimal_digits, 
                       upper_limit, lower_limit
                FROM steelmaking.steelmaking_kpi_def
                WHERE display_enabled = true
                ORDER BY proc_cd, display_order
            """)
            rows = cur.fetchall()
        
        result: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            proc_cd = row["proc_cd"]
            if proc_cd not in result:
                result[proc_cd] = []
            result[proc_cd].append(dict(row))
        return result
    
    @staticmethod
    def insert_kpi_stat(
        db,
        *,
        heat_no: int,
        pro_line_cd: str,
        proc_cd: str,
        device_no: str,
        kpi_code: str,
        stat_value: Optional[Decimal],
        sample_time,
        extra: Optional[Dict] = None,
    ) -> int:
        """Insert a single KPI statistic record.
        
        Args:
            db: Database manager instance
            heat_no: Heat number
            pro_line_cd: Production line code
            proc_cd: Process code
            device_no: Device number
            kpi_code: KPI code
            stat_value: KPI value
            sample_time: Sample timestamp
            extra: Optional extra JSON data
            
        Returns:
            ID of the inserted record
        """
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO steelmaking.steelmaking_kpi_stats 
                    (heat_no, pro_line_cd, proc_cd, device_no, kpi_code, stat_value, sample_time, extra)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (heat_no, pro_line_cd, proc_cd, device_no, kpi_code, stat_value, sample_time,
                  Json(extra) if extra is not None else None))
            return cur.fetchone()["id"]
    
    @staticmethod
    def insert_kpi_stats_batch(db, stats: List[Dict[str, Any]]) -> int:
        """Insert multiple KPI statistics records in a batch.
        
        Args:
            db: Database manager instance
            stats: List of stat dicts with keys matching insert_kpi_stat params
            
        Returns:
            Number of records inserted
        """
        if not stats:
            return 0
        
        with db.cursor() as cur:
            from psycopg2.extras import execute_values
            
            values = [
                (
                    s["heat_no"],
                    s["pro_line_cd"],
                    s["proc_cd"],
                    s["device_no"],
                    s["kpi_code"],
                    s.get("stat_value"),
                    s["sample_time"],
                    Json(s.get("extra")) if s.get("extra") is not None else None,
                )
                for s in stats
            ]
            
            execute_values(
                cur,
                """
                INSERT INTO steelmaking.steelmaking_kpi_stats 
                    (heat_no, pro_line_cd, proc_cd, device_no, kpi_code, stat_value, sample_time, extra)
                VALUES %s
                """,
                values,
            )
            return len(values)
    
    @staticmethod
    def get_operation_kpi_stats_count(
        db,
        *,
        heat_no: int,
        proc_cd: str,
        device_no: str,
        window_start,
        window_end,
    ) -> int:
        """Count KPI stats for an operation within a time window.
        
        Args:
            db: Database manager instance
            heat_no: Heat number
            proc_cd: Process code
            device_no: Device number
            window_start: Start of time window
            window_end: End of time window
            
        Returns:
            Number of KPI stat records
        """
        with db.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) as cnt
                FROM steelmaking.steelmaking_kpi_stats
                WHERE heat_no = %s
                  AND proc_cd = %s
                  AND device_no = %s
                  AND sample_time >= %s
                  AND sample_time <= %s
            """, (heat_no, proc_cd, device_no, window_start, window_end))
            return cur.fetchone()["cnt"]
    
    @staticmethod
    def get_operation_last_kpi_sample_time(
        db,
        *,
        heat_no: int,
        proc_cd: str,
        device_no: str,
        window_start,
        window_end,
    ):
        """Get the latest sample_time for KPI stats in an operation window.
        
        Args:
            db: Database manager instance
            heat_no: Heat number
            proc_cd: Process code
            device_no: Device number
            window_start: Start of time window
            window_end: End of time window
            
        Returns:
            Latest sample_time or None
        """
        with db.cursor() as cur:
            cur.execute("""
                SELECT MAX(sample_time) as last_time
                FROM steelmaking.steelmaking_kpi_stats
                WHERE heat_no = %s
                  AND proc_cd = %s
                  AND device_no = %s
                  AND sample_time >= %s
                  AND sample_time <= %s
            """, (heat_no, proc_cd, device_no, window_start, window_end))
            row = cur.fetchone()
            return row["last_time"] if row else None
    
    @staticmethod
    def clear_kpi_stats(db) -> None:
        """Clear all KPI statistics (for demo reset)."""
        with db.cursor() as cur:
            cur.execute("TRUNCATE steelmaking.steelmaking_kpi_stats RESTART IDENTITY")
